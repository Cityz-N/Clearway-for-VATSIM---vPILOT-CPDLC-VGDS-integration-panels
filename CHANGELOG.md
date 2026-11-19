# Changelog

## 1.1.0

- New **TSAT clock** in the MSFS panel. After you submit your TOBT on the VDGS website (vats.im/vdgs), Clearway reads your start-up time from the vIFF / CDM network and the clock becomes a countdown: yellow while it counts down to the opening of the start-up window, then green from -5:00 to 0:00 (your TSAT) and up to +5:00, then red. Hover it for TSAT, window, TOBT, TTOT and CTOT. Click it to switch to the other clocks as before; it switches to the TSAT clock by itself when a new TSAT arrives and goes back to your usual clock after take-off or when you disconnect
- TSAT clock: when the start-up window opens, the floating icon turns electric yellow-green until you open the card or click the clock (not while notifications are muted)
- Phone: the home-screen app no longer stops connecting when your PC gets a new address on the Wi-Fi (new DHCP lease, Windows' random hardware addresses). After scanning the QR code, the page switches to your PC's name (http://your-pc-name.local:8787) when the phone can find it, and that address stays valid. Phones that can't use .local names stay on the IP as before. Scan the QR code once more and add the page to the home screen again after it says "Now using your PC's name"
- Radar: each airport with controllers shows a dot with its controller badges underneath and its name above (zoomed in); airport names for traffic are also above their dot
- MSFS panel: the callsign shown when hovering the faint icon is white
- New **Dark** theme colours (navy, #050e17) and a new **Black** theme. Settings > Theme: Dark, Black or Light (phone, PC and MSFS panel)
- TSAT clock: Clearway only asks while vPilot is connected (not as an observer) and you're on the ground with a flight plan: once every 3 minutes until a TSAT is set, then no more, or once a minute if your flight has a CTOT. Only your own flight is kept. It needs your VATSIM CID in Settings, which is sent as the request's User-Agent. It can be switched off in Clearway's settings
- MSFS panel: accents and symbols no longer show as empty boxes in MSFS 2024. The panel and the radar now use the bundled Selawik font (Microsoft's open version of Segoe UI, SIL Open Font License)
- MSFS panel: the floating icon turns cyan only for vPilot messages meant for you (private messages, SELCAL, frequency text with your callsign). Other unread messages (broadcasts) show a small grey dot at its bottom left. Hover the faint icon to see your callsign
- MSFS panel: the faint icon is yellow while you're not connected to VATSIM
- MSFS panel: the notepad shows your callsign at the top right
- Radar: the info windows (airport, controller, pilot) are about a third smaller: the airport name is on the ICAO line and each controller's information is cut to two lines (click it to read it all)
- Radar: departures and arrivals have their own slim box at the bottom right (the same height as the pilot count) while an airport is selected: a red circle (departures) and a green circle (arrivals) with the counts. Click one to show or hide its lines; filled means shown
- Radar: fixed an error when the controller data wasn't ready yet

## 1.0.0

- New **Radar** tab in the MSFS panel: live VATSIM traffic on a dark map. Planes show their callsign and type with the destination underneath; click one for the full tag (frequency it's tuned to, altitude, speed) and its details. Planes on the ground appear when zoomed in to airport level
- Radar: online controllers with their sectors from VATGlasses (coloured areas with callsign and frequency), airport badges for Delivery / Ground / Tower / Approach / ATIS, and approach circles where VATGlasses has no data. Click a sector or airport for the controllers, frequencies and ATIS
- Radar: airports with arriving traffic show as small dots; click an airport for red departure and green arrival lines (each can be switched off)
- Radar: your own aircraft is green when you're connected (Clearway knows your callsign from the vPilot plugin), or a hollow green outline at your sim position when you're offline or an observer. The target button centres the map on you (click once), then keeps tracking you (click again)
- Radar: on the Radar tab the card is twice as wide. The detach button opens the radar in its own window that you can move and resize (it stays open when the card is closed); dock it back with the button in its title bar or "Put it back here" in the tab
- Radar: buttons for labels, ATC and display size (AUTO / 1080p / 1440p / 4K). The buttons and the map credits keep the same size whatever the display size
- Radar: nothing is downloaded or drawn while the radar is hidden; its data (about 120 MB of memory) only loads the first time you open it. Map: Esri World Dark Gray Canvas; sectors: VATGlasses (CC BY-NC-SA 4.0); airports: VATSpy data project (CC BY-SA 4.0)
- MSFS panel: the card is a little wider so its header fits all four tabs, the clock and the buttons (with four tabs the notepad and collapse buttons were cut off)
- Radar: smooth dragging and zooming in MSFS 2024 (the map is moved on screen while you drag and redrawn when you stop), no more gaps between map tiles, and new map areas load about twice as fast
- Radar: the detached radar window stays under the Clearway card
- MSFS panel: the floating icon turns solid when a message arrives instead of flashing, and is fully visible for the first 10 seconds so it's easy to find
- MSFS panel: right click on the icon works in MSFS 2024 (peek at the latest message, CPDLC replies, WX)
- MSFS panel: Tab / Shift+Tab move between text boxes
- MSFS panel: new mute icon for notifications and a rotation-lock icon for the card direction
- MSFS panel: fixed a drawing glitch in MSFS 2024 when the card changed size (deleted messages, request form)
- vPilot: Nearby ATC on the left of the chat tabs (its count stands out when controllers are online), frequency on the right; hover the frequency for TX / RX on each radio
- vPilot: Mode C, Standby and Ident now also set the aircraft's transponder in the sim, which vPilot follows (from the panel and the phone)
- vPilot: the SELCAL in the connect form is always written AB-CD
- vPilot: as an observer you can only send private messages, not frequency text
- vPilot: the FP status badge is red with a cross when no flight plan is filed on VATSIM and green with a tick when it is
- vPilot: "vPilot not opened / plugin not found" when Clearway can't reach vPilot
- CPDLC: Hoppie status in the CPDLC tab (green tick connected, red cross not); click it to type or paste your logon code. The code and your SimBrief ID are hidden on screen
- CPDLC: a logon request with no answer after 10 minutes is cancelled
- SELCAL: the VATSIM flight plan count is no longer shown in the bar

## 0.9.8

- Fixed: fetching the SimBrief flight plan failed with "invalid literal for int()" (SimBrief now sends the plan's time as a date)
- Fixed: your own flight plan or prefile no longer shows your SELCAL as "Used by" yourself (your vPilot callsign, your SimBrief callsign and the callsign in the SELCAL tab are ignored)
- MSFS panel: the SimBrief username box keeps lower-case letters instead of showing everything in capitals
- MSFS panel: your SimBrief username or pilot ID is shown in the SELCAL bar next to the SimBrief button; click it to change it (the box opens with the current one selected, Fetch saves the new one, click again to cancel)

## 0.9.7

- vPilot connect form: under the callsign box, **SB: CALLSIGN** shows the callsign of your latest SimBrief flight plan, to catch typos. It turns green when what you typed matches and amber when it doesn't; click it to use that callsign. The small refresh icon next to it fetches your latest SimBrief plan again (panel and phone)
- The SimBrief plan is fetched automatically the first time you open the connect form (once your SimBrief username is set in the SELCAL tab)

## 0.9.6

- vPilot connect form: a small line under the SELCAL field checks the code on VATSIM as you type: "check. avail..." while checking, then **avail.** in green or **taken by CALLSIGN** in red (panel and phone)
- MSFS panel: play/pause button in the top-right icons to pause panel notifications. While paused, the floating icon stays faint and quiet (no flashing, colour or counters) and shows a small pause mark; Clearway also stops muting your phone, so messages still reach you there. Click again to resume
- MSFS panel: the card is slightly wider to fit the extra button

## 0.9.5

- New **SELCAL** tab (MSFS panel, phone and PC), merged from the SELCAL code generator: standard (16-tone) and extended (32-tone) codes, airline name and logo, save codes for 24 hours (up to 10 per callsign), shared between the panel, phone and PC
- SELCAL: generated codes are checked against every flight plan on VATSIM (online and prefiled), so you never get a code someone else is using. Each code shows "Free on VATSIM" or who uses it
- SELCAL: **SimBrief** button reads your latest SimBrief flight plan and shows its SELCAL, with the same VATSIM check (enter your SimBrief username or pilot ID once)
- SELCAL: "Use in vPilot" puts the code in vPilot's connect form
- SELCAL: "Check a code": type any code to see if it's valid and whether anyone on VATSIM uses it, then save it or use it in vPilot
- SELCAL: the "Free / Used by" lines refresh by themselves whenever Clearway reads new VATSIM data (every minute while vPilot is connected)
- vPilot: a bold **FP status** warning appears next to your callsign when you're connected but VATSIM has no flight plan filed for it (or only a prefile)

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
