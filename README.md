# Rudi Makes Site

Simple static site + Python editor script for:
- project build logs
- repair/troubleshooting logs
- site profile content (about/contact)

## Files
- `index.html` – main builds page (generated)
- `repairs.html` – troubleshooting page (generated)
- `projects/*.html` – per-project detail pages (generated)
- `template.html` – template used to rebuild `index.html`
- `repairs_template.html` – template used to rebuild `repairs.html`
- `project_template.html` – template used to rebuild per-project pages
- `projects.json` – build entries
- `repairs.json` – repair entries
- `site.json` – profile, contact, and about tags
- `manage.py` – interactive editor script

## Run
From this folder:

```bash
python3 manage.py
```

Then choose a command:
- `input-project` – add a new build
- `edit-project` – edit build details (title, status, cover, gallery, tags, links, text)
- `edit-story` – edit build story sections (photos + text)
- `input-repair` – add a new repair log
- `edit-repair` – edit an existing repair entry
- `delete-project` – remove a build and its generated project page
- `delete-repair` – remove a repair entry
- `undo-last` – restore the latest JSON backup
- `list-backups` – show available backups
- `restore-backup` – choose and restore a specific backup
- `publish-github` – stage all, commit, and push changes to your GitHub repo
- `web-ui` – launch a local browser-based admin menu
- `edit-site` – update name, about text, links, tags
- `list-projects` – list builds
- `list-repairs` – list repairs
- `rebuild` – regenerate both HTML pages from JSON + templates
- `rebuild` – regenerates list pages and per-project detail pages

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
- add/delete builds and repairs
- manage build story sections

## Notes
- Images are copied into `images/` when you add entries with photos.
- `manage.py` now escapes text before writing HTML, so special characters in descriptions/tags won’t break page markup.
- Backups are stored in `.backups/` before content-editing commands.
- `publish-github` uses local git config/credentials (SSH key or token) and pushes current branch to `origin`.
