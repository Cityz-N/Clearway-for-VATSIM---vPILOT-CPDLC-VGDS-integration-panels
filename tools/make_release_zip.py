"""Build the all-in-one download for flightsim.to (or any site): one folder that goes into
the MSFS Community folder, with the companion app and vPilot plugin inside it.

    Clearway-for-VATSIM-v<version>.zip
    └── clearway-panel/                     <- extract into the Community folder
        ├── layout.json, manifest.json, html_ui/, InGamePanels/   (the MSFS panel)
        └── Clearway companion/
            ├── Clearway.exe                 <- run this on your PC
            ├── _internal/                   (support files, keep next to the exe)
            ├── vPilot plugin/Clearway.vPilot.dll
            └── READ ME FIRST.txt

MSFS only loads the files listed in layout.json, so the companion folder doesn't affect the sim.

Usage:  python tools/make_release_zip.py
Needs:  dist/Clearway/ (python tools/build_exe.py), msfs-panel/compiled/clearway-panel.spb,
        vpilot-plugin/compiled/Clearway.vPilot.dll
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
VERSION = re.search(r'__version__ = "([^"]+)"', (ROOT / "companion" / "clearway" / "__init__.py").read_text()).group(1)

README = f"""CLEARWAY FOR VATSIM  {VERSION}
CPDLC (Hoppie) and vPilot on your phone (iPhone or Android) and in an MSFS toolbar panel. Free, no accounts.
Full guide, source code and updates: https://github.com/Cityz-N/Clearway-for-VATSIM---vPILOT-and-CPDLC-RADAR-integration-for-MSFS

QUICK START
1. You already did step 1 if you're reading this inside your Community folder:
   the "clearway-panel" folder goes into the MSFS Community folder.

2. Start the companion: double-click "Clearway.exe" in this folder
   (keep the "_internal" folder next to it; Clearway needs it).
   - There's no window: Clearway runs as an icon next to the clock.
     Double-click it to open Clearway, right-click it to connect or quit.
   - Windows SmartScreen may warn because the app isn't signed:
     click "More info" > "Run anyway".
   - Windows Firewall will ask about network access: allow "Private networks"
     (needed for your phone).
   - The first time, your browser opens Clearway's Settings. Enter your Hoppie
     logon code (free at https://www.hoppie.nl/acars/system/register.html) and
     your VATSIM CID.
   Tip: create a desktop shortcut to Clearway.exe.

3. vPilot plugin (optional, for the vPilot tab):
   close vPilot, copy "vPilot plugin\\Clearway.vPilot.dll" into vPilot's
   "Plugins" folder (for example C:\\vPilot\\Plugins), then start vPilot again.

4. In MSFS, click the Clearway icon in the toolbar. A small round icon appears:
   click it to open the card, drag it anywhere on screen.

5. Phone (optional, iPhone or Android): the phone must be on the same Wi-Fi as the PC.
   In Clearway's Settings, scan the "Pair your phone" QR code with the phone's camera,
   then add the page to your home screen:
     - iPhone: Safari > Share > Add to Home Screen
     - Android: Chrome > menu (three dots) > Add to Home screen
   For lock-screen notifications, install the free "ntfy" app (App Store or Google Play)
   and subscribe to the topic shown in Settings; these work even away from home.
   If the phone can't connect: allow Clearway on "Private networks" in Windows Firewall,
   make sure your Windows network is set to Private, and avoid guest Wi-Fi networks.

Clearway is not affiliated with Hoppie, VATSIM, vPilot, ntfy or Microsoft.
For flight simulation only. MIT License.
"""


def main() -> None:
    app = DIST / "Clearway"
    dll = ROOT / "vpilot-plugin" / "compiled" / "Clearway.vPilot.dll"
    for needed in (app / "Clearway.exe", dll, ROOT / "msfs-panel" / "compiled" / "clearway-panel.spb"):
        if not needed.exists():
            sys.exit(f"Missing {needed}. Build it first (see README).")

    # fresh copy of the MSFS package
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_panel.py"), "--assemble"], check=True)

    stage = DIST / "release" / "clearway-panel"
    if stage.parent.exists():
        shutil.rmtree(stage.parent)
    shutil.copytree(DIST / "clearway-panel", stage)
    comp = stage / "Clearway companion"
    shutil.copytree(app, comp)                       # Clearway.exe + _internal/
    (comp / "vPilot plugin").mkdir(parents=True)
    shutil.copy2(dll, comp / "vPilot plugin" / "Clearway.vPilot.dll")
    (comp / "READ ME FIRST.txt").write_text(README.replace("\n", "\r\n"), encoding="utf-8")
    shutil.copy2(ROOT / "LICENSE", comp / "LICENSE.txt")

    out = DIST / f"Clearway-for-VATSIM-v{VERSION}.zip"
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(stage.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(stage.parent).as_posix())
    print(f"Created {out}  ({out.stat().st_size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
