# Clearway

**CPDLC and vPilot for VATSIM on your phone and inside Microsoft Flight Simulator.** Free, no accounts, no Mac needed.

Clearway is a small companion program for Windows that connects to the [Hoppie ACARS](https://www.hoppie.nl/acars/) network. It lets you read and answer CPDLC messages from:

- 📱 **your phone** (iPhone or Android): a clean web app on your home screen, plus lock-screen notifications through the free [ntfy](https://ntfy.sh) app
- ✈️ **an in-game MSFS toolbar panel**: a small floating icon you can put anywhere on screen. It flashes when a message arrives and stays amber until you answer.

You can use both at the same time; they stay in sync.

<p align="center">
  <img src="docs/phones.png" width="640" alt="Clearway on a phone: vPilot tab and CPDLC tab">
</p>
<p align="center">
  <img src="docs/panel-vpilot.png" width="400" alt="MSFS panel, vPilot tab">
  &nbsp;
  <img src="docs/panel-cpdlc.png" width="400" alt="MSFS panel, CPDLC tab">
</p>

## Features

- CPDLC logon and logoff, automatic handover to the next station
- One-tap answers: **WILCO / UNABLE / STANDBY**, **AFFIRM / NEGATIVE**, **ROGER**, or free text
- Requests: level, direct to, speed, "when can we expect…", free text
- Pre-departure clearance (PDC/DCL), oceanic clearance request and telex, from the phone and the MSFS panel
- METAR, TAF and VATSIM ATIS lookups
- Automatic ADS-C position reports, using the sim's position when the panel is open and VATSIM data otherwise
- Phone notifications with quick-reply buttons
- Optionally mutes phone notifications while the MSFS panel is open
- Callsign and flight plan read automatically from VATSIM using your CID
- Collapse messages to one line, delete them, and restore deleted ones (until Clearway quits)
- Dark theme by default, with a light theme in Settings that also applies to the MSFS panel
- Runs quietly as a tray icon with no console window
- **vPilot tab** (with the vPilot plugin): frequency chat plus one tab per private chat, nearby controllers (tap the arrow for their information), connect/disconnect, Mode C/standby, ident, and vPilot's dot commands. Clearway also connects to Hoppie automatically as soon as vPilot connects.
- Two tabs everywhere: **vPilot** on the left, **CPDLC** on the right. Unread counters are cyan for vPilot and amber for CPDLC, on the tabs and on the panel's floating icon.
- Notepad shared between the phone, the PC page and the MSFS panel
- VDGS shortcut on the phone: opens the official VDGS page ([vats.im/vdgs](https://vats.im/vdgs)) for your TOBT, TSAT and start-up window

## How it works

```
 Hoppie ACARS  ◄──►  Clearway (your PC)  ◄──►  MSFS panel  (localhost)
                         │      ▲
                         │      └──────────►  phone web app (home Wi-Fi) 
                         └──► ntfy.sh ─────►  phone lock-screen notifications
```

Only the companion talks to Hoppie, so the phone and the panel never compete for messages. Your Hoppie logon code stays on your PC. Notifications contain only the message text.

## Setup

### 1. The companion (Windows)

1. Download **`Clearway-for-VATSIM-<version>.zip`** from the [Releases](../../releases) page and extract it into your MSFS **Community** folder. Then run `Clearway companion\Clearway.exe` inside it (keep the `_internal` folder next to it). Not using MSFS? Download `Clearway-companion.zip` instead and extract it anywhere. There is no window: Clearway runs as an icon in the notification area next to the clock. **Double-click** the icon to open it; **right-click** it to connect, disconnect or quit. Keep it running while you fly.
2. Windows Firewall will ask about network access. Allow **Private networks**, so your phone can reach it.
3. The first time, your browser opens on `http://localhost:8787` (later, double-click the tray icon). Go to **Settings** and enter:
   - your **Hoppie logon code** (get one free at [hoppie.nl/acars](https://www.hoppie.nl/acars/system/register.html))
   - your **VATSIM CID**
4. Connect to VATSIM with your pilot client, then press **Connect**.

### 2. Your phone (iPhone or Android)

1. Make sure the phone is on the same Wi-Fi as the PC.
2. In Clearway on the PC, open **Settings** and scan the **Pair your phone** QR code with the phone's camera.
3. Add the page to your home screen: on iPhone, Safari **Share → Add to Home Screen**; on Android, Chrome **⋮ → Add to Home screen**.
4. For notifications, install **ntfy** from the App Store or Google Play (free, no account). Tap **+** and subscribe to the topic shown in Clearway's Settings. Press **Send test** to check.

> Notifications arrive anywhere, but replying from the phone needs your home Wi-Fi.

### 4. The vPilot plugin (optional)

1. Download `clearway-vpilot-plugin.zip` from the Releases page.
2. Copy `Clearway.vPilot.dll` into vPilot's `Plugins` folder (for example `C:\vPilot\Plugins`).
3. Restart vPilot. Its message window shows "Clearway plugin loaded".

The **vPilot** tab (phone, PC page and MSFS panel) now works like vPilot's own window:

- **Frequency** chat with everything on frequency (messages that mention you are highlighted and alert you), controller info (ATIS), METARs, broadcasts and SELCAL alerts
- one tab per **private chat**; close a tab with × or `.close`
- **Nearby ATC** with frequencies and distance; the arrow next to a controller shows their information
- **Connect / Disconnect**, **Standby / Mode C** and **Ident**
- dot commands: `.chat` `.msg` `.close` `.atis` `.wx` `.metar` `.wallop` `.clear` `.copy`, plus `.modec` `.standby` `.ident` `.connect` `.disconnect` and `.help`

vPilot doesn't let plugins set the squawk code or tune radios, so `.x`/`.squawk`, `.com1`, `.com2`, `.com`, `.ctaf`, `.towerview`, `.aircraft`, `.debug`, `.reloadrules` and `.ignore` still need vPilot's own window. Clearway tells you when you type one.

### 3. The MSFS panel (optional)

1. Download `clearway-panel.zip` from the Releases page.
2. Unzip it into your MSFS **Community** folder.
3. In the sim, click the Clearway icon in the toolbar. A small round icon appears:
   - **click** it to open or collapse the message card
   - **drag** it anywhere on screen (the position is remembered)
   - it **flashes** when a message arrives and **stays amber** until you answer or acknowledge it

The panel is a transparent full-screen layer, and only the icon and card catch the mouse. It's designed for 16:9 screens (1080p, 1440p, 4K).

## Using it

1. In **Requests → ATC logon**, enter the station (e.g. `EGGX`, `CZQX`, `KZNY`) and press **Log on**.
2. Messages from ATC appear with answer buttons. Answer from the phone, the panel, or straight from the notification.
3. Tap a message without answer options to acknowledge it.

## Building from source

The companion needs Python 3.11+ with only the standard library. To run it:

```bash
cd companion
python clearway_app.py
```

Or double-click `companion/Clearway.pyw` to run it from source with only the tray icon, no console window.

To test without the real network, run against a fake Hoppie server:

```bash
python tools/dev_run.py
```

To build the Windows app (`dist/Clearway/`, an exe with its support folder):

```bash
pip install pyinstaller==6.11.1
python tools/build_exe.py
```

For the MSFS panel you need the free MSFS SDK. The SDK's package tool briefly starts the sim to compile the panel:

```bash
python tools/build_panel.py --install
```

The compiled panel definition is cached in `msfs-panel/compiled/`. Commit it, so GitHub Actions can package releases without the SDK.

The vPilot plugin is a small C# library for .NET Framework 4.7.2. It builds against the plugin interface that ships with vPilot, which is not redistributed here:

```bash
cd vpilot-plugin
dotnet build -c Release
```

Copy the result to `vpilot-plugin/compiled/` and commit it, so releases can include it.

Releases are built by GitHub Actions when you push a tag such as `v0.1.0`.

For sites like flightsim.to, `python tools/make_release_zip.py` builds one all-in-one zip: a `clearway-panel` folder for the Community folder, with `Clearway companion\` (the exe, the vPilot plugin and a quick-start guide) inside it.

## Project layout

```
companion/            Python companion (no third-party packages)
  clearway/           Hoppie client, CPDLC session, ntfy, web server
  web/                phone and desktop web app
msfs-panel/           MSFS toolbar panel package sources
vpilot-plugin/        vPilot plugin (C#) that bridges vPilot and Clearway
tools/                build scripts, icon generator, mock Hoppie server
```

## Credits

- Inspired by [EasyCPDLC](https://github.com/quassbutreally/EasyCPDLC) by Joshua Seagrave. Clearway is an independent implementation and contains no EasyCPDLC code.
- [Hoppie's ACARS](https://www.hoppie.nl/acars/) by Jeroen Hoppenbrouwers makes all of this possible.
- QR codes by [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) (MIT).

Clearway is not affiliated with Hoppie, VATSIM, vPilot, ntfy or Microsoft. It's for flight simulation only.

## License

[MIT](LICENSE)
