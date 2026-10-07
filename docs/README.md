# Cell to Singularity Save Editor

A **Cell to Singularity save editor** for viewing, filtering, editing, backing up, and writing back game save variables.

English | [Simplified Chinese](./README-cn.md)

![Screenshot](./screenshot-cn.png)

## ✨ Features

- 📂 Automatically locates and opens the save directory, providing quick access
- 🧩 Supports filtering by keyword, source, and category
- 📚 Built-in common variable categories and descriptions
- 🛠️ Inspector on the right supports variable viewing and editing
- 💾 Supports overwrite save, save as, and manual backup
- 🌐 Multi-language support (Simplified Chinese / English)
- 🔄 Automatic update detection

## ⚠️ IMPORTANT

> **Be sure to back up** before editing saves.
>
> You can use the "Backup" button to manually create a backup. It is recommended to store backup files outside the game save directory to avoid accidental overwriting or corruption.

## 🔄 Update Configuration

You can customize the update source via an environment variable:

```powershell
$env:CTS_UPDATE_JSON_URL="http://cdn.maxing.site/update/app/cts_save_editor.json"
```

## 📄 Update JSON Format

The update endpoint needs to return the following structure:

```json
{
  "version": "0.1.0",
  "title": "CTS Save Editor 0.1.0",
  "download_url": "https://github.com/Wulian233/CTS-Save-Editor/releases/latest",
  "changelog": {
    "zh-CN": "- 初次发布",
    "en-US": "- Initial release"
  }
}
```
