import ctypes
from dataclasses import dataclass
from pathlib import Path
import sys
import uuid


_FOLDERID_LOCAL_APP_DATA_LOW = bytes.fromhex(
    uuid.UUID("A520A1A4-1780-4FF6-BD18-167343C5AF16").bytes_le.hex()
)


@dataclass(slots=True)
class SaveLocation:
    label: str
    path: Path


def get_local_app_data_low() -> Path | None:
    if sys.platform != "win32":
        return None

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    ole32 = ctypes.OleDLL("ole32")

    raw_guid = (ctypes.c_byte * 16).from_buffer_copy(_FOLDERID_LOCAL_APP_DATA_LOW)
    out_path = ctypes.c_wchar_p()
    result = shell32.SHGetKnownFolderPath(raw_guid, 0, None, ctypes.byref(out_path))
    if result != 0:
        return None
    try:
        raw_path = out_path.value
        if raw_path is None:
            return None
        return Path(raw_path)
    finally:
        ole32.CoTaskMemFree(out_path)


def iter_default_save_locations() -> list[SaveLocation]:
    candidates: list[SaveLocation] = []
    seen: set[Path] = set()

    def add(label: str, path: Path) -> None:
        resolved = path.expanduser()
        if resolved in seen:
            return
        seen.add(resolved)
        candidates.append(SaveLocation(label=label, path=resolved))

    if base := get_local_app_data_low():
        saves_dir = base / "Computer Lunch" / "Cell to Singularity"
        add("LocalLow savedGames2", saves_dir / "savedGames2.gd")
        add("LocalLow savedGames", saves_dir / "savedGames.gd")

    return candidates
