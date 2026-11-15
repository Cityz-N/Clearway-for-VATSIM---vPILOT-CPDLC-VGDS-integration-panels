"""Fill a test Clearway (tools/dev_run.py, port 8797) with realistic demo traffic.

Used for documentation screenshots. Start tools/dev_run.py and the fake vPilot first:
    python tools/dev_run.py
    set CLEARWAY_PORT=8797 & tools\\fake-vpilot\\bin\\Release\\net472\\FakeVpilot.exe vpilot-plugin\\compiled\\Clearway.vPilot.dll
    python tools/demo_data.py
"""
import json
import time
import urllib.request

API = "http://127.0.0.1:8797/api/"


def call(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read() or b"{}")


def main():
    call("clear", {})
    for m in call("state?since=0")["messages"]:
        call("delete", {"id": m["id"]})

    # vPilot: radios, frequency chat, controller info, private chat
    call("com", {"com1": "118.500", "com1_stby": "121.975", "com1_tx": True,
                 "com2": "121.500", "com2_stby": "122.800", "com2_tx": False})
    ev = lambda **e: call("vpilot/event", e)  # noqa: E731
    ev(type="radio", message="AFR1681 line up and wait runway 27R", frequencies="118.500", **{"from": "EGLL_TWR"})
    time.sleep(0.2)
    call("vp/command", {"text": "BAW117 holding point 27R, ready for departure", "chat": "FREQ"})
    time.sleep(0.6)
    ev(type="radio", message="BAW117 behind the departing A320, line up runway 27R behind", frequencies="118.500", **{"from": "EGLL_TWR"})
    time.sleep(0.2)
    call("vp/command", {"text": ".atis EGLL_ATIS", "chat": "FREQ"})
    time.sleep(0.8)
    ev(type="pm", message="Hi! Expect the CPT 5K departure, CPDLC available on EGGX after departure.", **{"from": "EGLL_TWR"})
    time.sleep(0.2)
    call("vp/command", {"text": "Thanks, copied!", "chat": "EGLL_TWR"})
    time.sleep(0.6)
    ev(type="radio", message="BAW117 wind 250 degrees 9 knots, runway 27R cleared for take-off", frequencies="118.500", **{"from": "EGLL_TWR"})

    # CPDLC: METAR, logon (climb instruction), a request, then a DCL with its clearance
    call("connect", {})
    time.sleep(2)
    for what, body in [("inforeq", {"what": "metar", "icao": "EGLL"}), ("logon", {"station": "EGGX"}),
                       ("cpdlc", {"text": "REQUEST FL390 DUE TO WEATHER"}),
                       ("telex", {"station": "EGLL", "text": "REQUEST PREDEP CLEARANCE BAW117 B77W TO KJFK AT EGLL STAND 512 ATIS C"})]:
        call(what, body)
        time.sleep(0.5)
    for m in call("state?since=0")["messages"]:
        if m.get("tag") == "METAR" and m["dir"] == "in":
            call("ack", {"id": m["id"]})
    call("notes", {"text": "EGLL ATIS C  QNH 1018\nStand 512  Squawk 4621\nCPT 5K  initial alt 6000\nNAT track B  M84 FL370\n\nEGGX logon after departure"})
    s = call("state?since=0")
    print("messages:", len(s["messages"]), "| unread vPilot:", s["unacked_vpilot"], "| unread CPDLC:", s["unacked_cpdlc"])


if __name__ == "__main__":
    main()
