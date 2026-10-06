# CTS Save Editor

A desktop save editor for **Cell to Singularity**, written in Rust and Tauri 2.

[简体中文](docs/README-cn.md)

Open a save file or folder, search variables, edit text, booleans or numbers, and save your changes. Categories, descriptions and binary records are carried over from the Python editor. Large numbers keep their floating-point mantissa and 64-bit exponent; values such as `1.25e1000` are supported.

The interface uses a sage green palette, [Lucide](https://lucide.dev/) icons, and light, dark or system appearance. Language, appearance, recent files and the optional startup behavior are remembered.

Undo and redo are available for applied edits. Restore a variable to its last saved value, or review all changed values before saving. Saving keeps the undo history; restoration uses the latest saved version. Text fields retain native undo behavior.

## Saving and backups

- Opening a folder reads `savedGames2.gd` first, falling back to `savedGames.gd`. You can choose either file explicitly.
- Saving either standard file updates **both** `savedGames.gd` and `savedGames2.gd`. A missing companion is created. The `savegame.gd` / `savegame2.gd` and `savegame` / `savegame2.gd` aliases are also recognized.
- If the files differ, the editor shows which file was read. Each original is backed up before both are replaced with the edited version.
- Files changed externally after opening must be reloaded before saving.
- Replacement files are staged first. If a replacement fails, completed replacements are rolled back. An interrupted process or power loss cannot be made atomic across two files; the original backups remain available.
- **Save As** follows the same pairing rules for standard names. Other names export a single file.

Automatic backups are stored under `CTS Save Editor/backups` in the operating system's local application data directory, outside the usual game save directory. **Backup** lets you choose a separate directory. **Show backup** reveals the latest backup; restore it by copying its original files back into the game save directory while the game is closed.

Default locations are detected on Windows and macOS. Linux includes Unity and the standard Steam/Flatpak Proton locations. For another Steam library or a copied save, select the folder manually.

## Development

Install the latest stable Rust and Node.js, and the [Tauri platform prerequisites](https://v2.tauri.app/start/prerequisites/). Windows needs the C++ Build Tools and WebView2; Linux needs GTK and WebKitGTK 4.1. Rust uses edition 2024. Frontend output targets `esnext` and requires a current system WebView.

```sh
npm ci
npm run tauri dev
```

```sh
npm run format        # Prettier + rustfmt
npm run format:check
npm run lint          # Oxlint + Biome CSS lint; warnings fail
npm run check         # TypeScript
cargo clippy --workspace --all-targets --locked -- -D warnings
npm run tauri build
```

`npm run dev` and `npm run preview` display the frontend in a browser. Native file dialogs and save editing require `tauri dev` or the built desktop app. There are no test files or test dependencies.

| Platform            | Build output                                                         |
| ------------------- | -------------------------------------------------------------------- |
| Windows x64         | `.exe` installer; executable in `target/release/cts-save-editor.exe` |
| Linux x64           | Executable in `target/release/cts-save-editor`                       |
| macOS Apple Silicon | `.app` and `.dmg`                                                    |

The GitHub Actions workflow builds all three platforms on push, pull request or manual dispatch and uploads the artifacts. Linux's artifact contains only the executable in a `.tar.gz` to preserve permissions; it needs the system GTK/WebKitGTK libraries. No `.msi`, `.deb`, `.rpm` or AppImage is built. The macOS application is also archived to preserve its executable permissions. Code signing and macOS notarization are not configured.

Dependencies are locked in `package-lock.json` and `Cargo.lock`. Dependabot checks npm, Cargo and Actions weekly.

## Shortcuts

| Shortcut                 | Action                           |
| ------------------------ | -------------------------------- |
| Ctrl / ⌘ + O             | Open a save                      |
| Ctrl / ⌘ + S             | Save                             |
| Ctrl / ⌘ + Shift + S     | Save As                          |
| Ctrl / ⌘ + F             | Search                           |
| Ctrl / ⌘ + Z             | Undo                             |
| Ctrl / ⌘ + Shift + Z / Y | Redo                             |
| F5                       | Reload                           |
| Enter                    | Apply a numeric or boolean input |
| Ctrl / ⌘ + Enter         | Apply a text input               |
| ↑ / ↓                    | Select a variable in the table   |

## Update source

The original update JSON endpoint is retained. Set `CTS_UPDATE_JSON_URL` to another endpoint or to an empty value to disable update checks. Requests time out after six seconds. Invalid, unavailable or older versions are ignored.

```json
{
  "version": "0.4.0",
  "title": "CTS Save Editor 0.4.0",
  "download_url": "https://github.com/Wulian233/CTS-Save-Editor/releases/latest",
  "changelog": { "zh-CN": "更新说明", "en-US": "Release notes" }
}
```

## Source layout

`crates/save-core` contains parsing, numeric conversion, categorization and file saving. `src-tauri` provides desktop commands, save discovery and update checks. `src` contains the TypeScript interface, theme, translations and CSS. Save data is processed locally.

This rewrite lives on the independent `rewrite/tauri` branch. The Python editor remains on `master`.
