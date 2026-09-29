# Rudi Makes Site

Simple static site + Python editor script for rudimakes.com: Filament's amp and
synth repair business, and Rudi's design portfolio.

- the homepage (repair services, recent repairs, TBX feature, about, contact)
- repair/troubleshooting logs and service pages
- the TBX Home Broadcast page at `/tbx/`
- site profile content (about/contact)

The build log and the shop were retired in the 2026-09 revamp (see
`RETIRED-PROJECTS.md`). Old `shop.html` and `projects/tbx-home-broadcast.html`
URLs are redirect stubs.

## Files
- `index.html` – homepage (generated from `template.html`)
- `repairs.html` – repair log + pricing (generated from `repairs_template.html`)
- `repairs/*.html` – per-repair pages (generated from `repair_template.html`)
- `services.html`, `services/*.html` – service pages (generated)
- `tbx/` – the TBX page. **Not generated here**: it is copied from the TBX project
  (`~/Documents/tbx/landing`) by `python3 tools/sync_tbx.py`, which also adds the site nav strip
- `style.css` – shared styles (Filament brand: Outfit + DM Sans, amber filament accent)
- `images/filament-logo-{dark,light}.svg`, `images/filament-mark.svg` – the Filament logo
- `repairs.json`, `services.json`, `site.json` – content
- `manage.py` – interactive editor script

## Run
From this folder:

```bash
python3 manage.py
```

Then choose a command:
- `input-repair` – add a new repair log
- `edit-repair` – edit an existing repair entry
- `delete-repair` – remove a repair entry
- `undo-last` – restore the latest JSON backup
- `list-backups` – show available backups
- `restore-backup` – choose and restore a specific backup
- `publish-github` – stage all, commit, and push changes to your GitHub repo
- `web-ui` – launch a local browser-based admin menu
- `edit-site` – update name, about text, links, tags
- `list-repairs` – list repairs
- `rebuild` – regenerate the homepage, repair log, services and sitemap

## Typical flow
1. Add or edit content with `manage.py`.
2. Run `rebuild` (or use commands that rebuild automatically).
3. Open `index.html` in a browser and verify.

`manage.py` now runs in a loop until you choose `q` to quit.

## Web Admin UI
From `manage.py`, choose `web-ui` (menu option `16`).

Default URL:
- `http://127.0.0.1:8081`

The web UI lets you:
- rebuild and publish
- edit site settings
- add/delete repairs

(Its Build and Shop forms are leftovers: nothing is published from them any more.)

## Notes
- Images are copied into `images/` when you add entries with photos.
- `manage.py` now escapes text before writing HTML, so special characters in descriptions/tags won’t break page markup.
- Backups are stored in `.backups/` before content-editing commands.
- `publish-github` uses local git config/credentials (SSH key or token) and pushes current branch to `origin`.
