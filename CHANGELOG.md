# Changelog

## 0.9.1

- MSFS panel: fixed the card sometimes opening partly off screen (mostly with the icon near the bottom or top edge) until the icon was moved. The card now keeps itself on screen whenever its content or the window changes size

## 0.9.0

- MSFS panel: while you type in a panel text field, the keys no longer reach MSFS key bindings or other programs such as ChasePlane, so typing doesn't move the camera or trigger sim commands. Clearway holds the keyboard and types into the panel itself. Controllers keep working, and function keys, Alt+Tab and the Windows key work as usual
- The keyboard goes back to the sim on Esc, a click outside the panel, 15 seconds without typing, or if the panel stops answering
- Text editing in the panel: arrows (Up/Down move between lines in the notepad), Home/End, Shift to select, Ctrl+A, Ctrl+V (paste from Windows), Ctrl+Backspace, accents and dead keys follow your keyboard layout
- New setting to switch this off (Options: "MSFS panel: keep typed keys away from the sim and other programs")

## 0.8.0

- vPilot: "Connect as observer" tickbox in the connect form (panel and phone). An observer only needs a callsign; Clearway shows "(observer)" and greys out the transponder buttons
- vPilot: an observer connection now counts as connected (it used to show "vPilot offline"), and doesn't start the automatic Hoppie connection
- MSFS panel: clicking anywhere outside the panel (cockpit, scenery, another window) now takes the cursor out of the notepad and message boxes straight away. The click still reaches the sim as normal
- vPilot plugin 0.5.0 (needed for observer mode: copy the new Clearway.vPilot.dll into vPilot's Plugins folder)

## 0.7.0

- MSFS panel: right click the icon to peek at the latest unread message in a small window, which marks it as read (vPilot messages first, then CPDLC). Right click again for the next one
- MSFS panel: right clicking when everything is read marks the latest received message as unread again
- MSFS panel: click the peek window to open the card on that message
- MSFS panel: CPDLC messages that need an answer show their reply buttons (WILCO, UNABLE, STANDBY...) right in the peek window
- MSFS panel: the peek window stays open while the mouse is over it, and closes 3 seconds after the mouse leaves

## 0.6.2

- The "Got it" button is replaced by a small tick next to the time: click it to mark a message as read (panel and phone)

## 0.6.1

- MSFS panel: text fields no longer take the keyboard away from MSFS, so controllers (yoke, joystick, throttle...) always keep working while you type. Keys bound to sim commands also reach the sim while typing
- MSFS panel: a text field gives up its cursor after 15 seconds without typing (and on Esc), so later sim key presses can't end up in a forgotten message box
- MSFS panel: the TYPING badge is removed (keys no longer go only to Clearway)

## 0.6.0

- MSFS panel: the card opens towards the middle of the screen vertically too (bottom-left icon: card opens up and to the right; bottom-right: up and to the left)
- MSFS panel: padlock button next to the notepad locks the direction the card opens
- MSFS panel: clock in the top bar - UTC by default; click to switch to sim time and local time (each in its own colour)
- Accented letters (é, à, ç, ü...) now display correctly in received messages: Clearway reads both UTF-8 and Western-European text from Hoppie and repairs the classic "Ã©" mix-up in vPilot messages. Messages to Hoppie are sent in the same Western-European encoding
- MSFS panel: a text field keeps the keyboard while its cursor blinks, even when the mouse moves away. It is released by a click elsewhere (the panel losing focus), Esc, collapsing the card or switching tabs. A TYPING badge shows while the keyboard goes to Clearway (click it to release). Controllers are not affected
- MSFS panel: the cursor stays in the message box after Send

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
