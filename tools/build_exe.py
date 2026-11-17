"""Build the Clearway companion for Windows with PyInstaller.

Produces dist/Clearway/ : Clearway.exe plus a support folder (_internal).
A folder build ("onedir") is used instead of a single self-extracting exe, and the exe carries
proper file details (product, version, description). Both make antivirus heuristics far less
likely to flag the app; self-extracting, detail-less executables are what they distrust.

Usage:  pip install pyinstaller==6.11.1
        python tools/build_exe.py
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPANION = ROOT / "companion"
BUILD = ROOT / "build" / "pyinstaller"
DIST = ROOT / "dist"
VERSION = re.search(r'__version__ = "([^"]+)"', (COMPANION / "clearway" / "__init__.py").read_text()).group(1)


def version_tuple(v: str) -> tuple[int, int, int, int]:
    parts = [int(p) for p in re.findall(r"\d+", v)][:4]
    return tuple(parts + [0] * (4 - len(parts)))  # type: ignore[return-value]


def write_version_file(path: Path) -> None:
    t = version_tuple(VERSION)
    path.write_text(f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Clearway contributors'),
      StringStruct('FileDescription', 'Clearway - CPDLC and vPilot companion for VATSIM'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', 'Clearway'),
      StringStruct('LegalCopyright', 'MIT License - https://github.com/Cityz-N/Clearway-for-VATSIM---vPILOT-and-CPDLC-RADAR-integration-for-MSFS'),
      StringStruct('OriginalFilename', 'Clearway.exe'),
      StringStruct('ProductName', 'Clearway for VATSIM'),
      StringStruct('ProductVersion', '{VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""", encoding="utf-8")


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    version_file = BUILD / "version_info.txt"
    write_version_file(version_file)
    out = DIST / "Clearway"
    if out.exists():
        shutil.rmtree(out)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",                      # no self-extracting single file
        "--noupx",                       # never compress the binaries (another antivirus trigger)
        "--noconsole",
        "--noconfirm",
        "--clean",
        "--name", "Clearway",
        "--icon", str(COMPANION / "web" / "clearway.ico"),
        "--version-file", str(version_file),
        "--add-data", f"{COMPANION / 'web'};web",
        "--distpath", str(DIST),
        "--workpath", str(BUILD / "work"),
        "--specpath", str(BUILD),
        "--log-level", "WARN",
        str(COMPANION / "clearway_app.py"),
    ]
    subprocess.run(cmd, check=True, cwd=COMPANION)
    print(f"Built {out / 'Clearway.exe'} (version {VERSION})")


if __name__ == "__main__":
    main()
