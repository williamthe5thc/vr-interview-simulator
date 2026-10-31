"""
Manage access codes for the headset app (see docs/ACCESS_CODES.md).

  python tools\access_codes.py add "Sam" [--per-day 3] [--expires 2026-12-31] [--max-concurrent 1] [--usd-per-day 0.25]
  python tools\access_codes.py list
  python tools\access_codes.py revoke "Sam"
  python tools\access_codes.py usage [--days 7]
  python tools\access_codes.py disable      kill switch: refuse every headset now (running interviews get no more turns)
  python tools\access_codes.py enable

The new code is printed ONCE by "add"; only a salted hash is stored, so a lost code cannot be shown again (revoke it, add a new one).
The running server picks up every change here by itself (codes, revokes, the kill switch): no restart needed.
"""

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.access_codes import load_codes, save_codes, make_entry, new_code, pretty, _read_json  # noqa: E402

CODES = os.path.join(ROOT, "config", "access_codes.json")
STATE = os.path.join(ROOT, "data", "access_state.json")
KILL = os.path.join(ROOT, "config", "quest_disabled")
TOOL = "python tools\\access_codes.py"


def _find_label(codes, label):
    return [c for c in codes if c["label"].lower() == label.lower()]


def cmd_add(a):
    data = load_codes(CODES)
    if any(not c.get("revoked") for c in _find_label(data["codes"], a.label)):
        sys.exit(f"'{a.label}' already has an active code. Revoke it first, or use another name.")
    if a.expires:
        try:
            datetime.date.fromisoformat(a.expires)
        except ValueError:
            sys.exit("--expires must be a date like 2026-12-31")
    code = new_code()
    data["codes"].append(make_entry(code, a.label, a.per_day, a.expires, a.max_concurrent, a.usd_per_day))
    save_codes(CODES, data)
    print(f"Code for {a.label}:  {pretty(code)}")
    print(f"({a.per_day} interviews a day"
          + (f", up to ${a.usd_per_day:.2f} a day" if a.usd_per_day is not None else "")
          + (f", valid through {a.expires}" if a.expires else "") + ")")
    print("Write it down now: it is not stored and cannot be shown again.")


def cmd_list(a):
    codes = load_codes(CODES)["codes"]
    if not codes:
        print(f"No codes yet. Add one with: {TOOL} add \"Name\"")
        return
    print(f"{'label':20} {'status':9} {'per day':>7} {'max at once':>11} {'$/day':>6}  {'expires':10}  created")
    for c in codes:
        status = "revoked" if c.get("revoked") else ("expired" if c.get("expires") and datetime.date.today().isoformat() > c["expires"] else "active")
        usd = "dflt" if c.get("usd_per_day") is None else f"{c['usd_per_day']:.2f}"
        print(f"{c['label'][:20]:20} {status:9} {c.get('interviews_per_day', 0):>7} {c.get('max_concurrent', 1):>11} {usd:>6}  "
              f"{(c.get('expires') or '-'):10}  {c.get('created', '')}")
    if os.path.exists(KILL):
        print(f"\nKILL SWITCH IS ON: every headset is refused ({TOOL} enable)")


def cmd_revoke(a):
    data = load_codes(CODES)
    hits = [c for c in _find_label(data["codes"], a.label) if not c.get("revoked")]
    if not hits:
        sys.exit(f"No active code for '{a.label}'.")
    for c in hits:
        c["revoked"] = True
        c["revoked_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    save_codes(CODES, data)
    print(f"Revoked {len(hits)} code(s) for {a.label}. A headset already in an interview finishes it; new connections are refused.")


def cmd_usage(a):
    codes = load_codes(CODES)["codes"]
    state = _read_json(STATE, {})
    usage = state.get("usage", {})
    spend = state.get("spend", {})
    now = datetime.datetime.now().timestamp()
    days = [(datetime.date.today() - datetime.timedelta(days=i)).isoformat() for i in range(a.days)]
    print(f"Interviews started per day (today first: {days[0]})")
    print(f"{'label':20} " + " ".join(d[5:] for d in days) + "   total   $ today")
    for c in codes:
        u = usage.get(c["id"], {})
        counts = [u.get(d, 0) for d in days]
        usd = spend.get(days[0], {}).get(c["id"], 0.0)
        print(f"{c['label'][:20]:20} " + " ".join(f"{n:>5}" for n in counts) + f"   {sum(counts):>5}   {usd:7.3f}"
              + ("  (revoked)" if c.get("revoked") else ""))
    print("\nEstimated API spend of all code sessions: " + ", ".join(f"{d[5:]} ${spend.get(d, {}).get('total', 0.0):.3f}" for d in days))
    if os.path.exists(KILL):
        print(f"\nKILL SWITCH IS ON: every headset is refused ({TOOL} enable)")
    if float(state.get("global_lockout", 0)) > now:
        print(f"\nAll code attempts paused after many wrong codes, until "
              f"{datetime.datetime.fromtimestamp(state['global_lockout']).strftime('%H:%M')}")
    locks = {ip: t for ip, t in state.get("lockouts", {}).items() if t > now}
    if locks:
        print("\nLocked out after wrong codes:")
        for ip, t in locks.items():
            print(f"  {ip} until {datetime.datetime.fromtimestamp(t).strftime('%H:%M')}")


def cmd_disable(a):
    with open(KILL, "w", encoding="utf-8") as f:
        f.write(f"disabled {datetime.datetime.now().isoformat(timespec='seconds')}\n")
    print("Kill switch ON: every headset is refused from now on, and running interviews get no more turns.")
    print(f"Turn it off with: {TOOL} enable")


def cmd_enable(a):
    if os.path.exists(KILL):
        os.remove(KILL)
        print("Kill switch OFF: headsets with a valid code can connect again.")
    else:
        print("The kill switch was already off.")


def main():
    p = argparse.ArgumentParser(description="Access codes for the VR interview headset app")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add", help="make a new code for a friend (printed once)")
    s.add_argument("label")
    s.add_argument("--per-day", type=int, default=3)
    s.add_argument("--expires", help="last valid day, YYYY-MM-DD")
    s.add_argument("--max-concurrent", type=int, default=1)
    s.add_argument("--usd-per-day", type=float, default=None, help="estimated API spend cap for this code (default: access.code_usd_per_day)")
    s.set_defaults(fn=cmd_add)
    sub.add_parser("list", help="show all codes (never the codes themselves)").set_defaults(fn=cmd_list)
    s = sub.add_parser("revoke", help="turn off a friend's code")
    s.add_argument("label")
    s.set_defaults(fn=cmd_revoke)
    s = sub.add_parser("usage", help="interviews and spend per code per day, and current lockouts")
    s.add_argument("--days", type=int, default=7)
    s.set_defaults(fn=cmd_usage)
    sub.add_parser("disable", help="kill switch: refuse every headset now").set_defaults(fn=cmd_disable)
    sub.add_parser("enable", help="turn the kill switch off").set_defaults(fn=cmd_enable)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
