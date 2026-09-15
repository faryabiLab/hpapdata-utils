#!/usr/bin/env python3
"""
HPAP 2nd ID Generator

Computes the "2nd ID" for a donor from the pancreas cross-clamp time and
logs the entry into HPAP_2nd_ID_Log.csv.

2nd ID format: YY + M + DD + HH  (all from the cross-clamp time, local time)
  YY = 2-digit year
  M  = single-letter month code (custom scheme, avoids Jan/Jun/Jul & Mar/May & Apr/Aug collisions)
  DD = 2-digit day
  HH = 2-digit hour, 24-hour clock

Run it with:  python3 generate_id.py
"""

import csv
import datetime
import re
from pathlib import Path

LOG_FILE = Path(__file__).parent / "HPAP_2nd_ID_Log.csv"
HEADERS = [
    "HPAP_ID", "UNOS#", "cross_clamp_time", "time_zone",
    "disease_status", "notes", "2nd_ID",
]

MONTH_CODE = {
    1: "J", 2: "F", 3: "M", 4: "A", 5: "Y", 6: "U",
    7: "L", 8: "G", 9: "S", 10: "O", 11: "N", 12: "D",
}


def parse_crossclamp(text):
    """Parse a cross-clamp date/time string into a datetime.

    Accepts things like: 10/29/2016 15:13, 10/29/16, 15:13, 1/21/24 4:13,
    3/02/24, 22.02, 2/08/23, 0053
    """
    text = text.strip()

    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})[,\.]?\s*(\d{1,2})[:\.](\d{2})$", text)
    if m:
        mo, d, y, h, mi = m.groups()
    else:
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})[,\.]?\s*(\d{3,4})$", text)
        if not m:
            raise ValueError(
                f"Couldn't understand the date/time {text!r}. "
                "Try a format like 8/20/2026 14:30"
            )
        mo, d, y, hm = m.groups()
        hm = hm.zfill(4)
        h, mi = hm[:2], hm[2:]

    year = int(y)
    if year < 100:
        year += 2000

    return datetime.datetime(year, int(mo), int(d), int(h), int(mi))


def compute_second_id(dt):
    return f"{dt.year % 100:02d}{MONTH_CODE[dt.month]}{dt.day:02d}{dt.hour:02d}"


def load_log_rows():
    """Return existing log rows as a list of dicts, or [] if none yet."""
    if not LOG_FILE.exists():
        return []
    with open(LOG_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def existing_hpap_ids(rows):
    return {r["HPAP_ID"].strip() for r in rows if r.get("HPAP_ID")}


def suggest_next_hpap_id(rows):
    max_num = 0
    for r in rows:
        hpap_id = r.get("HPAP_ID")
        if hpap_id:
            m = re.match(r"HPAP0*(\d+)", hpap_id.strip(), re.IGNORECASE)
            if m:
                max_num = max(max_num, int(m.group(1)))
    return f"HPAP{max_num + 1:03d}" if max_num else "HPAP001"


def append_entry(hpap_id, unos, crossclamp_dt, timezone, disease_status,
                  notes, second_id):
    is_new = not LOG_FILE.exists()
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        if is_new:
            writer.writeheader()
        writer.writerow({
            "HPAP_ID": hpap_id,
            "UNOS#": unos,
            "cross_clamp_time": crossclamp_dt.strftime("%m/%d/%y %H:%M"),
            "time_zone": timezone,
            "disease_status": disease_status,
            "notes": notes,
            "2nd_ID": second_id,
        })


def prompt(label, default=None, required=True):
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"{label}{suffix}: ").strip()
        if not val and default is not None:
            val = default
        if val or not required:
            return val
        print("  This field is required.")


def main():
    print("=" * 50)
    print("HPAP 2nd ID Generator")
    print("=" * 50)

    rows = load_log_rows()
    ids_seen = existing_hpap_ids(rows)

    while True:
        default_id = suggest_next_hpap_id(rows)
        while True:
            hpap_id = prompt("HPAP_ID", default=default_id)
            if hpap_id in ids_seen:
                confirm = input(
                    f"  '{hpap_id}' is already in the log. Add it again anyway? (y/N): "
                ).strip().lower()
                if confirm != "y":
                    continue
            break

        unos = prompt("UNOS#", required=False)

        while True:
            cc_raw = prompt("Cross clamp time, local (e.g. 8/20/2026 14:30)")
            try:
                cc_dt = parse_crossclamp(cc_raw)
                break
            except ValueError as e:
                print(f"  {e}")

        timezone = prompt("Time zone (e.g. EST)", required=False)
        disease_status = prompt("Disease status", required=False)
        notes = prompt("Notes", required=False)

        second_id = compute_second_id(cc_dt)
        append_entry(hpap_id, unos, cc_dt, timezone, disease_status, notes,
                     second_id)
        rows.append({
            "HPAP_ID": hpap_id,
            "UNOS#": unos,
            "cross_clamp_time": cc_dt.strftime("%m/%d/%y %H:%M"),
            "time_zone": timezone,
            "disease_status": disease_status,
            "notes": notes,
            "2nd_ID": second_id,
        })
        ids_seen.add(hpap_id)

        print(f"\n  2nd ID: {second_id}")
        print(f"  Saved to {LOG_FILE.name}\n")

        again = input("Add another entry? (Y/n): ").strip().lower()
        if again == "n":
            break

    print("Done.")


if __name__ == "__main__":
    main()