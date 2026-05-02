import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
ENTRYPOINT = ROOT_DIR / "main.py"

NAME = "CTS-Save-Editor"
WORK_PATH = ROOT_DIR / "build" / "pyinstaller" / "work"
SPEC_PATH = ROOT_DIR / "build" / "pyinstaller" / "spec"
ICON_PATH = ROOT_DIR / "cts" / "icon.ico"
LOCALES_PATH = ROOT_DIR / "cts" / "locales"
UPX_DIR = Path(os.environ["UPX_DIR"]) if "UPX_DIR" in os.environ else None
CLEAN = True

EXCLUDED_MODULES = [
    "idlelib",
]


def main(extra_args=None) -> int:
    ensure_pyinstaller()

    if CLEAN:
        for path in (WORK_PATH, SPEC_PATH):
            shutil.rmtree(path, ignore_errors=True)
            Path(path).mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--optimize",
        "2",
        "--name",
        NAME,
        "--icon",
        str(ICON_PATH),
        "--add-data",
        _data_arg(ICON_PATH, Path("cts") / "icon.ico"),
        "--add-data",
        _data_arg(LOCALES_PATH, Path("cts") / "locales"),
        "--workpath",
        str(WORK_PATH),
        "--specpath",
        str(SPEC_PATH),
        str(ENTRYPOINT),
    ]

    for module in EXCLUDED_MODULES:
        command.extend(["--exclude-module", module])

    if platform.system() != "Windows":
        command.append("--strip")

    if UPX_DIR:
        command.extend(["--upx-dir", str(UPX_DIR)])

    if extra_args:
        command[3:3] = extra_args

    print("Command:", " ".join(command))

    return subprocess.run(command).returncode


def _data_arg(source: Path, target: Path) -> str:
    separator = ";" if platform.system() == "Windows" else ":"
    return f"{source}{separator}{target}"


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        raise SystemExit("PyInstaller 未安装，请先安装")


if __name__ == "__main__":
    extra = sys.argv[1:]
    raise SystemExit(main(extra))
