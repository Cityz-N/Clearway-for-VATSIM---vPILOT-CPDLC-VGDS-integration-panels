"""Fill the test Clearway (tools/dev_run.py on 8797, plus the fake vPilot) with a realistic flight for the
screenshots: CPDLC logon + clearance, tower calls and a private message, radios, SELCAL codes, notes.
Never point this at the real Clearway (8787).

    python tools/dev_run.py
    set CLEARWAY_PORT=8797 & tools\\fake-vpilot\\bin\\Release\\net472\\FakeVpilot.exe vpilot-plugin\\compiled\\Clearway.vPilot.dll 3600
    build\\venv\\Scripts\\python tools/screenshots/prepare_shots.py
"""
import json
import time
import urllib.request

API = "http://127.0.0.1:8797/api/"


def call(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def main():
    call("com", {"com1": "118.500", "com1_stby": "121.975", "com1_tx": True,
                 "com2": "121.500", "com2_stby": "122.800", "com2_tx": False})
    call("connect", {})
    for _ in range(30):                       # wait for the mock Hoppie connection
        if call("state?since=0")["status"] == "online":
            break
        time.sleep(0.5)
    # CPDLC: departure clearance by telex, then logon to Shanwick (the mock answers with a CLIMB to accept)
    call("telex", {"station": "EGLL", "text": "REQUEST PREDEP CLEARANCE BAW117 B77W TO KJFK AT EGLL STAND 512 ATIS C"})
    time.sleep(2.5)
    call("logon", {"station": "EGGX"})
    time.sleep(3)
    # vPilot: frequency history and a private message
    for frm, msg in [("EGLL_TWR", "BAW117 behind the landing A320, line up and wait runway 27R behind"),
                     ("EGLL_TWR", "BAW117 wind 250 degrees 9 knots, runway 27R cleared for take-off"),
                     ("EGLL_TWR", "BAW117 contact London Control 132.840, goodbye")]:
        call("vpilot/event", {"type": "radio", "from": frm, "message": msg, "frequencies": "118.500"})
        time.sleep(0.2)
    call("vp/command", {"text": "Wind 250 at 9, cleared for take-off 27R, BAW117", "chat": "FREQ"})
    call("vpilot/event", {"type": "pm", "from": "EGTT_CTR", "message": "BAW117, expect direct LAM after departure, report when ready"})
    time.sleep(0.5)
    # SELCAL: codes for BAW117 (checked against VATSIM), two saved entries, a checked code
    cur = call("selcal/generate", {"callsign": "BAW117"})["current"]
    call("selcal/save", {"callsign": "BAW117", "generated": cur["generated"], "std": cur["std"], "ext": cur["ext"]})
    call("selcal/save", {"callsign": "AFR1681", "generated": 1, "std": "CH-LP"})
    call("selcal/check", {"code": "DM-QS", "exclude": "BAW117"})
    call("notes", {"text": "EGLL 27R  BPK7G  squawk 5523\nATIS C  QNH 1018\nShanwick 127.650\nOceanic: NAT B  FL370  M.84"})
    # read everything except the Shanwick clearance (so it shows WILCO / UNABLE) and the private message
    s = call("state?since=0")
    for m in s["messages"]:
        if m["dir"] == "in" and not m["acked"] and not m.get("options") and m["kind"] != "pm":
            call("ack", {"id": m["id"]})
    print("ready:", len(s["messages"]), "messages; SELCAL", cur["std"], cur["ext"])


if __name__ == "__main__":
    main()
