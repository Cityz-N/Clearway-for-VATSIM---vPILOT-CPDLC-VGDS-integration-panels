# Changelog

## 0.5.0

- The Windows companion is now a normal program folder (Clearway.exe + _internal) instead of a single self-extracting exe, and carries proper file details (product, version, description). This avoids most antivirus false positives that the self-extracting format triggered
- Releases now include the all-in-one zip (MSFS panel + companion + vPilot plugin) built automatically

## 0.4.1

- MSFS panel: text fields (notepad, chat, requests) give the keyboard and mouse back to the sim as soon as the mouse leaves the card, on Esc, or when collapsing; previously the sim stayed blocked
- MSFS panel: the idle icon is fainter (12%) and grey; colour comes back on hover
- Nearby ATC: an arrow on each controller expands their information in place (no more double-click; nothing added to the frequency chat)
- Phone instructions now cover Android as well as iPhone (the phone app works on both)
- Phone: VDGS button in the vPilot tab opens the official VDGS page (vats.im/vdgs) for TOBT/TSAT and start-up times
- Fixed: the vPilot tab kept showing 'connected' after vPilot or its plugin had closed

## 0.4.0

- Commands and messages reach vPilot in about 30 ms instead of up to a second (Mode C, standby, ident, chat)
- MSFS panel: COM1/COM2 frequencies read from the sim; the transmit frequency shows on the FREQ tab, hover for both radios (also shown on the phone)
- Purpose labels on CPDLC messages: DCL, CLEARANCE, OCEANIC, LOGON, REQUEST, METAR/TAF/ATIS
- MSFS panel: Enter sends; message boxes grow with long text; hints clear themselves; text 2 px smaller; bigger collapse arrows
- MSFS panel: the floating icon fades when there is nothing to read
- MSFS panel: fixed symbols that showed as boxes in the sim's font (x, ..., arrows)
- Clearance form: 'Aircraft type' label, prefilled from vPilot
- Fixed: v0.3.0 panel card stretched across the screen and wasn't clickable

## 0.3.0

- New layout: **vPilot** tab (left) and **CPDLC** tab (right) on the phone, PC page and MSFS panel
- vPilot tab: frequency chat, private chat tabs, nearby controllers (double-click for info), connect/disconnect, Mode C/standby, ident and vPilot's dot commands
- Unread counters: cyan (#00d8d4) for vPilot on the left, amber for CPDLC on the right, on the tabs and the panel icon
- Notepad, shared between all screens and kept between sessions
- vPilot chat and CPDLC history are limited separately, so busy frequencies never push out CPDLC messages

## 0.2.0

- vPilot plugin: private messages, frequency text that mentions you, broadcasts and SELCAL alerts appear in Clearway, on the phone (with notifications) and in the MSFS panel
- Send private or frequency text messages through vPilot from the phone (Requests → Text message) or the panel (PM)
- Connects to Hoppie automatically when vPilot connects, using vPilot's callsign straight away

## 0.1.1

- MSFS panel: request pre-departure clearance, oceanic clearance and telex (the panel previously only had logon, level, direct, free text and weather)
- Delete single messages (× on each message) in the panel and on the phone; trash button in the panel to clear old messages
- Collapse any message to a single line (chevron), synced between phone and panel
- Restore deleted messages (kept until Clearway quits)

## 0.1.0

First version.

- Windows companion: Hoppie polling (45–75 s, 20 s while waiting for a reply), CPDLC logon, logoff and handover, replies, requests, PDC, oceanic, telex, METAR, TAF and ATIS, automatic ADS-C
- iPhone/desktop web app with pairing QR code
- ntfy phone notifications with quick-reply buttons, optionally muted while the MSFS panel is open
- Runs as a tray icon (no console window); doesn't open the browser on start except the first time
- Dark theme by default, light theme optional (phone, PC and panel)
- MSFS toolbar panel: draggable floating icon, flashes on new messages and stays amber until acknowledged
