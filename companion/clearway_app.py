"""Clearway companion - entry point.

Runs quietly as an icon in the Windows notification area (next to the clock).
Double-click the icon to open Clearway; right-click for Connect/Disconnect and Quit.

    python clearway_app.py             tray icon (default on Windows)
    python clearway_app.py --console   no tray icon, keep running in this console
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import webbrowser

from clearway import __version__
from clearway.config import Config, data_dir
from clearway.server import lan_ip, make_server, pc_name_url, web_root
from clearway.procs import claim_single_instance, process_running
from clearway.session import Session

VPILOT_EXE = os.environ.get("CLEARWAY_VPILOT_EXE", "vPilot.exe")


def watch_vpilot(cfg: Config, on_quit) -> None:
    """Quit Clearway when vPilot closes (setting "quit_with_vpilot"), but only once vPilot has been seen running
    in this session: Clearway on its own (CPDLC only) keeps running. Checked every 5 s, closed for 10 s."""
    log = logging.getLogger("clearway")
    seen, missing = False, 0
    while True:
        threading.Event().wait(5)
        running = process_running(VPILOT_EXE)
        if running is None:
            return                                  # can't check processes here
        if running:
            seen, missing = True, 0
            continue
        missing += 1
        if seen and missing >= 2 and cfg.get("quit_with_vpilot"):
            log.info("vPilot closed: Clearway quits too")
            on_quit()
            return


def setup_logging() -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    file_handler = logging.FileHandler(data_dir() / "clearway.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    if sys.stdout is not None:            # no console when packaged as a windowed exe
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter("  %(message)s"))
        console.setLevel(logging.INFO)
        root.addHandler(console)


def notify_user(text: str) -> None:
    if sys.stdout is not None:
        print(f"\n  {text}\n")
    if os.name == "nt":
        from clearway.tray import message_box
        message_box(text)


def main() -> None:
    # Windows consoles may not use UTF-8; never crash on a special character.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    setup_logging()
    log = logging.getLogger("clearway")
    cfg = Config()
    port = int(cfg.get("port") or 8787)
    # one Clearway at a time (per port): checked before anything starts (Hoppie, vPilot, radar...)
    if not claim_single_instance(f"Clearway-{port}"):
        log.info("Clearway is already running: this second copy closes")
        notify_user("Clearway is already running. Look for its icon next to the clock.")
        return
    session = Session(cfg)
    try:
        server = make_server(session, port)
    except OSError:
        notify_user("Clearway is already running. Look for its icon next to the clock.")
        return

    session.port = port                           # session.base_url follows the PC's current IP
    session.name_url = pc_name_url(port)          # the phone app moves to this one when it can reach it
    local_url = f"http://localhost:{port}/"
    open_page = lambda: webbrowser.open(local_url)  # noqa: E731
    log.info("Clearway %s running on %s (phone: %s)", __version__, local_url, session.base_url)

    # First start (nothing configured yet) always opens the page so people find the settings.
    first_run = not cfg.get("hoppie_logon")
    if cfg.get("open_browser_on_start") or first_run:
        threading.Timer(0.8, open_page).start()

    use_tray = os.name == "nt" and "--console" not in sys.argv
    if not use_tray:
        print(f"\n  Clearway {__version__} - open {local_url}\n  Keep this window open while you fly. Ctrl+C to quit.\n")
        threading.Thread(target=watch_vpilot, args=(cfg, server.shutdown), daemon=True, name="vpilot-watch").start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            if session.status == "online":
                session.disconnect()
            server.server_close()
        return

    from clearway.tray import TrayIcon
    threading.Thread(target=server.serve_forever, daemon=True).start()
    tray: TrayIcon

    def tooltip() -> str:
        if session.status == "online":
            unit = session.current_unit or "no ATC"
            unread = sum(1 for m in session.messages if m["dir"] == "in" and not m["acked"])
            return f"Clearway - {session.callsign} · {unit}" + (f" · {unread} new" if unread else "")
        if session.status == "connecting":
            return "Clearway - connecting…"
        return "Clearway - not connected"

    def toggle_connection() -> None:
        if session.status in ("online", "connecting"):
            session.disconnect()
        else:
            session.connect()

    def quit_app() -> None:
        tray.quit()

    def menu() -> list:
        online = session.status in ("online", "connecting")
        return [
            ("Open Clearway", open_page, True),
            (tooltip().replace("Clearway - ", ""), None, False),
            None,
            ("Disconnect" if online else "Connect", toggle_connection, True),
            None,
            ("Quit Clearway", quit_app, True),
        ]

    icon = str(web_root() / "clearway.ico")
    tray = TrayIcon(icon, tooltip, menu, open_page)
    threading.Thread(target=watch_vpilot, args=(cfg, quit_app), daemon=True, name="vpilot-watch").start()
    try:
        tray.run(balloon=None if first_run else "Clearway is running. Double-click this icon to open it.")
    except Exception:
        log.exception("Tray icon failed")
        notify_user("Clearway couldn't create its tray icon. See clearway.log for details.")
    if session.status == "online":
        session.disconnect()          # logs off ATC politely
    server.shutdown()
    server.server_close()


if __name__ == "__main__":
    main()
