# 细胞到奇点存档编辑器

使用 Rust + Tauri 2 重写的桌面存档编辑器，支持 Windows、Linux 和 macOS Apple Silicon。

[English](../README.md)

支持打开、搜索、分类筛选、编辑、保存、另存为和备份。原版的二进制解析、变量分类、说明和中英文翻译已迁移。数值保留浮点尾数和 64 位指数，支持 `1.25e1000` 这样的科学计数法。

界面使用鼠尾草绿配色和 [Lucide](https://lucide.dev/) 图标。外观可选浅色、暗色或跟随系统，语言、外观、最近打开的文件和启动设置会自动保存。

## 打开和保存

1. 选择存档文件夹，或单独打开文件。打开文件夹时优先读取 `savedGames2.gd`，不存在时读取 `savedGames.gd`。
2. 按变量名、值、分类或说明搜索，选择变量后输入新值并应用修改。可以撤销、重做，或恢复上次保存时的原值。
3. 点击“查看修改”对照原值和当前值，确认需要保存的变量。
4. 点击保存，同时更新 `savedGames.gd` 和 `savedGames2.gd`。缺少的配对文件会自动创建。

保存会先分别备份原文件，再按变量名和类型将修改同步到每份存档。每份存档未修改的变量和其他字节各自保留，不会用其中一份的完整内容覆盖另一份。

配对存档缺少已修改变量或同名变量数量不同，保存会停止并显示变量名。缺少整个配对文件时，才会创建完整副本。另存为遇到已有文件也只应用本次修改；新文件则导出完整存档。

同时支持 `savegame.gd` / `savegame2.gd` 和 `savegame` / `savegame2.gd` 命名。另存为标准文件名也会保存配对文件；使用其他文件名则导出单个文件。

存档被游戏或其他程序修改后，需要重新加载才能保存。写入前会准备临时文件；写入失败会回滚已经替换的文件。两个文件无法保证在程序被强制终止或断电时同时完成，原文件备份可用于恢复。

## 备份

每次保存前，自动将原文件备份到系统本地应用数据目录下的 `CTS Save Editor/backups`，通常位于游戏存档目录之外。手动备份可以选择其他目录。

点击“查看备份”定位最近一次备份。恢复时先关闭游戏，再把备份中的原文件复制回游戏存档目录。

默认位置检测覆盖 Windows、macOS，以及 Linux 的 Unity、标准 Steam 和 Flatpak Proton 目录。其他 Steam 库或复制出来的存档可手动选择文件夹。

## 开发和构建

安装最新稳定版 Rust、Node.js 和 [Tauri 系统依赖](https://v2.tauri.app/start/prerequisites/)。Windows 需要 C++ Build Tools 和 WebView2，Linux 需要 GTK 和 WebKitGTK 4.1。Rust 使用 2024 edition，前端构建目标为 `esnext`，需要较新的系统 WebView。

```sh
npm ci
npm run tauri dev
```

```sh
npm run format
npx prettier --check .
cargo fmt --all -- --check
npx oxlint --deny-warnings src vite.config.ts
npx biome lint src/style.css --error-on-warnings
npm run check
cargo clippy --workspace --all-targets --locked -- -D warnings
npm run tauri build
```

Prettier 格式化前端代码，rustfmt 格式化 Rust；Oxlint 和 Biome 检查 TypeScript 与 CSS。检查遇到警告会失败。项目没有测试文件和测试依赖。

`npm run dev` 可在浏览器中查看前端。文件操作需要桌面程序或 `tauri dev`。

| 平台                | 产物                     |
| ------------------- | ------------------------ |
| Windows x64         | `.exe` 安装程序          |
| Linux x64           | 可执行文件，不生成安装包 |
| macOS Apple Silicon | `.app` 和 `.dmg`         |

GitHub Actions 在推送、PR 和手动触发时构建并上传构件。Linux 构件用 `.tar.gz` 保留可执行权限，压缩包内仅有可执行文件；运行时需要系统 GTK/WebKitGTK 库。不构建 MSI、DEB、RPM 或 AppImage。macOS 同时提供保留权限的 `.app` 压缩包，暂未配置签名和公证。

依赖版本由 `package-lock.json` 和 `Cargo.lock` 锁定，Dependabot 每周检查更新。

## 快捷键

| 快捷键                   | 操作               |
| ------------------------ | ------------------ |
| Ctrl / ⌘ + O             | 打开               |
| Ctrl / ⌘ + S             | 保存               |
| Ctrl / ⌘ + Shift + S     | 另存为             |
| Ctrl / ⌘ + F             | 搜索               |
| Ctrl / ⌘ + Z             | 撤销               |
| Ctrl / ⌘ + Shift + Z / Y | 重做               |
| F5                       | 重新加载           |
| Enter                    | 应用数值或布尔修改 |
| Ctrl / ⌘ + Enter         | 应用文本修改       |
| ↑ / ↓                    | 在表格中选择变量   |

输入框内的撤销和重做由系统处理。保存后仍可撤销之前的编辑；“恢复保存时的值”以最近一次保存为准。

## 更新检测

保留原版更新接口。通过 `CTS_UPDATE_JSON_URL` 指定其他接口，设为空值可关闭更新检测。请求超时为六秒；网络错误、无效数据和旧版本不影响启动。JSON 示例见英文 README。

重写位于独立的 `rewrite/tauri` 分支，Python 版本保留在 `master`。
