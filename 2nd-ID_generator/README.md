# HPAP 2nd ID Generator

A small command-line tool that replaces the manual Excel workflow for computing an HPAP donor's "2nd ID" from the pancreas cross-clamp time. It computes the ID and logs each entry to an Excel workbook, so no one has to hand-compute the month-letter code anymore.

## What it does

Given a donor's cross-clamp time, the script computes a 2nd ID in the format:

```
YY + M + DD + HH
```

- `YY` — 2-digit year
- `M` — single-letter month code (custom scheme, see below)
- `DD` — 2-digit day
- `HH` — 2-digit hour (24-hour clock)

All values come from the cross-clamp time exactly as entered (local time, no time zone conversion).

### Month letter codes

A custom letter scheme is used instead of the first letter of the month name, to avoid collisions (e.g. Jan/Jun/Jul all start with J):

| Month | Code | Month | Code |
|-------|------|-------|------|
| Jan   | J    | Jul   | L    |
| Feb   | F    | Aug   | G    |
| Mar   | M    | Sep   | S    |
| Apr   | A    | Oct   | O    |
| May   | Y    | Nov   | N    |
| Jun   | U    | Dec   | D    |

### Logging

Each entry (HPAP_ID, UNOS#, cross-clamp time, time zone, disease status, notes, and the computed 2nd ID) is appended as a row to `HPAP_2nd_ID_Log.xlsx` in this folder. The workbook is created automatically on first run if it doesn't already exist.

## Requirements

- Python 3
- The [`openpyxl`](https://pypi.org/project/openpyxl/) package

## How to run it

### Option 1: `run.sh` (recommended, no setup required)

From Terminal:

```bash
cd 2nd-ID_generator
./run.sh
```

The first time you run it, this script creates a local virtual environment (`.venv`) in this folder and installs `openpyxl` into it automatically — it won't touch your system Python or any other project. On later runs it just launches the tool. This works no matter what Python setup you already have.

You can also double-click `run.sh` from Finder if your Mac is set up to run `.sh` files directly.

### Option 2: run the script directly

If you already have Python 3 and `openpyxl` installed (or are working in an IDE like VS Code, PyCharm, etc.):

```bash
pip install -r requirements.txt
python3 generate_id.py
```

## Using the tool

Once running, it will prompt you for each field:

```
HPAP_ID [HPAP217]:
UNOS#:
Cross clamp time, local (e.g. 8/20/2026 14:30):
Time zone (e.g. EST):
Disease status:
Notes:
```

- `HPAP_ID` suggests the next sequential ID by default — press Enter to accept it, or type your own.
- Cross-clamp time accepts several common formats, e.g. `10/29/2016 15:13`, `1/21/24 4:13`, `3/02/24 0053`.
- All fields except `HPAP_ID` and cross-clamp time are optional — just press Enter to skip.

After each entry, the computed 2nd ID is printed and the row is saved to `HPAP_2nd_ID_Log.xlsx`. You'll then be asked if you want to add another entry.

## Files

| File | Purpose |
|------|---------|
| `generate_id.py` | The main script |
| `run.sh` | Self-contained launcher (sets up its own virtual environment) |
| `requirements.txt` | Python dependencies |
| `HPAP_2nd_ID_Log.xlsx` | The log of all generated entries |
