# Retired projects — do not restore

On **2026-08-29** the build log was deliberately cut down to two projects.
The site is being focused on repair work and the shop; the projects below are
retired and should **not** be added back to `projects.json`.

## Currently live (the only two that belong)

| slug | title |
|---|---|
| `tbx-home-broadcast` | TBX Home Broadcast Station |
| `blu-language` | Blu — A Compiled Programming Language |

## Retired — do not re-add

| slug | title |
|---|---|
| `555-polyphonic-synth` | 37-Key 555 Polyphonic Synthesizer |
| `bench-os` | Filament Bench OS |
| `basil-game` | BASIL — Cinematic Narrative Game |
| `glorb-card-game` | Glorb — A Solo Card Game |
| `keystone-board-game` | Keystone — Arena Board Game |
| `linux-wifi-driver-patch` | MT7902 Linux Wi-Fi Driver Patch |
| `python-web-scraper` | Python Web Scraper |
| `usb-pd-charging-rack` | 30-Port iPad Charging Rack |

Their cover images are still in `images/projects/` and their entries are still
in git history, so nothing is lost if any of them is ever wanted back — but
that should be a deliberate decision, not an accident.

## Why this file exists

These projects were removed once before and came back on their own. The cause
is on record:

- Commit `e288a8c` had `projects.json` pruned down to 4 projects.
- Commit `3c67126` ("Remove image paths and update project titles", 2026-07-12)
  added 361 lines back and restored all 10.

That commit also rewrote every cover image path from
`images/projects/<slug>.jpg` to a flattened `images/<slug-no-dashes>.jpg`,
which is why **no project image on the site loaded** until 2026-08-29.

The likely source is a second, stale copy of this repo at
`C:\Users\Rudi\Desktop\rudimakes-main` (unpacked from `rudimakes-main (2).zip`).
It still contains all 10 projects and the old broken image paths. Publishing or
pasting `projects.json` from that folder undoes this cleanup.

**`C:\Users\Rudi\Desktop\rudimakes` is the only folder that publishes the site.**
It is the git checkout for `github.com/willockrudi/rudimakes`. Edit here, and
nowhere else.

## Rules of thumb

- `projects.json` is the source of truth. Editing `index.html` or
  `projects/*.html` by hand does nothing — `manage.py` regenerates both.
- Cover images live at `images/projects/<slug>.jpg`. Keep that shape.
- After changing `projects.json`, run `manage.py` → `rebuild-all` (or any
  edit command, which rebuilds automatically).
