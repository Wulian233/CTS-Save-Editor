import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SYSTEM = platform.system()

NAME = "CTS-Save-Editor"
ENTRYPOINT = ROOT / "main.py"

WORK_PATH = ROOT / "build" / "pyinstaller" / "work"
SPEC_PATH = ROOT / "build" / "pyinstaller" / "spec"

ICON_DIR = ROOT / "cts" / "icon"
ICON_PATH = ICON_DIR / ("icon.icns" if SYSTEM == "Darwin" else "icon.ico")
LOCALES_PATH = ROOT / "cts" / "locales"

EXCLUDED_MODULES = ("idlelib", "unittest", "test", "pydoc")


def main(extra_args: list[str] | None = None) -> int:
    ensure_pyinstaller()

    reset_dirs(WORK_PATH, SPEC_PATH)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--optimize",
        "2",
        "--name",
        NAME,
        "--workpath",
        str(WORK_PATH),
        "--specpath",
        str(SPEC_PATH),
        *([] if SYSTEM == "Darwin" else ["--onefile"]),
        *optional_icon(),
        *data_args(),
        *exclude_args(),
        *([] if SYSTEM == "Windows" else ["--strip"]),
        *upx_args(),
        *(extra_args or []),
        str(ENTRYPOINT),
    ]

    print("Command:", " ".join(command))
    return subprocess.run(command).returncode


def reset_dirs(*paths: Path) -> None:
    for path in paths:
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)


def optional_icon() -> list[str]:
    return ["--icon", str(ICON_PATH)] if ICON_PATH.exists() else []


def data_args() -> list[str]:
    items = [
        (ICON_DIR / "icon.png", Path("cts/icon/icon.png")),
        (ICON_DIR / "icon.ico", Path("cts/icon/icon.ico")),
        (ICON_DIR / "icon.icns", Path("cts/icon/icon.icns")),
        (LOCALES_PATH, Path("cts/locales")),
    ]

    args = []
    for source, target in items:
        if source.exists():
            args.extend(["--add-data", data_arg(source, target)])

    return args


def data_arg(source: Path, target: Path) -> str:
    separator = ";" if SYSTEM == "Windows" else ":"
    return f"{source}{separator}{target}"


def exclude_args() -> list[str]:
    return [arg for module in EXCLUDED_MODULES for arg in ("--exclude-module", module)]


def upx_args() -> list[str]:
    upx_dir = os.environ.get("UPX_DIR")

    if SYSTEM == "Windows" and upx_dir:
        return ["--upx-dir", upx_dir]

    return []


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        raise SystemExit("PyInstaller 未安装，请先安装")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
