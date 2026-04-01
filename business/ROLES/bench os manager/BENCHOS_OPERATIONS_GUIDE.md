# BenchOS — Operations Guide

**Last updated:** March 31, 2026

---

## What This Is

Willock Bench OS is a local-first repair shop management system for
electronics and instrument repair. Built with Python, Flask, and SQLite.
Runs entirely on your machine — no internet required.

---

## Project Location

```
~/bench_os/
```

Copied from the LaCie drive (`/media/rudi/LaCie/dev/bench_os/`) on
March 31, 2026 because the LaCie is formatted exFAT and can't support
Python virtual environments (no symlinks).

The LaCie copy is your backup/archive. The working copy is `~/bench_os/`.

---

## How to Start the Server

Open a terminal and run:

```bash
cd ~/bench_os
source venv/bin/activate
python run.py
```

Then open your browser to:

```
http://127.0.0.1:5000
```

Press `Ctrl+C` in the terminal to stop the server.

---

## Virtual Environment

**Location:** `~/bench_os/venv/`

The venv must be activated every time you open a new terminal:

```bash
source ~/bench_os/venv/bin/activate
```

You'll know it's active when you see `(venv)` at the start of your prompt.

**Installed packages:** Flask (and its dependencies: Jinja2, Werkzeug,
Click, MarkupSafe, itsdangerous, blinker).

If you ever need to recreate the venv:

```bash
cd ~/bench_os
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install flask
```

---

## Database

**Location:** `~/bench_os/data/benchos.db`

SQLite file. No server process needed — the app reads it directly.

**Backups:** `~/bench_os/backup/archives/`

A dated backup is created automatically every time the app starts
(one per day, keeps the last 30). You can also run a manual backup:

```bash
cd ~/bench_os
source venv/bin/activate
python cli.py backup
```

**If the database gets corrupted or you need a fresh start:**

```bash
rm ~/bench_os/data/benchos.db
python run.py
```

The migration system rebuilds everything from scratch on next startup.

---

## CLI Commands

With the venv activated:

```bash
python cli.py help       # Show all commands
python cli.py init       # Initialize database
python cli.py backup     # Run a manual backup
python cli.py check      # Run reminder checks
python cli.py jonas      # Print Jonas invoice for current month
python cli.py jobs       # List active jobs
python cli.py stale      # List stale jobs
python cli.py search <q> # Search from terminal
python cli.py orphans    # Close orphaned timer sessions
```

---

## What Was Built — March 31, 2026

### Fix 1 — Directory structure
Organized all files from a flat layout into proper Python packages
(db/, dal/, logic/, web/, backup/). Created config.py and migrations.py.

### Fix 2 — Missing DAL functions
Wrote 13 missing database functions for intake, diagnostics, repair
records, and bench timer sessions.

### Fix 3 — Duplicate status history
Dropped a database trigger that was creating duplicate rows on every
status change.

### Fix 4 — Search indexes
Added 21 FTS sync triggers so full-text search actually finds data.

### Fix 5 — Invoice numbering
Replaced COUNT(*)-based numbering with an atomic sequence so invoice
numbers can't collide after a restore.

### Fix 6 — Timer bugs
Fixed a crash in start_timer() and an operator precedence bug in
get_timer_status().

### Fix 7 — Connection management
Added Flask g.db hooks so routes don't manually manage database
connections. Rewrote all 7 route files.

### Fix 8 — Dead code cleanup
Removed unused duplicate queries and shadowed imports.

### Fix 9 — Workflow fix
DECLINED jobs can now transition back to APPROVED when a customer
changes their mind.

---

## File Structure

```
~/bench_os/
├── config.py              ← all settings
├── run.py                 ← start the server
├── cli.py                 ← command line tools
├── data/benchos.db        ← the database
├── migrations/            ← schema migrations (4 files)
├── db/                    ← connection + migration runner
├── dal/                   ← data access layer (12 files)
├── logic/                 ← business logic (5 files)
├── backup/                ← backup system + archives
├── venv/                  ← Python virtual environment
└── web/
    ├── routes/            ← Flask route handlers (7 files)
    ├── static/css/        ← main.css
    ├── static/js/         ← main.js
    └── templates/         ← HTML templates (22 files)
```
