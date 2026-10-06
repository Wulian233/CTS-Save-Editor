use std::{
    fs,
    io::Write,
    path::{Path, PathBuf},
};
use tempfile::NamedTempFile;

pub type Snapshot = Vec<(PathBuf, Option<Vec<u8>>)>;

pub fn targets(path: &Path) -> Vec<PathBuf> {
    let parent = path.parent().unwrap_or(Path::new("."));
    let name = path
        .file_name()
        .unwrap_or_default()
        .to_string_lossy()
        .to_lowercase();
    let pair = match name.as_str() {
        "savedgames.gd" | "savedgames2.gd" => Some(("savedGames.gd", "savedGames2.gd")),
        "savegame.gd" => Some(("savegame.gd", "savegame2.gd")),
        "savegame2.gd" => {
            let primary = if !existing_name(parent, "savegame.gd").is_file()
                && existing_name(parent, "savegame").is_file()
            {
                "savegame"
            } else {
                "savegame.gd"
            };
            Some((primary, "savegame2.gd"))
        }
        "savegame" => Some(("savegame", "savegame2.gd")),
        "savegame2" => Some(("savegame", "savegame2")),
        _ => None,
    };
    pair.map(|(a, b)| vec![existing_name(parent, a), existing_name(parent, b)])
        .unwrap_or_else(|| vec![path.to_path_buf()])
}

fn existing_name(parent: &Path, name: &str) -> PathBuf {
    fs::read_dir(parent)
        .ok()
        .into_iter()
        .flatten()
        .filter_map(Result::ok)
        .find(|e| e.file_name().to_string_lossy().eq_ignore_ascii_case(name))
        .map(|e| e.path())
        .unwrap_or_else(|| parent.join(name))
}

pub fn snapshot(paths: &[PathBuf]) -> Result<Snapshot, String> {
    paths
        .iter()
        .map(|path| {
            if fs::symlink_metadata(path).is_ok_and(|m| m.file_type().is_symlink()) {
                return Err(format!(
                    "Refusing to overwrite a symbolic link: {}",
                    path.display()
                ));
            }
            let data = match fs::read(path) {
                Ok(data) => Some(data),
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => None,
                Err(e) => return Err(format!("{}: {e}", path.display())),
            };
            Ok((path.clone(), data))
        })
        .collect()
}

pub fn backup(original: &Snapshot, root: &Path) -> Result<PathBuf, String> {
    fs::create_dir_all(root).map_err(|e| e.to_string())?;
    let dir = tempfile::Builder::new()
        .prefix("cts-backup-")
        .tempdir_in(root)
        .map_err(|e| e.to_string())?;
    for (path, data) in original {
        if let Some(data) = data {
            let target = dir.path().join(path.file_name().ok_or("Invalid filename")?);
            let mut file = fs::File::create(target).map_err(|e| e.to_string())?;
            file.write_all(data)
                .and_then(|()| file.sync_all())
                .map_err(|e| e.to_string())?;
        }
    }
    Ok(dir.keep())
}

fn stage(path: &Path, data: &[u8]) -> Result<NamedTempFile, String> {
    let parent = path.parent().ok_or("Invalid target directory")?;
    fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    let mut temp = NamedTempFile::new_in(parent).map_err(|e| e.to_string())?;
    temp.write_all(data)
        .and_then(|()| temp.as_file().sync_all())
        .map_err(|e| e.to_string())?;
    if let Ok(metadata) = fs::metadata(path) {
        temp.as_file()
            .set_permissions(metadata.permissions())
            .map_err(|e| e.to_string())?;
    }
    Ok(temp)
}

pub fn save(
    original: &Snapshot,
    contents: &[Vec<u8>],
    backup_root: &Path,
) -> Result<PathBuf, String> {
    if original.len() != contents.len() {
        return Err("Save file count does not match output count".into());
    }
    let paths: Vec<_> = original.iter().map(|(p, _)| p.clone()).collect();
    if &snapshot(&paths)? != original {
        return Err(
            "Save files changed on disk. Reload before saving to avoid overwriting game progress."
                .into(),
        );
    }
    let mut staged = Vec::new();
    for ((path, _), data) in original.iter().zip(contents) {
        staged.push(stage(path, data)?);
    }
    let backup_path = backup(original, backup_root)?;
    for (i, ((path, _), temp)) in original.iter().zip(staged).enumerate() {
        if let Err(error) = temp.persist(path) {
            let mut failures = Vec::new();
            for (target, before) in original.iter().take(i) {
                let result = match before {
                    Some(bytes) => stage(target, bytes)
                        .and_then(|t| t.persist(target).map(|_| ()).map_err(|e| e.to_string())),
                    None => fs::remove_file(target).map_err(|e| e.to_string()),
                };
                if let Err(e) = result {
                    failures.push(format!("{}: {e}", target.display()));
                }
            }
            return Err(format!(
                "Save failed: {error}. Backup: {}. Rollback errors: {}",
                backup_path.display(),
                failures.join("; ")
            ));
        }
    }
    Ok(backup_path)
}
