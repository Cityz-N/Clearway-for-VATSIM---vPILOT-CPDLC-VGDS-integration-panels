"""Local HTTP server: serves the web app and the JSON API used by the phone and the MSFS panel."""
from __future__ import annotations

import ipaddress
import json
import logging
import mimetypes
import socket
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .session import Session

log = logging.getLogger("clearway.server")


def web_root() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "web"


def lan_ip() -> str:
    """Best guess of this PC's address on the home network (no traffic is sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "Clearway"
    session: Session = None  # set by make_server

    # Keep the console clean; errors still go to the log file.
    def log_message(self, fmt, *args):
        log.debug("%s - %s", self.address_string(), fmt % args)

    # ------------------------------------------------------------ helpers
    def _is_local(self) -> bool:
        try:
            return ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            return False

    def _authorized(self, query: dict) -> bool:
        if self._is_local():
            return True
        key = self.headers.get("X-Clearway-Key") or (query.get("k") or [""])[0]
        return key == self.session.cfg.get("pair_key")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Clearway-Key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(min(length, 64_000))
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except ValueError:
            return {}

    # ------------------------------------------------------------ verbs
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(url.query)
        if url.path == "/api/state":
            if not self._authorized(query):
                return self._json({"error": "pair"}, 401)
            if (query.get("panel") or ["0"])[0] == "1":
                self.session.panel_seen = time.time()
            since = (query.get("since") or ["0"])[0]
            if since.isdigit() and int(since) == self.session.version:
                return self._json({"version": self.session.version, "unchanged": True,
                                   "panel_active": self.session.panel_active()})
            snap = self.session.snapshot()
            if not self._is_local():
                snap["settings"].pop("port", None)
            return self._json(snap)
        if url.path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        return self._static(url.path)

    def do_POST(self):
        url = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(url.query)
        if not url.path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        if not self._authorized(query):
            return self._json({"error": "pair"}, 401)
        action = url.path[len("/api/"):]
        body = self._read_body()
        s = self.session
        try:
            if action == "quick":            # tapped button on a phone notification
                s.reply(int(query["id"][0]), query["r"][0])
            elif action == "connect":
                s.connect()
            elif action == "disconnect":
                s.disconnect()
            elif action == "reply":
                s.reply(int(body["id"]), str(body.get("text", "")))
            elif action == "ack":
                s.ack(int(body["id"]) if body.get("id") is not None else None)
            elif action == "logon":
                s.logon(str(body.get("station", "")))
            elif action == "logoff":
                s.logoff()
            elif action == "cpdlc":
                s.send_cpdlc(body.get("station"), str(body.get("text", "")), str(body.get("ra", "Y")).upper())
            elif action == "telex":
                s.send_telex(str(body.get("station", "")), str(body.get("text", "")))
            elif action == "inforeq":
                s.inforeq(str(body.get("what", "")), str(body.get("icao", "")))
            elif action == "clear":
                s.clear_history()
            elif action == "position":
                s.panel_seen = time.time()
                s.set_panel_position(float(body["lat"]), float(body["lon"]), float(body.get("alt", 0)))
            elif action == "settings":
                data = dict(body)
                if not data.get("hoppie_logon"):
                    data.pop("hoppie_logon", None)   # empty field = keep the saved code
                s.cfg.update(data)
                s._bump()
            elif action == "pair":
                if not self._is_local():
                    return self._json({"error": "only available on this PC"}, 403)
                return self._json({"ok": True, "key": s.cfg.get("pair_key")})
            elif action == "test-notification":
                s.test_notification()
            elif action == "new-topic":
                s.cfg.regenerate_topic()
                s._bump()
            else:
                return self._json({"error": "unknown action"}, 404)
        except (KeyError, TypeError, ValueError) as exc:
            msg = str(exc) if isinstance(exc, ValueError) else "Bad request."
            return self._json({"ok": False, "error": msg}, 400)
        except Exception as exc:
            log.exception("API error")
            return self._json({"ok": False, "error": f"Internal error: {exc}"}, 500)
        return self._json({"ok": True, "version": s.version})

    def _static(self, path: str):
        root = web_root()
        rel = path.lstrip("/") or "index.html"
        target = (root / rel).resolve()
        if root.resolve() not in target.parents and target != root.resolve():
            return self._json({"error": "not found"}, 404)
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            target = root / "index.html"   # single-page app fallback
        data = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix == ".webmanifest":
            ctype = "application/manifest+json"
        self.send_response(200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") or ctype.endswith("javascript") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self._cors()
        self.end_headers()
        self.wfile.write(data)


def make_server(session: Session, port: int) -> ThreadingHTTPServer:
    Handler.session = session
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.daemon_threads = True
    return server
