#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod update;

use cts_save_core::{Editor, Entry, files};
use serde::Serialize;
use std::{
    path::{Path, PathBuf},
    sync::Mutex,
};
use tauri::{Manager, State};

#[derive(Default)]
struct AppState(Mutex<Option<Session>>);

struct Session {
    editor: Editor,
    baseline: Vec<u8>,
    baseline_entries: Vec<Entry>,
    source: PathBuf,
    snapshot: files::Snapshot,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct FileInfo {
    path: String,
    name: String,
    exists: bool,
    size: u64,
    modified: u64,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct View {
    path: String,
    entries: Vec<Entry>,
    files: Vec<FileInfo>,
    dirty: bool,
    can_undo: bool,
    can_redo: bool,
    changed_ids: Vec<usize>,
    original_values: std::collections::HashMap<usize, String>,
}

fn file_info(path: &Path) -> FileInfo {
    let metadata = path.metadata().ok();
    FileInfo {
        path: path.to_string_lossy().into(),
        name: path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .into(),
        exists: metadata.as_ref().is_some_and(|m| m.is_file()),
        size: metadata.as_ref().map(|m| m.len()).unwrap_or(0),
        modified: metadata
            .and_then(|m| m.modified().ok())
            .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_secs())
            .unwrap_or(0),
    }
}

impl Session {
    fn view(&self) -> View {
        let entries = self.editor.parse();
        let changed_ids = entries
            .iter()
            .filter_map(|entry| {
                let original = self.baseline_entries.get(entry.id)?;
                (self.editor.data[entry.start..entry.end]
                    != self.baseline[original.start..original.end])
                    .then_some(entry.id)
            })
            .collect();
        View {
            path: self.source.to_string_lossy().into(),
            entries,
            files: self.snapshot.iter().map(|(p, _)| file_info(p)).collect(),
            dirty: self.editor.data != self.baseline,
            can_undo: self.editor.can_undo(),
            can_redo: self.editor.can_redo(),
            changed_ids,
            original_values: self
                .baseline_entries
                .iter()
                .map(|entry| (entry.id, entry.value.clone()))
                .collect(),
        }
    }
}

#[derive(Serialize)]
struct Location {
    label: String,
    path: String,
    files: Vec<FileInfo>,
}

#[tauri::command]
fn discover_saves() -> Vec<Location> {
    let Some(home) = dirs::home_dir() else {
        return Vec::new();
    };
    let mut candidates = Vec::<(&str, PathBuf)>::new();
    if cfg!(target_os = "windows") {
        // LocalAppDataLow lives alongside LocalAppData (supports redirected profiles).
        let low = dirs::data_local_dir()
            .and_then(|p| p.parent().map(|p| p.join("LocalLow")))
            .unwrap_or_else(|| home.join("AppData/LocalLow"));
        candidates.push((
            "Windows · LocalLow",
            low.join("Computer Lunch/Cell to Singularity"),
        ));
    } else if cfg!(target_os = "macos") {
        candidates.push((
            "macOS · Application Support",
            home.join("Library/Application Support/Computer Lunch/Cell to Singularity"),
        ));
        candidates.push((
            "macOS · Unity",
            home.join("Library/Application Support/com.computerlunchllc.cells"),
        ));
    } else {
        let config = std::env::var_os("XDG_CONFIG_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| home.join(".config"));
        candidates.push((
            "Linux · Unity",
            config.join("unity3d/Computer Lunch/Cell to Singularity"),
        ));
        for steam in [
            home.join(".steam/steam"),
            home.join(".local/share/Steam"),
            home.join(".var/app/com.valvesoftware.Steam/.local/share/Steam"),
        ] {
            let users = steam.join("steamapps/compatdata/977400/pfx/drive_c/users");
            if let Ok(items) = std::fs::read_dir(&users) {
                for user in items.flatten() {
                    candidates.push((
                        "Linux · Steam Proton",
                        user.path()
                            .join("AppData/LocalLow/Computer Lunch/Cell to Singularity"),
                    ));
                }
            }
        }
    }
    let mut seen = std::collections::HashSet::new();
    candidates
        .into_iter()
        .filter(|(_, path)| seen.insert(std::fs::canonicalize(path).unwrap_or(path.clone())))
        .map(|(label, dir)| Location {
            label: label.into(),
            path: dir.to_string_lossy().into(),
            files: files::targets(&dir.join("savedGames.gd"))
                .iter()
                .map(|p| file_info(p))
                .collect(),
        })
        .collect()
}

#[tauri::command]
async fn open_save(path: String, app: tauri::AppHandle) -> Result<View, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let mut path = PathBuf::from(path);
        if path.is_dir() {
            path = [
                "savedGames2.gd",
                "savedGames.gd",
                "savegame2.gd",
                "savegame.gd",
                "savegame",
                "savegame2",
            ]
            .iter()
            .map(|name| path.join(name))
            .find(|p| p.is_file())
            .ok_or("No save file found in this folder")?;
        }
        let path = dunce::canonicalize(path).map_err(|e| e.to_string())?;
        let snapshot = files::snapshot(&files::targets(&path))?;
        let data = std::fs::read(&path).map_err(|e| e.to_string())?;
        let editor = Editor::new(data.clone());
        let baseline_entries = editor.parse();
        if baseline_entries.is_empty() {
            return Err(
                "No supported variables found. Select a Cell to Singularity binary save.".into(),
            );
        }
        let session = Session {
            editor,
            baseline: data,
            baseline_entries,
            source: path,
            snapshot,
        };
        let view = session.view();
        *app.state::<AppState>()
            .0
            .lock()
            .map_err(|e| e.to_string())? = Some(session);
        Ok(view)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
fn apply_edit(id: usize, value: String, state: State<AppState>) -> Result<View, String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    let session = guard.as_mut().ok_or("No save open")?;
    session.editor.edit(id, value.trim())?;
    Ok(session.view())
}

#[tauri::command]
fn history_edit(redo: bool, state: State<AppState>) -> Result<View, String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    let session = guard.as_mut().ok_or("No save open")?;
    if redo {
        session.editor.redo();
    } else {
        session.editor.undo();
    }
    Ok(session.view())
}

#[tauri::command]
fn restore_entry(id: usize, state: State<AppState>) -> Result<View, String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    let session = guard.as_mut().ok_or("No save open")?;
    let original = session
        .baseline_entries
        .get(id)
        .ok_or("Variable no longer exists")?;
    let current = session
        .editor
        .parse()
        .into_iter()
        .find(|entry| entry.id == id)
        .ok_or("Variable no longer exists")?;
    session
        .editor
        .restore(&current, &session.baseline[original.start..original.end]);
    Ok(session.view())
}

#[tauri::command]
async fn save_session(path: Option<String>, app: tauri::AppHandle) -> Result<View, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let state = app.state::<AppState>();
        let mut guard = state.0.lock().map_err(|e| e.to_string())?;
        let session = guard.as_mut().ok_or("No save open")?;
        let source = path
            .map(PathBuf::from)
            .unwrap_or_else(|| session.source.clone());
        let source = if source.exists() {
            dunce::canonicalize(source).map_err(|e| e.to_string())?
        } else {
            source
        };
        let targets = files::targets(&source);
        let same_targets = targets
            == session
                .snapshot
                .iter()
                .map(|(p, _)| p.clone())
                .collect::<Vec<_>>();
        let original = if same_targets {
            session.snapshot.clone()
        } else {
            files::snapshot(&targets)?
        };
        let contents = original
            .iter()
            .map(|(path, data)| {
                if (!same_targets || path != &session.source)
                    && let Some(data) = data
                {
                    return session
                        .editor
                        .apply_changes_to(&session.baseline, data)
                        .map_err(|e| format!("{}: {e}", path.display()));
                }
                Ok(session.editor.data.clone())
            })
            .collect::<Result<Vec<_>, String>>()?;
        files::save(&original, &contents)?;
        if let Some(index) = targets.iter().position(|path| path == &source)
            && contents[index] != session.editor.data
        {
            session.editor = Editor::new(contents[index].clone());
        }
        session.source = source;
        session.snapshot = original
            .into_iter()
            .zip(contents)
            .map(|((p, _), data)| (p, Some(data)))
            .collect();
        session.baseline = session.editor.data.clone();
        session.baseline_entries = session.editor.parse();
        Ok(session.view())
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn backup_session(
    directory: Option<String>,
    app: tauri::AppHandle,
) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let state = app.state::<AppState>();
        let guard = state.0.lock().map_err(|e| e.to_string())?;
        let session = guard.as_ref().ok_or("No save open")?;
        let paths = session
            .snapshot
            .iter()
            .map(|(p, _)| p.clone())
            .collect::<Vec<_>>();
        let root = directory.map(PathBuf::from).map(Ok).unwrap_or_else(|| {
            dirs::data_local_dir()
                .map(|p| p.join("CTS Save Editor/backups"))
                .ok_or("Could not find the application data folder")
        })?;
        files::backup(&files::snapshot(&paths)?, &root).map(|p| p.to_string_lossy().into())
    })
    .await
    .map_err(|e| e.to_string())?
}

fn main() {
    tauri::Builder::default()
        .manage(AppState::default())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            discover_saves,
            open_save,
            apply_edit,
            history_edit,
            restore_entry,
            save_session,
            backup_session,
            update::check_update
        ])
        .run(tauri::generate_context!())
        .expect("Failed to start CTS Save Editor");
}
