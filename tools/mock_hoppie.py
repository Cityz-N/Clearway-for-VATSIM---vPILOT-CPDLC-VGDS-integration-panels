"""A tiny fake Hoppie server for testing Clearway without the real network.

Usage:
    python tools/mock_hoppie.py            (listens on http://127.0.0.1:8790/connect.html)
Then set "hoppie_url": "http://127.0.0.1:8790/connect.html" in a test config
(use the CLEARWAY_DATA_DIR environment variable to point Clearway at a test folder).

Behaviour: answers REQUEST LOGON with LOGON ACCEPTED followed by a CLIMB clearance,
answers REQUEST FL... with UNABLE, ADS-C periodic request after logon, METAR on inforeq.
Queued messages are delivered on the next request of any kind.
"""
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

queue: list[str] = []
counter = [100]


def nxt():
    counter[0] += 1
    return counter[0]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
        q = {k: v[0] for k, v in urllib.parse.parse_qs(body, keep_blank_values=True).items()}
        kind, to, packet = q.get("type", ""), q.get("to", ""), q.get("packet", "")
        print(f"<- {q.get('from')} -> {to} [{kind}] {packet}")
        reply = "ok"
        if not q.get("logon"):
            reply = "error {illegal logon code}"
        elif kind == "inforeq":
            reply = "ok {server info {METAR " + packet.split()[-1] + " 121250Z 24012KT 9999 FEW030 12/06 Q1018}}"
        elif kind == "cpdlc":
            m = re.match(r"/data2/(\d+)/(\d*)/(\w+)/(.*)", packet)
            if m:
                mn, _, _, text = m.groups()
                if text == "REQUEST LOGON":
                    queue.append(f"{{{to} cpdlc {{/data2/{nxt()}/{mn}/NE/LOGON ACCEPTED}}}}")
                    queue.append(f"{{{to} cpdlc {{/data2/{nxt()}//WU/{q['from']} CLIMB TO AND MAINTAIN @FL370@ REPORT LEVEL @FL370@}}}}")
                    queue.append(f"{{{to} ads-c {{REQUEST PERIODIC 300}}}}")
                elif text.startswith("REQUEST FL"):
                    queue.append(f"{{{to} cpdlc {{/data2/{nxt()}/{mn}/NE/UNABLE DUE TO TRAFFIC}}}}")
                elif text.startswith("WHEN CAN WE"):
                    queue.append(f"{{{to} cpdlc {{/data2/{nxt()}/{mn}/AN/EXPECT HIGHER AT @1430@ CAN YOU ACCEPT @FL390@}}}}")
        elif kind == "telex":
            queue.append(f"{{{to} telex {{CLEARED {q['from']} AS FILED. SQUAWK 4621. NEXT FREQ 121.975}}}}")
        if reply == "ok" and queue:
            reply = "ok " + " ".join(queue)
            queue.clear()
        print(f"-> {reply}")
        data = reply.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print("Mock Hoppie on http://127.0.0.1:8790/connect.html")
    ThreadingHTTPServer(("127.0.0.1", 8790), H).serve_forever()
