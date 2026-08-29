
import json
import os
import re
import shutil
import html
import subprocess
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlencode, urlparse

# This script prints emoji status markers. On Windows stdout defaults to cp1252,
# which raises UnicodeEncodeError and kills the command (or 500s a web-UI request)
# whenever output is redirected to a file or pipe.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))

# Main Builds page
INDEX_PATH = os.path.join(ROOT, "index.html")
TEMPLATE_PATH = os.path.join(ROOT, "template.html")
PROJECT_TEMPLATE_PATH = os.path.join(ROOT, "project_template.html")
PROJECTS_DIR = os.path.join(ROOT, "projects")

# Troubleshooting page
REPAIRS_INDEX_PATH = os.path.join(ROOT, "repairs.html")
REPAIRS_TEMPLATE_PATH = os.path.join(ROOT, "repairs_template.html")

# Shop
SHOP_INDEX_PATH = os.path.join(ROOT, "shop.html")
SHOP_TEMPLATE_PATH = os.path.join(ROOT, "shop_template.html")
SHOP_COLLECTION_TEMPLATE_PATH = os.path.join(ROOT, "shop_collection_template.html")
SHOP_ITEM_TEMPLATE_PATH = os.path.join(ROOT, "shop_item_template.html")
SHOP_DIR = os.path.join(ROOT, "shop")

# Data files
DATA_PATH = os.path.join(ROOT, "projects.json")
REPAIRS_PATH = os.path.join(ROOT, "repairs.json")
SITE_PATH = os.path.join(ROOT, "site.json")
SHOP_PATH = os.path.join(ROOT, "shop.json")

# Assets
IMAGES_DIR = os.path.join(ROOT, "images")
BACKUPS_DIR = os.path.join(ROOT, ".backups")

# Site URL (used for canonical URLs, OG tags, structured data).
# Change this one line when the domain moves, then run `rebuild`. Every shop page
# derives its canonical/OG URLs from it via the {{SITE_URL}} placeholder.
# Also update CNAME, robots.txt, and the older non-shop templates, which still
# have the domain written into them directly.
SITE_URL = "https://rudimakes.com"

# Markers
PROJECTS_START = "<!-- PROJECTS_START -->"
PROJECTS_END = "<!-- PROJECTS_END -->"
REPAIRS_START = "<!-- REPAIRS_START -->"
REPAIRS_END = "<!-- REPAIRS_END -->"
TAGS_START = "<!-- TAGS_START -->"
TAGS_END = "<!-- TAGS_END -->"
PROJECT_STEPS_START = "<!-- PROJECT_STEPS_START -->"
PROJECT_STEPS_END = "<!-- PROJECT_STEPS_END -->"
COLLECTIONS_START = "<!-- COLLECTIONS_START -->"
COLLECTIONS_END = "<!-- COLLECTIONS_END -->"
COLLECTION_NAV_START = "<!-- COLLECTION_NAV_START -->"
COLLECTION_NAV_END = "<!-- COLLECTION_NAV_END -->"
SHOP_ITEMS_START = "<!-- SHOP_ITEMS_START -->"
SHOP_ITEMS_END = "<!-- SHOP_ITEMS_END -->"
ITEM_GALLERY_START = "<!-- ITEM_GALLERY_START -->"
ITEM_GALLERY_END = "<!-- ITEM_GALLERY_END -->"
ITEM_BUY_START = "<!-- ITEM_BUY_START -->"
ITEM_BUY_END = "<!-- ITEM_BUY_END -->"
ITEM_SPECS_START = "<!-- ITEM_SPECS_START -->"
ITEM_SPECS_END = "<!-- ITEM_SPECS_END -->"
ITEM_SERVICE_START = "<!-- ITEM_SERVICE_START -->"
ITEM_SERVICE_END = "<!-- ITEM_SERVICE_END -->"
ITEM_INCLUDES_START = "<!-- ITEM_INCLUDES_START -->"
ITEM_INCLUDES_END = "<!-- ITEM_INCLUDES_END -->"
ITEM_FITS_START = "<!-- ITEM_FITS_START -->"
ITEM_FITS_END = "<!-- ITEM_FITS_END -->"

# Shipping markup applied to the UPS Zone 8 (worst-case) quote.
SHIP_MARKUP = 1.2


# ---------- Data IO ----------
def _load_json_list(path: str) -> list:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        print(f"⚠️  JSON parse error in {os.path.basename(path)}. Using empty list.")
        return []


def _save_json(path: str, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _data_files() -> list[str]:
    return [DATA_PATH, REPAIRS_PATH, SITE_PATH, SHOP_PATH]


def create_backup(label: str) -> str:
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{timestamp}-{slugify(label)[:40]}"
    backup_path = os.path.join(BACKUPS_DIR, name)

    i = 2
    while os.path.exists(backup_path):
        backup_path = os.path.join(BACKUPS_DIR, f"{name}-{i}")
        i += 1

    os.makedirs(backup_path, exist_ok=True)

    for src in _data_files():
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(backup_path, os.path.basename(src)))

    meta = {
        "label": label,
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    _save_json(os.path.join(backup_path, "meta.json"), meta)
    return os.path.basename(backup_path)


def list_backups() -> list[str]:
    if not os.path.isdir(BACKUPS_DIR):
        return []
    names = [n for n in os.listdir(BACKUPS_DIR) if os.path.isdir(os.path.join(BACKUPS_DIR, n))]
    names.sort(reverse=True)
    return names


def restore_backup(name: str) -> bool:
    backup_path = os.path.join(BACKUPS_DIR, name)
    if not os.path.isdir(backup_path):
        return False

    for dst in _data_files():
        src = os.path.join(backup_path, os.path.basename(dst))
        if os.path.exists(src):
            shutil.copy2(src, dst)
    return True


def create_backup_note(label: str):
    backup_name = create_backup(label)
    print(f"🗂 Backup saved: .backups/{backup_name}")


def run_git(args: list[str]) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", "git is not installed or not available in PATH"


def publish_to_github():
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        print("This folder is not a git repository.")
        return

    rc, remote, err = run_git(["remote", "get-url", "origin"])
    if rc != 0 or not remote:
        print("Git remote 'origin' is not configured.")
        if err:
            print(err)
        return

    rc, branch, err = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if rc != 0 or not branch:
        print("Could not detect current git branch.")
        if err:
            print(err)
        return

    rc, status, err = run_git(["status", "--porcelain"])
    if rc != 0:
        print("Could not read git status.")
        if err:
            print(err)
        return

    print(f"\nRemote: {remote}")
    print(f"Branch: {branch}")

    if not status:
        print("No local file changes to commit.")
        if not prompt_yes_no("Push anyway? (y/n)", default="n"):
            print("Cancelled.")
            return
    else:
        print("Detected local changes.")

    if not prompt_yes_no("Publish all changes to GitHub now? (y/n)", default="n"):
        print("Cancelled.")
        return

    msg_default = f"site update {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    commit_message = prompt("Commit message", default=msg_default, optional=True)

    rc, out, err = run_git(["add", "-A"])
    if rc != 0:
        print("git add failed.")
        if err:
            print(err)
        return

    rc, out, err = run_git(["commit", "-m", commit_message])
    commit_created = rc == 0
    if not commit_created:
        combined = f"{out}\n{err}".strip().lower()
        if "nothing to commit" in combined:
            print("No new commit created (nothing to commit).")
        else:
            print("git commit failed.")
            if out:
                print(out)
            if err:
                print(err)
            return
    else:
        print("Commit created.")

    rc, out, err = run_git(["push", "origin", branch])
    if rc != 0:
        print("git push failed.")
        if out:
            print(out)
        if err:
            print(err)

        combined = f"{out}\n{err}".lower()
        if "password authentication is not supported" in combined:
            print("Tip: GitHub no longer accepts account passwords over HTTPS.")
            print("Use SSH remote (git@github.com:owner/repo.git) or use a Personal Access Token.")
        elif "permission denied (publickey)" in combined:
            print("Tip: SSH key is missing in GitHub account. Add ~/.ssh/id_ed25519.pub to GitHub SSH keys.")
        elif "non-fast-forward" in combined or "fetch first" in combined:
            print("Tip: Remote has newer commits. Run: git pull --rebase origin main, then push again.")
        else:
            print("Tip: make sure git auth is set up (SSH key or GitHub token).")
        return

    print("\n✅ Published to GitHub successfully.")


def publish_to_github_noninteractive(commit_message: str | None = None) -> tuple[bool, str]:
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        return False, "This folder is not a git repository."

    rc, remote, err = run_git(["remote", "get-url", "origin"])
    if rc != 0 or not remote:
        return False, f"Git remote 'origin' is not configured. {err}".strip()

    rc, branch, err = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if rc != 0 or not branch:
        return False, f"Could not detect current branch. {err}".strip()

    rc, status, err = run_git(["status", "--porcelain"])
    if rc != 0:
        return False, f"Could not read git status. {err}".strip()

    if not status:
        rc, out, err = run_git(["push", "origin", branch])
        if rc == 0:
            return True, f"No local changes. Remote is up to date on {branch}."
        return False, f"git push failed. {out} {err}".strip()

    message = commit_message or f"site update {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    rc, out, err = run_git(["add", "-A"])
    if rc != 0:
        return False, f"git add failed. {err}".strip()

    rc, out, err = run_git(["commit", "-m", message])
    if rc != 0:
        combined = f"{out}\n{err}".strip().lower()
        if "nothing to commit" not in combined:
            return False, f"git commit failed. {out} {err}".strip()

    rc, out, err = run_git(["push", "origin", branch])
    if rc != 0:
        combined = f"{out}\n{err}".lower()
        if "non-fast-forward" in combined or "fetch first" in combined:
            return False, "git push failed (remote ahead). Run sync flow: git pull --rebase origin main, then push."
        if "password authentication is not supported" in combined:
            return False, "git push failed: use SSH key or PAT instead of password auth."
        if "permission denied (publickey)" in combined:
            return False, "git push failed: SSH key not accepted by GitHub account."
        return False, f"git push failed. {out} {err}".strip()

    return True, f"Published to GitHub ({branch})."


def _split_csv(text: str) -> list[str]:
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


def _split_lines(text: str) -> list[str]:
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def _links_to_lines(links: list[dict]) -> str:
    rows = []
    for link in links or []:
        label = (link.get("label") or "Link").strip()
        url = (link.get("url") or "").strip()
        if url:
            rows.append(f"{label}|{url}")
    return "\n".join(rows)


def _links_from_lines(text: str) -> list[dict]:
    rows = _split_lines(text)
    links = []
    for row in rows:
        if "|" in row:
            label, url = row.split("|", 1)
            label = label.strip() or "Link"
            url = url.strip()
        else:
            label = "Link"
            url = row.strip()
        if url:
            links.append({"label": label, "url": url})
    return links


def _safe_index(value: str, total: int) -> int:
    if not value or not value.isdigit():
        return -1
    idx = int(value)
    if idx < 0 or idx >= total:
        return -1
    return idx


def resolve_image_input(image_value: str, title: str) -> str:
    value = (image_value or "").strip().strip('"')
    if not value:
        return ""

    if value.startswith("http://") or value.startswith("https://"):
        return value

    if os.path.isfile(value):
        return copy_image_into_site(value, title)

    root_relative = os.path.join(ROOT, value)
    if os.path.isfile(root_relative):
        return value.replace("\\", "/")

    return value


_ADMIN_CSS = """
:root {
  --bg: #0f0f0f;
  --surface: #1a1a1a;
  --surface2: #242424;
  --border: #2e2e2e;
  --border-light: #3a3a3a;
  --text: #e8e4dc;
  --text-muted: #7a7570;
  --text-dim: #4a4540;
  --accent: #d4a847;
  --accent-dim: #a07830;
  --accent-bg: rgba(212,168,71,0.08);
  --red: #c0392b;
  --red-bg: rgba(192,57,43,0.12);
  --green: #2ecc71;
  --green-bg: rgba(46,204,113,0.10);
  --blue: #3b82f6;
  --blue-bg: rgba(59,130,246,0.10);
  --radius: 6px;
  --radius-lg: 10px;
  --shadow: 0 2px 12px rgba(0,0,0,0.4);
  font-size: 15px;
}
*, *::before, *::after { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: 'IBM Plex Mono', 'Courier New', monospace;
  min-height: 100vh;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── HEADER ── */
.admin-header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 20px;
  height: 56px;
  position: sticky;
  top: 0;
  z-index: 100;
}
.admin-logo {
  font-size: 16px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: 0.04em;
  white-space: nowrap;
  margin-right: 8px;
}
.admin-logo span { color: var(--text-muted); font-weight: 400; }

/* ── NAV TABS ── */
.admin-nav { display: flex; gap: 2px; flex: 1; overflow-x: auto; }
.nav-tab {
  padding: 0 16px;
  height: 56px;
  display: flex;
  align-items: center;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  border: none;
  background: none;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  white-space: nowrap;
  transition: color 0.15s, border-color 0.15s;
  text-decoration: none;
  letter-spacing: 0.03em;
}
.nav-tab:hover { color: var(--text); text-decoration: none; }
.nav-tab.active { color: var(--accent); border-bottom-color: var(--accent); }

.header-actions { display: flex; gap: 8px; margin-left: auto; flex-shrink: 0; }

/* ── LAYOUT ── */
.admin-wrap { max-width: 1200px; margin: 0 auto; padding: 28px 24px; }
.page-title { font-size: 20px; font-weight: 700; color: var(--text); margin: 0 0 24px; letter-spacing: 0.02em; }
.page-title small { font-size: 13px; color: var(--text-muted); font-weight: 400; margin-left: 10px; }

/* ── TOAST ── */
.toast {
  background: var(--surface2);
  border: 1px solid var(--border-light);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius);
  padding: 12px 16px;
  font-size: 13px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  animation: slideIn 0.2s ease;
}
.toast.error { border-left-color: var(--red); }
@keyframes slideIn { from { opacity:0; transform: translateY(-6px); } to { opacity:1; transform: none; } }

/* ── GRID ── */
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.three-col { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
@media (max-width: 900px) { .two-col, .three-col { grid-template-columns: 1fr; } }

/* ── CARD ── */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px;
}
.card-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin: 0 0 16px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

/* ── STAT CARDS ── */
.stat-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
@media (max-width: 700px) { .stat-row { grid-template-columns: repeat(2, 1fr); } }
.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px 20px;
}
.stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; }
.stat-value { font-size: 28px; font-weight: 700; color: var(--accent); line-height: 1; }
.stat-sub { font-size: 12px; color: var(--text-dim); margin-top: 4px; }

/* ── FORMS ── */
.form-group { margin-bottom: 14px; }
.form-group:last-child { margin-bottom: 0; }
label { display: block; font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 5px; }
input[type=text], input[type=date], input[type=email], input[type=url], textarea, select {
  width: 100%;
  background: var(--surface2);
  border: 1px solid var(--border-light);
  border-radius: var(--radius);
  color: var(--text);
  padding: 9px 12px;
  font-family: inherit;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
  appearance: none;
}
input:focus, textarea:focus, select:focus { border-color: var(--accent); }
textarea { min-height: 90px; resize: vertical; }
select { cursor: pointer; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%237a7570' d='M1 1l5 5 5-5'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 12px center; padding-right: 36px; }
.hint { font-size: 11px; color: var(--text-dim); margin-top: 4px; }

/* ── BUTTONS ── */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 18px;
  border: none;
  border-radius: var(--radius);
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
  text-decoration: none;
  letter-spacing: 0.03em;
  white-space: nowrap;
}
.btn:hover { opacity: 0.85; text-decoration: none; }
.btn:active { transform: scale(0.98); }
.btn-primary { background: var(--accent); color: #111; }
.btn-secondary { background: var(--surface2); color: var(--text); border: 1px solid var(--border-light); }
.btn-danger { background: var(--red-bg); color: #e57373; border: 1px solid rgba(192,57,43,0.3); }
.btn-ghost { background: transparent; color: var(--text-muted); border: 1px solid var(--border); padding: 6px 12px; font-size: 12px; }
.btn-ghost:hover { color: var(--text); border-color: var(--border-light); }
.btn-sm { padding: 5px 10px; font-size: 12px; }
.btn-publish { background: var(--green-bg); color: var(--green); border: 1px solid rgba(46,204,113,0.25); }
.btn-rebuild { background: var(--blue-bg); color: #93c5fd; border: 1px solid rgba(59,130,246,0.25); }
.actions-row { display: flex; gap: 8px; flex-wrap: wrap; align-items: flex-end; }
.publish-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.publish-row input { flex: 1; min-width: 200px; }

/* ── ENTRY LIST ── */
.entry-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
.entry-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius);
  background: var(--surface2);
  border: 1px solid transparent;
  transition: border-color 0.15s;
}
.entry-item:hover { border-color: var(--border-light); }
.entry-num { font-size: 11px; color: var(--text-dim); width: 18px; flex-shrink: 0; text-align: right; }
.entry-title { font-size: 14px; color: var(--text); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.entry-meta { font-size: 11px; color: var(--text-dim); flex-shrink: 0; }
.entry-actions { display: flex; gap: 4px; flex-shrink: 0; }
.tag-badge {
  display: inline-block;
  background: var(--surface2);
  border: 1px solid var(--border-light);
  border-radius: 3px;
  padding: 1px 6px;
  font-size: 11px;
  color: var(--text-muted);
}
.status-badge {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 3px;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.status-complete { background: var(--green-bg); color: var(--green); }
.status-progress { background: var(--blue-bg); color: #93c5fd; }
.status-fixed { background: var(--green-bg); color: var(--green); }
.status-other { background: var(--surface2); color: var(--text-muted); }

/* ── SECTION HEADER ── */
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.section-label { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.1em; }
.empty-state { padding: 24px; text-align: center; color: var(--text-dim); font-size: 13px; border: 1px dashed var(--border); border-radius: var(--radius); }

/* ── BACK LINK ── */
.back-link { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-muted); margin-bottom: 20px; }
.back-link:hover { color: var(--text); text-decoration: none; }
.divider { border: none; border-top: 1px solid var(--border); margin: 20px 0; }
"""

_ADMIN_FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&display=swap">'

def _status_badge(status: str) -> str:
    s = (status or "").strip()
    sl = s.lower()
    if "complete" in sl or "done" in sl:
        cls = "status-complete"
    elif "progress" in sl or "wip" in sl:
        cls = "status-progress"
    elif "fixed" in sl or "resolved" in sl:
        cls = "status-fixed"
    else:
        cls = "status-other"
    return f'<span class="status-badge {cls}">{html.escape(s)}</span>'


def _web_layout(title: str, body: str, message: str = "", active_tab: str = "dashboard") -> str:
    msg_is_error = any(w in message.lower() for w in ["fail", "error", "invalid", "required"])
    message_html = ""
    if message:
        cls = "toast error" if msg_is_error else "toast"
        icon = "✗" if msg_is_error else "✓"
        message_html = f'<div class="{cls}">{icon} {html.escape(message)}</div>'

    tabs = [
        ("dashboard", "/", "Dashboard"),
        ("shop", "/?tab=shop", "Shop"),
        ("add-item", "/?tab=add-item", "Add Item"),
        ("add-build", "/?tab=add-build", "Add Build"),
        ("add-repair", "/?tab=add-repair", "Add Repair"),
        ("site", "/?tab=site", "Site Settings"),
    ]
    nav_html = "\n".join(
        f'<a href="{url}" class="nav-tab{" active" if key == active_tab else ""}">{label}</a>'
        for key, url, label in tabs
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)} - RudiMakes Admin</title>
  {_ADMIN_FONTS}
  <style>{_ADMIN_CSS}</style>
</head>
<body>
  <header class="admin-header">
    <div class="admin-logo">RUDI<span>MAKES</span></div>
    <nav class="admin-nav">{nav_html}</nav>
  </header>
  <div class="admin-wrap">
    {message_html}
    {body}
  </div>
  <script>
    // Auto-dismiss toast after 4s
    const t = document.querySelector('.toast');
    if (t) setTimeout(() => t.style.display='none', 4000);
    // Tab switching via hash/query
    const params = new URLSearchParams(location.search);
    const tab = params.get('tab');
    if (tab) {{
      document.querySelectorAll('.tab-panel').forEach(p => p.style.display='none');
      const target = document.getElementById('tab-' + tab);
      if (target) target.style.display='block';
    }}
  </script>
</body>
</html>"""


def start_web_ui(host: str = "127.0.0.1", port: int = 8081):
    def parse_form(handler: BaseHTTPRequestHandler) -> dict[str, str]:
        length = int(handler.headers.get("Content-Length", "0") or "0")
        raw = handler.rfile.read(length).decode("utf-8") if length > 0 else ""
        parsed = parse_qs(raw, keep_blank_values=True)
        # Keep every value for multi-selects under a "<name>[]" key alongside the scalar.
        out = {k: (v[0] if v else "") for k, v in parsed.items()}
        for k, v in parsed.items():
            out[f"{k}[]"] = v
        return out

    class AdminHandler(BaseHTTPRequestHandler):
        def _send_html(self, content: str, status: int = 200):
            data = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _redirect(self, path: str, msg: str = ""):
            target = path
            if msg:
                sep = "&" if "?" in target else "?"
                target = f"{target}{sep}{urlencode({'msg': msg})}"
            self.send_response(303)
            self.send_header("Location", target)
            self.end_headers()

        def _shop_rows(self, shop: dict) -> str:
            items = shop.get("items", [])
            if not items:
                return '<div class="empty-state">Nothing listed yet - add one in the Add Item tab.</div>'
            cmap = collection_map(shop)
            rows = []
            for i, it in enumerate(items):
                t = html.escape(it.get("title") or "Untitled")
                sku = html.escape(it.get("sku") or "")
                state = item_state(it)
                badge_cls = {"draft": "status-other", "sold_out": "status-other",
                             "low": "status-progress", "in_stock": "status-complete"}[state]
                badge_txt = {"draft": "DRAFT", "sold_out": "SOLD OUT",
                             "low": f"LOW ({it.get('stock', 0)})", "in_stock": f"IN STOCK ({it.get('stock', 0)})"}[state]
                price = fmt_price(it.get("price")) or "no price"
                cols = html.escape(", ".join(
                    (cmap.get(s) or {}).get("title", s) for s in (it.get("collections") or [])))
                warn = ""
                if item_needs_payment_link(it):
                    warn = '<span class="entry-meta" style="color:#f0b429">no buy link</span>'
                rows.append(f"""<li class="entry-item">
  <span class="entry-num">{sku}</span>
  <span class="entry-title">{t}</span>
  <span class="entry-meta">{price}</span>
  <span class="entry-meta">{cols}</span>
  {warn}
  <span class="status-badge {badge_cls}">{badge_txt}</span>
  <span class="entry-actions">
    <a href="/shop/edit?idx={i}" class="btn btn-ghost btn-sm">Edit</a>
    <form method="post" action="/shop/sold" style="margin:0">
      <input type="hidden" name="idx" value="{i}" />
      <button type="submit" class="btn btn-ghost btn-sm" onclick="return confirm('Mark one sold?')">Sold</button>
    </form>
    <form method="post" action="/shop/stock" style="margin:0;display:flex;gap:4px">
      <input type="hidden" name="idx" value="{i}" />
      <input type="number" name="stock" min="0" value="{int(it.get('stock', 0) or 0)}"
             style="width:64px;padding:4px 6px" />
      <button type="submit" class="btn btn-ghost btn-sm">Set</button>
    </form>
    <form method="post" action="/shop/delete" style="margin:0">
      <input type="hidden" name="idx" value="{i}" />
      <button type="submit" class="btn btn-danger btn-sm" onclick="return confirm('Delete this listing?')">Del</button>
    </form>
  </span>
</li>""")
            return f'<ul class="entry-list">{"".join(rows)}</ul>'

        def _collection_options(self, shop: dict, selected=None) -> str:
            selected = set(selected or [])
            return "".join(
                f'<option value="{html.escape(c.get("slug", ""))}"'
                f'{" selected" if c.get("slug") in selected else ""}>'
                f'{html.escape(c.get("title", ""))}</option>'
                for c in sorted_collections(shop)
            )

        def _render_shop_edit(self, shop: dict, idx: int, message: str = ""):
            if idx < 0:
                self._redirect("/?tab=shop", "Invalid item selection")
                return
            it = shop["items"][idx]
            ship = it.get("shipping") or {}
            e = lambda v: html.escape(str(v if v is not None else ""), quote=True)  # noqa: E731
            state = item_state(it)
            coll_opts = self._collection_options(shop, it.get("collections"))

            cover_note = f'<div class="hint">Current: {e(it.get("cover_image")) or "none"}</div>'
            gallery_note = f'<div class="hint">{len(it.get("images") or [])} extra photo(s) - use the CLI to change these.</div>'

            body = f"""
<div class="card" style="max-width:680px">
  <div class="section-header">
    <div class="card-title" style="margin:0;border:none;padding:0">
      {e(it.get('sku'))} &middot; {e(it.get('title'))}
    </div>
    <a href="/?tab=shop" class="btn btn-ghost btn-sm">&larr; Back</a>
  </div>
  <hr class="divider" style="margin:12px 0" />
  <form method="post" action="/shop/save">
    <input type="hidden" name="idx" value="{idx}" />
    <div class="two-col">
      <div class="form-group"><label>Title *</label>
        <input name="title" required value="{e(it.get('title'))}" /></div>
      <div class="form-group"><label>Type</label>
        <select name="item_type">
          <option value="gear"{' selected' if it.get('item_type') == 'gear' else ''}>Gear (one-of-a-kind)</option>
          <option value="part"{' selected' if it.get('item_type') == 'part' else ''}>Part (restockable)</option>
          <option value="kit"{' selected' if it.get('item_type') == 'kit' else ''}>Mod kit (restockable)</option>
        </select></div>
    </div>
    <div class="form-group"><label>Subtitle</label>
      <input name="subtitle" value="{e(it.get('subtitle'))}" /></div>
    <div class="two-col">
      <div class="form-group"><label>Price ($)</label>
        <input name="price" type="number" step="0.01" min="0" value="{e(it.get('price'))}" /></div>
      <div class="form-group"><label>Quantity in stock</label>
        <input name="stock" type="number" min="0" value="{int(it.get('stock', 0) or 0)}" /></div>
    </div>
    <div class="form-group"><label>Collections</label>
      <select name="collections" multiple size="5">{coll_opts}</select></div>
    <div class="two-col">
      <div class="form-group"><label>Brand</label>
        <input name="brand" value="{e(it.get('brand'))}" /></div>
      <div class="form-group"><label>Manufacturer part number</label>
        <input name="mpn" value="{e(it.get('mpn'))}" /></div>
    </div>
    <div class="two-col">
      <div class="form-group"><label>Year</label>
        <input name="year" value="{e(it.get('year'))}" /></div>
      <div class="form-group"><label>Condition</label>
        <input name="condition" value="{e(it.get('condition'))}" /></div>
    </div>
    <div class="form-group"><label>Fits models</label>
      <input name="fits_models" value="{e(', '.join(it.get('fits_models') or []))}" />
      <div class="hint">Comma separated.</div></div>
    <div class="form-group"><label>Description</label>
      <textarea name="description">{e(it.get('description'))}</textarea></div>
    <div class="form-group"><label>Bullets</label>
      <textarea name="bullets" style="min-height:70px">{e(chr(10).join(it.get('bullets') or []))}</textarea></div>
    <div class="form-group"><label>What you serviced</label>
      <textarea name="service_notes" style="min-height:70px">{e(it.get('service_notes'))}</textarea></div>
    <div class="form-group"><label>What's included</label>
      <textarea name="includes" style="min-height:60px">{e(chr(10).join(it.get('includes') or []))}</textarea></div>
    <div class="form-group"><label>Tags</label>
      <input name="tags" value="{e(', '.join(it.get('tags') or []))}" /></div>
    <div class="form-group"><label>Replace cover photo</label>
      <input name="cover_image_path" placeholder="Leave blank to keep current" />
      {cover_note}{gallery_note}</div>
    <hr class="divider" style="margin:16px 0" />
    <div class="card-title" style="font-size:14px">Shipping</div>
    <div class="two-col">
      <div class="form-group"><label>Weight (lb)</label>
        <input name="weight_lb" type="number" step="0.1" min="0" value="{e(ship.get('weight_lb'))}" /></div>
      <div class="form-group"><label>Box size (in)</label>
        <input name="box_in" value="{e(ship.get('box_in'))}" /></div>
    </div>
    <div class="two-col">
      <div class="form-group"><label>UPS Zone 8 quote ($)</label>
        <input name="ups_zone8_quote" type="number" step="0.01" min="0" value="{e(ship.get('ups_zone8_quote'))}" /></div>
      <div class="form-group"><label>Shipping to charge ($)</label>
        <input name="ship_price" type="number" step="0.01" min="0" value="{e(ship.get('ship_price'))}" />
        <div class="hint">Blank recomputes from the quote.</div></div>
    </div>
    <div class="form-group"><label>
      <input type="checkbox" name="local_pickup" value="1"{' checked' if ship.get('local_pickup', True) else ''} />
      Offer free local pickup</label></div>
    <hr class="divider" style="margin:16px 0" />
    <div class="card-title" style="font-size:14px">Payment Links</div>
    <div class="form-group"><label>Stripe Payment Link URL</label>
      <input name="stripe_url" value="{e(it.get('stripe_url'))}" /></div>
    <div class="form-group"><label>PayPal hosted button ID</label>
      <input name="paypal_button_id" value="{e(it.get('paypal_button_id'))}" /></div>
    <div class="form-group"><label>
      <input type="checkbox" name="published" value="1"{' checked' if it.get('status') != 'draft' else ''} />
      Published (uncheck to hide from the site)</label>
      <div class="hint">Currently: {state.replace('_', ' ')}</div></div>
    <button type="submit" class="btn btn-primary">Save Item</button>
  </form>
</div>"""
            self._send_html(_web_layout(f"Edit {it.get('title', 'Item')}", body, message, "shop"))

        def _render_home(self, message: str = "", active_tab: str = "dashboard"):
            projects = load_projects()
            repairs = load_repairs()
            site = load_site()
            shop = load_shop()

            n_builds = len(projects)
            n_repairs = len(repairs)
            n_complete = sum(1 for p in projects if "complete" in (p.get("status") or "").lower())
            n_fixed = sum(1 for r in repairs if "fixed" in (r.get("status") or "").lower())

            if projects:
                p_rows = []
                for i, p in enumerate(projects):
                    t = html.escape(p.get("title") or "Untitled")
                    st = p.get("status", "")
                    tags = " ".join(f'<span class="tag-badge">{html.escape(tg)}</span>' for tg in (p.get("tags") or [])[:3])
                    p_rows.append(f"""<li class="entry-item">
  <span class="entry-num">{i+1}</span>
  <span class="entry-title">{t}</span>
  {tags}
  {_status_badge(st)}
  <span class="entry-actions">
    <a href="/project/edit?idx={i}" class="btn btn-ghost btn-sm">Edit</a>
    <a href="/story?idx={i}" class="btn btn-ghost btn-sm">Story</a>
    <form method="post" action="/projects/delete" style="margin:0">
      <input type="hidden" name="idx" value="{i}" />
      <button type="submit" class="btn btn-danger btn-sm" onclick="return confirm('Delete this build?')">Del</button>
    </form>
  </span>
</li>""")
                project_list = f'<ul class="entry-list">{"".join(p_rows)}</ul>'
            else:
                project_list = '<div class="empty-state">No builds yet - add one in the Add Build tab.</div>'

            if repairs:
                r_rows = []
                for i, r in enumerate(repairs):
                    t = html.escape(r.get("title") or "Untitled Repair")
                    date = html.escape(r.get("date") or "")
                    st = r.get("status", "")
                    device = html.escape(r.get("device") or "")
                    r_rows.append(f"""<li class="entry-item">
  <span class="entry-num">{i+1}</span>
  <span class="entry-title">{t}</span>
  <span class="entry-meta">{device}</span>
  <span class="entry-meta">{date}</span>
  {_status_badge(st)}
  <span class="entry-actions">
    <a href="/repair/edit?idx={i}" class="btn btn-ghost btn-sm">Edit</a>
    <form method="post" action="/repairs/delete" style="margin:0">
      <input type="hidden" name="idx" value="{i}" />
      <button type="submit" class="btn btn-danger btn-sm" onclick="return confirm('Delete this repair?')">Del</button>
    </form>
  </span>
</li>""")
                repair_list = f'<ul class="entry-list">{"".join(r_rows)}</ul>'
            else:
                repair_list = '<div class="empty-state">No repairs yet - add one in the Add Repair tab.</div>'

            shop_items = shop.get("items", [])
            n_items = len(shop_items)
            n_live = sum(1 for i in shop_items if item_state(i) in ("in_stock", "low"))
            n_nolink = sum(1 for i in shop_items if item_needs_payment_link(i))
            shop_list = self._shop_rows(shop)
            coll_opts = self._collection_options(shop)
            nolink_warn = ""
            if n_nolink:
                nolink_warn = (f'<div class="hint" style="color:#f0b429;margin-bottom:8px">'
                               f'{n_nolink} listing(s) have no Stripe or PayPal link - they show '
                               f'"email for price" instead of Buy buttons.</div>')

            body = f"""
<div class="stat-row">
  <div class="stat-card">
    <div class="stat-label">Builds</div>
    <div class="stat-value">{n_builds}</div>
    <div class="stat-sub">{n_complete} complete</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Repairs</div>
    <div class="stat-value">{n_repairs}</div>
    <div class="stat-sub">{n_fixed} fixed</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Site</div>
    <div class="stat-value" style="font-size:18px;padding-top:4px">{html.escape(site.get('name') or 'RudiMakes')}</div>
    <div class="stat-sub">{html.escape(site.get('tagline') or '-')}</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Quick Actions</div>
    <div style="margin-top:8px;display:flex;flex-direction:column;gap:6px">
      <form method="post" action="/actions/rebuild">
        <button type="submit" class="btn btn-rebuild btn-sm" style="width:100%">⟳ Rebuild Site</button>
      </form>
      <form method="post" action="/actions/publish">
        <input type="hidden" name="commit_message" value="site update" />
        <button type="submit" class="btn btn-publish btn-sm" style="width:100%">↑ Publish GitHub</button>
      </form>
    </div>
  </div>
</div>

<div id="tab-dashboard" class="tab-panel">
  <div class="two-col">
    <div class="card">
      <div class="section-header">
        <div class="card-title" style="margin:0;border:none;padding:0">Builds ({n_builds})</div>
        <a href="/?tab=add-build" class="btn btn-primary btn-sm">+ Add Build</a>
      </div>
      <hr class="divider" style="margin:12px 0" />
      {project_list}
    </div>
    <div class="card">
      <div class="section-header">
        <div class="card-title" style="margin:0;border:none;padding:0">Repairs ({n_repairs})</div>
        <a href="/?tab=add-repair" class="btn btn-primary btn-sm">+ Add Repair</a>
      </div>
      <hr class="divider" style="margin:12px 0" />
      {repair_list}
    </div>
  </div>
  <div class="card" style="margin-top:20px">
    <div class="card-title">Publish Changes to GitHub</div>
    <form method="post" action="/actions/publish">
      <div class="publish-row">
        <input type="text" name="commit_message" placeholder="Commit message (optional - leave blank for auto)" />
        <button type="submit" class="btn btn-publish">↑ Publish</button>
      </div>
    </form>
  </div>
</div>

<div id="tab-shop" class="tab-panel" style="display:none">
  <div class="card">
    <div class="section-header">
      <div class="card-title" style="margin:0;border:none;padding:0">Inventory ({n_items} listed, {n_live} in stock)</div>
      <a href="/?tab=add-item" class="btn btn-primary btn-sm">+ Add Item</a>
    </div>
    <hr class="divider" style="margin:12px 0" />
    {nolink_warn}
    {shop_list}
  </div>
  <div class="card" style="margin-top:20px">
    <div class="card-title">When Something Sells</div>
    <div class="hint">
      1. Hit <strong>Sold</strong> above (drops stock by one and rebuilds the page).<br />
      2. If it hit zero, go deactivate the <strong>other</strong> processor's button so it can't sell
         twice - Stripe: Payment Links &rarr; deactivate. PayPal: PayPal Buttons &rarr; remove.<br />
      3. Publish, then pack it, ship it, and email the tracking number.
    </div>
  </div>
</div>

<div id="tab-add-item" class="tab-panel" style="display:none">
  <div class="card" style="max-width:680px">
    <div class="card-title">Add Shop Item</div>
    <form method="post" action="/shop/add">
      <div class="two-col">
        <div class="form-group">
          <label>Title *</label>
          <input name="title" required placeholder="e.g. Roland Juno-106 80017A Voice Chip" />
        </div>
        <div class="form-group">
          <label>Type</label>
          <select name="item_type">
            <option value="gear">Gear (one-of-a-kind)</option>
            <option value="part">Part (restockable)</option>
            <option value="kit">Mod kit (restockable)</option>
          </select>
        </div>
      </div>
      <div class="form-group">
        <label>Subtitle</label>
        <input name="subtitle" placeholder="One line - what makes it worth buying" />
      </div>
      <div class="two-col">
        <div class="form-group">
          <label>Price ($)</label>
          <input name="price" type="number" step="0.01" min="0" placeholder="36.99" />
        </div>
        <div class="form-group">
          <label>Quantity in stock</label>
          <input name="stock" type="number" min="0" value="1" />
        </div>
      </div>
      <div class="form-group">
        <label>Collections</label>
        <select name="collections" multiple size="5">{coll_opts}</select>
        <div class="hint">Ctrl-click (Cmd-click on Mac) to pick more than one.</div>
      </div>
      <div class="two-col">
        <div class="form-group">
          <label>Brand</label>
          <input name="brand" placeholder="Roland" />
        </div>
        <div class="form-group">
          <label>Manufacturer part number</label>
          <input name="mpn" placeholder="80017A" />
        </div>
      </div>
      <div class="two-col">
        <div class="form-group">
          <label>Year</label>
          <input name="year" placeholder="1984" />
        </div>
        <div class="form-group">
          <label>Condition</label>
          <input name="condition" placeholder="Excellent / New" />
        </div>
      </div>
      <div class="form-group">
        <label>Fits models</label>
        <input name="fits_models" placeholder="Juno-106, Juno-106S, HS-60" />
        <div class="hint">Comma separated. This is what people actually search for.</div>
      </div>
      <div class="form-group">
        <label>Description</label>
        <textarea name="description" placeholder="What it is, what shape it's in, what you did to it"></textarea>
      </div>
      <div class="form-group">
        <label>Bullets</label>
        <textarea name="bullets" style="min-height:70px" placeholder="One per line&#10;Recapped power supply&#10;Six new voice chips"></textarea>
      </div>
      <div class="form-group">
        <label>What you serviced</label>
        <textarea name="service_notes" style="min-height:70px" placeholder="Bench notes - the thing that separates you from a Reverb listing"></textarea>
      </div>
      <div class="form-group">
        <label>What's included</label>
        <textarea name="includes" style="min-height:60px" placeholder="One per line&#10;Power cable&#10;Original manual"></textarea>
      </div>
      <div class="form-group">
        <label>Tags</label>
        <input name="tags" placeholder="synth, roland, serviced" />
      </div>
      <div class="form-group">
        <label>Cover photo path</label>
        <input name="cover_image_path" placeholder="C:\\path\\to\\photo.jpg" />
        <div class="hint">Copied into images/shop/ automatically.</div>
      </div>
      <hr class="divider" style="margin:16px 0" />
      <div class="card-title" style="font-size:14px">Shipping</div>
      <div class="hint" style="margin-bottom:10px">
        Box it, weigh it, then get a UPS quote from Indianapolis to a west-coast ZIP (Zone 8 -
        the worst case). Enter that number and the {SHIP_MARKUP}x markup is applied for you.
      </div>
      <div class="two-col">
        <div class="form-group">
          <label>Weight (lb)</label>
          <input name="weight_lb" type="number" step="0.1" min="0" placeholder="32" />
        </div>
        <div class="form-group">
          <label>Box size (in)</label>
          <input name="box_in" placeholder="34 x 18 x 10" />
        </div>
      </div>
      <div class="two-col">
        <div class="form-group">
          <label>UPS Zone 8 quote ($)</label>
          <input name="ups_zone8_quote" type="number" step="0.01" min="0" placeholder="78.40" />
        </div>
        <div class="form-group">
          <label>Shipping to charge ($)</label>
          <input name="ship_price" type="number" step="0.01" min="0" placeholder="blank = auto" />
        </div>
      </div>
      <div class="form-group">
        <label><input type="checkbox" name="local_pickup" value="1" checked /> Offer free local pickup</label>
      </div>
      <hr class="divider" style="margin:16px 0" />
      <div class="card-title" style="font-size:14px">Payment Links</div>
      <div class="hint" style="margin-bottom:10px">
        Leave both blank to save as a draft, then paste them in once you've made the links.
      </div>
      <div class="form-group">
        <label>Stripe Payment Link URL</label>
        <input name="stripe_url" placeholder="https://buy.stripe.com/..." />
      </div>
      <div class="form-group">
        <label>PayPal hosted button ID</label>
        <input name="paypal_button_id" placeholder="ABCD1234EFGH" />
      </div>
      <button type="submit" class="btn btn-primary">Add Item</button>
    </form>
  </div>
</div>

<div id="tab-add-build" class="tab-panel" style="display:none">
  <div class="card" style="max-width:680px">
    <div class="card-title">Add New Build</div>
    <form method="post" action="/projects/add">
      <div class="two-col">
        <div class="form-group">
          <label>Title *</label>
          <input name="title" required placeholder="e.g. Fender Bassman Restoration" />
        </div>
        <div class="form-group">
          <label>Status</label>
          <select name="status">
            <option>Complete</option><option>In Progress</option><option>Archived</option>
          </select>
        </div>
      </div>
      <div class="form-group">
        <label>Description</label>
        <textarea name="description" placeholder="Brief description of the build or project"></textarea>
      </div>
      <div class="form-group">
        <label>Bullets</label>
        <textarea name="bullets" style="min-height:70px" placeholder="One bullet point per line&#10;Replaced output transformer&#10;Recapped power supply"></textarea>
        <div class="hint">Each line becomes a bullet point on the project card.</div>
      </div>
      <div class="two-col">
        <div class="form-group">
          <label>Tags</label>
          <input name="tags" placeholder="amp, fender, restoration" />
          <div class="hint">Comma-separated</div>
        </div>
        <div class="form-group">
          <label>Cover Image</label>
          <input name="image_path" placeholder="images/photo.jpg or URL" />
        </div>
      </div>
      <div class="actions-row" style="margin-top:18px">
        <button type="submit" class="btn btn-primary">Add Build</button>
        <a href="/" class="btn btn-secondary">Cancel</a>
      </div>
    </form>
  </div>
</div>

<div id="tab-add-repair" class="tab-panel" style="display:none">
  <div class="card" style="max-width:680px">
    <div class="card-title">Add Repair / Troubleshooting Log</div>
    <form method="post" action="/repairs/add">
      <div class="two-col">
        <div class="form-group">
          <label>Title *</label>
          <input name="title" required placeholder="e.g. Moog Subsequent 37 - No Audio Output" />
        </div>
        <div class="form-group">
          <label>Device / Board</label>
          <input name="device" placeholder="e.g. Moog Subsequent 37" />
        </div>
      </div>
      <div class="two-col">
        <div class="form-group">
          <label>Date</label>
          <input type="date" name="date" value="{datetime.now().strftime('%Y-%m-%d')}" />
        </div>
        <div class="form-group">
          <label>Status</label>
          <input name="status" value="Fixed" placeholder="Fixed / In Progress / No Fault Found" />
        </div>
      </div>
      <div class="form-group">
        <label>Symptom</label>
        <textarea name="symptom" placeholder="What was the reported or observed problem?"></textarea>
      </div>
      <div class="form-group">
        <label>Diagnosis</label>
        <textarea name="diagnosis" placeholder="What did you find on the bench?"></textarea>
      </div>
      <div class="form-group">
        <label>Fix / What Worked</label>
        <textarea name="fix" placeholder="What you replaced, adjusted, or reworked"></textarea>
      </div>
      <div class="two-col">
        <div class="form-group">
          <label>Tags</label>
          <input name="tags" placeholder="synth, moog, audio" />
          <div class="hint">Comma-separated</div>
        </div>
        <div class="form-group">
          <label>Photo</label>
          <input name="image_path" placeholder="images/repair.jpg or URL" />
        </div>
      </div>
      <div class="form-group">
        <label>Extra Notes</label>
        <textarea name="notes" style="min-height:60px" placeholder="Anything else worth logging"></textarea>
      </div>
      <div class="actions-row" style="margin-top:18px">
        <button type="submit" class="btn btn-primary">Add Repair Log</button>
        <a href="/" class="btn btn-secondary">Cancel</a>
      </div>
    </form>
  </div>
</div>

<div id="tab-site" class="tab-panel" style="display:none">
  <div class="card" style="max-width:680px">
    <div class="card-title">Site Settings</div>
    <form method="post" action="/site/save">
      <div class="two-col">
        <div class="form-group">
          <label>Name</label>
          <input name="name" value="{html.escape(site.get('name',''))}" />
        </div>
        <div class="form-group">
          <label>Tagline</label>
          <input name="tagline" value="{html.escape(site.get('tagline',''))}" />
        </div>
      </div>
      <div class="form-group">
        <label>About Text</label>
        <textarea name="about_text">{html.escape(site.get('about_text',''))}</textarea>
      </div>
      <div class="form-group">
        <label>Build Log Note</label>
        <input name="build_log_note" value="{html.escape(site.get('build_log_note',''))}" />
      </div>
      <div class="two-col">
        <div class="form-group">
          <label>Email</label>
          <input name="email" value="{html.escape(site.get('email',''))}" />
        </div>
        <div class="form-group">
          <label>About Tags</label>
          <input name="tags" value="{html.escape(', '.join(site.get('tags') or []))}" />
          <div class="hint">Comma-separated</div>
        </div>
      </div>
      <div class="two-col">
        <div class="form-group">
          <label>Instagram URL</label>
          <input name="instagram_url" value="{html.escape(site.get('instagram_url',''))}" />
        </div>
        <div class="form-group">
          <label>YouTube URL</label>
          <input name="youtube_url" value="{html.escape(site.get('youtube_url',''))}" />
        </div>
      </div>
      <div class="actions-row" style="margin-top:18px">
        <button type="submit" class="btn btn-primary">Save Settings</button>
      </div>
    </form>
  </div>
</div>
"""
            self._send_html(_web_layout("Dashboard", body, message, active_tab))

        def _render_story(self, idx: int, message: str = ""):
            projects = load_projects()
            if idx < 0 or idx >= len(projects):
                self._redirect("/", "Invalid project selection")
                return

            project = projects[idx]
            steps = project.get("steps") or []

            if steps:
                s_rows = []
                for i, s in enumerate(steps):
                    t = html.escape(s.get("title") or f"Part {i+1}")
                    preview = html.escape((s.get("text") or "")[:80])
                    s_rows.append(f"""<li class="entry-item">
  <span class="entry-num">{i+1}</span>
  <span class="entry-title">{t}</span>
  <span class="entry-meta" style="font-size:12px;color:var(--text-dim)">{preview}{"…" if len(s.get("text",""))>80 else ""}</span>
  <span class="entry-actions">
    <a href="/story/edit?idx={idx}&step_idx={i}" class="btn btn-ghost btn-sm">Edit</a>
    <form method="post" action="/story/delete" style="margin:0">
      <input type="hidden" name="idx" value="{idx}" />
      <input type="hidden" name="step_idx" value="{i}" />
      <button type="submit" class="btn btn-danger btn-sm" onclick="return confirm('Delete section?')">Del</button>
    </form>
  </span>
</li>""")
                section_list = f'<ul class="entry-list">{"".join(s_rows)}</ul>'
            else:
                section_list = '<div class="empty-state">No story sections yet - add one below.</div>'

            body = f"""
<a href="/" class="back-link">← Dashboard</a>
<div class="two-col">
  <div class="card">
    <div class="section-header">
      <div class="card-title" style="margin:0;border:none;padding:0">Build Story: {html.escape(project.get('title','Untitled'))}</div>
      <form method="post" action="/story/clear" style="margin:0">
        <input type="hidden" name="idx" value="{idx}" />
        <button type="submit" class="btn btn-danger btn-sm" onclick="return confirm('Clear all sections?')">Clear All</button>
      </form>
    </div>
    <hr class="divider" style="margin:12px 0" />
    {section_list}
  </div>

  <div class="card">
    <div class="card-title">Add Story Section</div>
    <form method="post" action="/story/add">
      <input type="hidden" name="idx" value="{idx}" />
      <div class="form-group">
        <label>Section Title</label>
        <input name="title" placeholder="Part {len(steps)+1}" />
      </div>
      <div class="form-group">
        <label>Section Text</label>
        <textarea name="text" placeholder="Describe what happened in this part of the build..."></textarea>
      </div>
      <div class="form-group">
        <label>Image Path or URL</label>
        <input name="image_path" placeholder="images/build-step.jpg or URL" />
      </div>
      <div class="form-group">
        <label>Image Alt Text</label>
        <input name="alt" placeholder="Description of the image" />
      </div>
      <div class="actions-row" style="margin-top:14px">
        <button type="submit" class="btn btn-primary">Add Section</button>
      </div>
    </form>
  </div>
</div>
"""
            self._send_html(_web_layout(f"Story - {project.get('title','Build')}", body, message))

        def _render_project_edit(self, idx: int, message: str = ""):
            projects = load_projects()
            if idx < 0 or idx >= len(projects):
                self._redirect("/", "Invalid build selection")
                return

            p = projects[idx]
            status_value = p.get("status", "Complete")
            options = ["Complete", "In Progress", "Archived"]
            status_opts = "\n".join([
                f"<option {'selected' if status_value == opt else ''}>{opt}</option>" for opt in options
            ])

            body = f"""
<a href="/" class="back-link">← Dashboard</a>
<div class="card" style="max-width:720px">
  <div class="card-title">Edit Build: {html.escape(p.get('title','Untitled'))}</div>
  <form method="post" action="/projects/save">
    <input type="hidden" name="idx" value="{idx}" />
    <div class="two-col">
      <div class="form-group">
        <label>Title *</label>
        <input name="title" value="{html.escape(p.get('title',''))}" required />
      </div>
      <div class="form-group">
        <label>Status</label>
        <select name="status">{status_opts}</select>
      </div>
    </div>
    <div class="form-group">
      <label>Description</label>
      <textarea name="description">{html.escape(p.get('description',''))}</textarea>
    </div>
    <div class="form-group">
      <label>Bullets</label>
      <textarea name="bullets">{html.escape(chr(10).join(p.get('bullets') or []))}</textarea>
      <div class="hint">One bullet per line</div>
    </div>
    <div class="two-col">
      <div class="form-group">
        <label>Tags</label>
        <input name="tags" value="{html.escape(', '.join(p.get('tags') or []))}" />
        <div class="hint">Comma-separated</div>
      </div>
      <div class="form-group">
        <label>Cover Image</label>
        <input name="cover_image" value="{html.escape(p.get('cover_image') or p.get('image') or '')}" />
      </div>
    </div>
    <div class="form-group">
      <label>Alt Text</label>
      <input name="alt" value="{html.escape(p.get('alt') or p.get('title') or '')}" />
    </div>
    <div class="form-group">
      <label>Gallery Images</label>
      <textarea name="images">{html.escape(chr(10).join(p.get('images') or []))}</textarea>
      <div class="hint">One path or URL per line</div>
    </div>
    <div class="form-group">
      <label>Links</label>
      <textarea name="links">{html.escape(_links_to_lines(p.get('links') or []))}</textarea>
      <div class="hint">One per line: Label|https://url</div>
    </div>
    <div class="actions-row" style="margin-top:18px">
      <button type="submit" class="btn btn-primary">Save Build</button>
      <a href="/story?idx={idx}" class="btn btn-secondary">Edit Story Sections</a>
      <a href="/" class="btn btn-ghost">Cancel</a>
    </div>
  </form>
</div>
"""
            self._send_html(_web_layout(f"Edit Build - {p.get('title','')}", body, message))

        def _render_repair_edit(self, idx: int, message: str = ""):
            repairs = load_repairs()
            if idx < 0 or idx >= len(repairs):
                self._redirect("/", "Invalid repair selection")
                return

            r = repairs[idx]
            body = f"""
<a href="/" class="back-link">← Dashboard</a>
<div class="card" style="max-width:720px">
  <div class="card-title">Edit Repair: {html.escape(r.get('title','Untitled Repair'))}</div>
  <form method="post" action="/repairs/save">
    <input type="hidden" name="idx" value="{idx}" />
    <div class="two-col">
      <div class="form-group">
        <label>Title *</label>
        <input name="title" value="{html.escape(r.get('title',''))}" required />
      </div>
      <div class="form-group">
        <label>Device / Board</label>
        <input name="device" value="{html.escape(r.get('device',''))}" />
      </div>
    </div>
    <div class="two-col">
      <div class="form-group">
        <label>Date</label>
        <input type="date" name="date" value="{html.escape(r.get('date',''))}" />
      </div>
      <div class="form-group">
        <label>Status</label>
        <input name="status" value="{html.escape(r.get('status',''))}" />
      </div>
    </div>
    <div class="form-group">
      <label>Symptom</label>
      <textarea name="symptom">{html.escape(r.get('symptom',''))}</textarea>
    </div>
    <div class="form-group">
      <label>Diagnosis</label>
      <textarea name="diagnosis">{html.escape(r.get('diagnosis',''))}</textarea>
    </div>
    <div class="form-group">
      <label>Fix / What Worked</label>
      <textarea name="fix">{html.escape(r.get('fix',''))}</textarea>
    </div>
    <div class="form-group">
      <label>Notes</label>
      <textarea name="notes">{html.escape(r.get('notes',''))}</textarea>
    </div>
    <div class="two-col">
      <div class="form-group">
        <label>Tags</label>
        <input name="tags" value="{html.escape(', '.join(r.get('tags') or []))}" />
        <div class="hint">Comma-separated</div>
      </div>
      <div class="form-group">
        <label>Photo</label>
        <input name="image" value="{html.escape(r.get('image') or '')}" />
      </div>
    </div>
    <div class="form-group">
      <label>Alt Text</label>
      <input name="alt" value="{html.escape(r.get('alt') or r.get('title') or '')}" />
    </div>
    <div class="actions-row" style="margin-top:18px">
      <button type="submit" class="btn btn-primary">Save Repair</button>
      <a href="/" class="btn btn-ghost">Cancel</a>
    </div>
  </form>
</div>
"""
            self._send_html(_web_layout(f"Edit Repair - {r.get('title','')}", body, message))

        def _render_story_edit(self, idx: int, step_idx: int, message: str = ""):
            projects = load_projects()
            if idx < 0 or idx >= len(projects):
                self._redirect("/", "Invalid project selection")
                return
            steps = projects[idx].get("steps") or []
            if step_idx < 0 or step_idx >= len(steps):
                self._redirect(f"/story?idx={idx}", "Invalid section selection")
                return

            s = steps[step_idx]
            proj_title = html.escape(projects[idx].get("title", "Untitled"))
            body = f"""
<a href="/story?idx={idx}" class="back-link">← Story: {proj_title}</a>
<div class="card" style="max-width:680px">
  <div class="card-title">Edit Section {step_idx+1}: {html.escape(s.get('title',''))}</div>
  <form method="post" action="/story/save">
    <input type="hidden" name="idx" value="{idx}" />
    <input type="hidden" name="step_idx" value="{step_idx}" />
    <div class="form-group">
      <label>Section Title</label>
      <input name="title" value="{html.escape(s.get('title',''))}" />
    </div>
    <div class="form-group">
      <label>Section Text</label>
      <textarea name="text" style="min-height:140px">{html.escape(s.get('text',''))}</textarea>
    </div>
    <div class="two-col">
      <div class="form-group">
        <label>Image Path or URL</label>
        <input name="image" value="{html.escape(s.get('image',''))}" />
      </div>
      <div class="form-group">
        <label>Alt Text</label>
        <input name="alt" value="{html.escape(s.get('alt',''))}" />
      </div>
    </div>
    <div class="actions-row" style="margin-top:18px">
      <button type="submit" class="btn btn-primary">Save Section</button>
      <a href="/story?idx={idx}" class="btn btn-ghost">Cancel</a>
    </div>
  </form>
</div>
"""
            self._send_html(_web_layout("Edit Story Section", body, message))

        def do_GET(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            message = (query.get("msg") or [""])[0]

            if parsed.path == "/":
                active_tab = (query.get("tab") or ["dashboard"])[0]
                self._render_home(message, active_tab)
                return

            if parsed.path == "/story":
                idx_raw = (query.get("idx") or ["-1"])[0]
                idx = _safe_index(idx_raw, len(load_projects()))
                self._render_story(idx, message)
                return

            if parsed.path == "/project/edit":
                idx_raw = (query.get("idx") or ["-1"])[0]
                idx = _safe_index(idx_raw, len(load_projects()))
                self._render_project_edit(idx, message)
                return

            if parsed.path == "/repair/edit":
                idx_raw = (query.get("idx") or ["-1"])[0]
                idx = _safe_index(idx_raw, len(load_repairs()))
                self._render_repair_edit(idx, message)
                return

            if parsed.path == "/shop/edit":
                idx_raw = (query.get("idx") or ["-1"])[0]
                shop = load_shop()
                idx = _safe_index(idx_raw, len(shop.get("items", [])))
                self._render_shop_edit(shop, idx, message)
                return

            if parsed.path == "/story/edit":
                idx_raw = (query.get("idx") or ["-1"])[0]
                step_raw = (query.get("step_idx") or ["-1"])[0]
                projects = load_projects()
                idx = _safe_index(idx_raw, len(projects))
                steps_total = len(projects[idx].get("steps") or []) if idx >= 0 else 0
                step_idx = _safe_index(step_raw, steps_total)
                self._render_story_edit(idx, step_idx, message)
                return

            self._send_html(_web_layout("Not Found", "<div class='card'><h2>404</h2></div>"), status=404)

        def _shop_apply_form(self, it: dict, form: dict, shop: dict):
            """Shared field mapping for both the add and edit shop forms."""
            def num(key, default=0.0):
                raw = (form.get(key) or "").strip().lstrip("$")
                try:
                    return float(raw) if raw else default
                except ValueError:
                    return default

            title = (form.get("title") or "").strip()
            if title:
                it["title"] = title
            it["subtitle"] = (form.get("subtitle") or "").strip()
            kind = (form.get("item_type") or "gear").strip().lower()
            it["item_type"] = kind if kind in ("gear", "part", "kit") else "gear"
            it["collections"] = [s for s in (form.get("collections[]") or []) if s]
            it["brand"] = (form.get("brand") or "").strip()
            it["mpn"] = (form.get("mpn") or "").strip()
            it["year"] = (form.get("year") or "").strip()
            it["condition"] = (form.get("condition") or "").strip()
            it["fits_models"] = _split_csv(form.get("fits_models") or "")
            it["price"] = num("price")
            stock_raw = (form.get("stock") or "").strip()
            it["stock"] = int(stock_raw) if stock_raw.isdigit() else 0
            it["description"] = (form.get("description") or "").strip()
            it["bullets"] = _split_lines(form.get("bullets") or "")
            it["service_notes"] = (form.get("service_notes") or "").strip()
            it["includes"] = _split_lines(form.get("includes") or "")
            it["tags"] = _split_csv(form.get("tags") or "")

            cover_path = (form.get("cover_image_path") or "").strip()
            if cover_path:
                try:
                    it["cover_image"] = copy_image_into_site(cover_path, it.get("title", "item"), subdir="shop")
                    it.setdefault("alt", it.get("title", ""))
                except FileNotFoundError:
                    pass

            quote_val = num("ups_zone8_quote")
            ship_raw = (form.get("ship_price") or "").strip()
            it["shipping"] = {
                "weight_lb": num("weight_lb"),
                "box_in": (form.get("box_in") or "").strip(),
                "ups_zone8_quote": quote_val,
                "ship_price": num("ship_price") if ship_raw else compute_ship_price(quote_val),
                "local_pickup": form.get("local_pickup") == "1",
            }

            it["stripe_url"] = (form.get("stripe_url") or "").strip()
            it["paypal_button_id"] = (form.get("paypal_button_id") or "").strip()
            if it["stock"] == 0 and not it.get("sold_date"):
                it["sold_date"] = datetime.now().strftime("%Y-%m-%d")
            elif it["stock"] > 0:
                it["sold_date"] = None

        def _handle_shop_post(self, path: str, form: dict):
            shop = load_shop()
            items = shop.get("items", [])

            if path == "/shop/add":
                if not (form.get("title") or "").strip():
                    self._redirect("/?tab=add-item", "Item title is required.")
                    return
                create_backup_note("web-shop-add")
                shop = load_shop()
                it = {
                    "sku": next_sku(shop),
                    "slug": slugify(form.get("title", "item")),
                    "images": [],
                    "cover_image": "",
                    "sold_date": None,
                    "created": datetime.now().isoformat(timespec="seconds"),
                }
                self._shop_apply_form(it, form, shop)
                it["status"] = "active" if (it["stripe_url"] or it["paypal_button_id"]) else "draft"
                shop["items"].insert(0, it)
                save_shop(shop)
                rebuild_all()
                note = "" if it["status"] == "active" else " (saved as draft - no payment link yet)"
                self._redirect("/?tab=shop", f"Added {it['sku']}{note}.")
                return

            idx = _safe_index(form.get("idx", "-1"), len(items))
            if idx < 0:
                self._redirect("/?tab=shop", "Invalid item selection.")
                return

            if path == "/shop/save":
                create_backup_note("web-shop-save")
                shop = load_shop()
                it = shop["items"][idx]
                self._shop_apply_form(it, form, shop)
                if form.get("published") == "1" and (it["stripe_url"] or it["paypal_button_id"]):
                    it["status"] = "active"
                elif form.get("published") == "1":
                    it["status"] = "active"
                else:
                    it["status"] = "draft"
                it["updated"] = datetime.now().isoformat(timespec="seconds")
                save_shop(shop)
                rebuild_all()
                self._redirect("/?tab=shop", f"Saved {it.get('sku', 'item')}.")
                return

            if path == "/shop/stock":
                create_backup_note("web-shop-stock")
                shop = load_shop()
                it = shop["items"][idx]
                raw = (form.get("stock") or "").strip()
                if not raw.isdigit():
                    self._redirect("/?tab=shop", "Stock must be a whole number.")
                    return
                it["stock"] = int(raw)
                it["sold_date"] = datetime.now().strftime("%Y-%m-%d") if it["stock"] == 0 else None
                save_shop(shop)
                rebuild_all()
                self._redirect("/?tab=shop", f"{it.get('sku')} stock set to {it['stock']}.")
                return

            if path == "/shop/sold":
                create_backup_note("web-shop-sold")
                shop = load_shop()
                it = shop["items"][idx]
                if it.get("item_type") == "gear":
                    it["stock"] = 0
                else:
                    it["stock"] = max(0, int(it.get("stock", 0) or 0) - 1)
                if it["stock"] == 0:
                    it["sold_date"] = datetime.now().strftime("%Y-%m-%d")
                save_shop(shop)
                rebuild_all()
                tail = " - now deactivate the other processor's button!" if it["stock"] == 0 else ""
                self._redirect("/?tab=shop", f"{it.get('sku')}: {it['stock']} left{tail}")
                return

            if path == "/shop/delete":
                create_backup_note("web-shop-delete")
                shop = load_shop()
                it = shop["items"][idx]
                slug = it.get("slug", "")
                shop["items"].pop(idx)
                save_shop(shop)
                page = os.path.join(SHOP_DIR, f"{slug}.html")
                if slug and os.path.exists(page):
                    os.remove(page)
                rebuild_all()
                self._redirect("/?tab=shop", "Deleted listing.")
                return

            self._redirect("/?tab=shop", "Unknown shop action.")

        def do_POST(self):
            form = parse_form(self)
            path = urlparse(self.path).path

            if path == "/actions/rebuild":
                rebuild_all()
                self._redirect("/", "Rebuilt site pages.")
                return

            if path == "/actions/publish":
                ok, msg = publish_to_github_noninteractive(form.get("commit_message", ""))
                self._redirect("/", msg)
                return

            if path == "/site/save":
                create_backup_note("web-site-save")
                site = load_site()
                site["name"] = form.get("name", "")
                site["tagline"] = form.get("tagline", "")
                site["build_log_note"] = form.get("build_log_note", "")
                site["about_text"] = form.get("about_text", "")
                site["email"] = form.get("email", "")
                site["instagram_url"] = form.get("instagram_url", "")
                site["youtube_url"] = form.get("youtube_url", "")
                site["tags"] = _split_csv(form.get("tags", ""))
                save_site(site)
                rebuild_all()
                self._redirect("/", "Saved site settings.")
                return

            if path == "/projects/add":
                title = (form.get("title") or "").strip()
                if not title:
                    self._redirect("/", "Build title is required.")
                    return
                create_backup_note("web-project-add")

                image_rel = resolve_image_input(form.get("image_path", ""), title)
                project = {
                    "title": title,
                    "slug": slugify(title),
                    "status": normalize_status(form.get("status", "Complete")),
                    "cover_image": image_rel,
                    "image": image_rel,
                    "images": [],
                    "alt": title,
                    "description": form.get("description", ""),
                    "bullets": _split_lines(form.get("bullets", "")),
                    "tags": _split_csv(form.get("tags", "")),
                    "links": [],
                    "steps": [],
                    "created": datetime.now().isoformat(timespec="seconds"),
                }
                projects = load_projects()
                projects.insert(0, project)
                save_projects(projects)
                rebuild_all(projects)
                self._redirect("/", "Added build.")
                return

            if path == "/projects/delete":
                projects = load_projects()
                idx = _safe_index(form.get("idx", "-1"), len(projects))
                if idx < 0:
                    self._redirect("/", "Invalid build selection.")
                    return
                create_backup_note("web-project-delete")
                projects.pop(idx)
                save_projects(projects)
                rebuild_all(projects)
                self._redirect("/", "Deleted build.")
                return

            if path == "/projects/save":
                projects = load_projects()
                idx = _safe_index(form.get("idx", "-1"), len(projects))
                if idx < 0:
                    self._redirect("/", "Invalid build selection.")
                    return

                create_backup_note("web-project-save")
                p = projects[idx]
                title = (form.get("title") or p.get("title") or "Untitled").strip()
                p["title"] = title
                p["status"] = normalize_status(form.get("status", p.get("status", "Complete")))
                p["description"] = form.get("description", "")
                p["bullets"] = _split_lines(form.get("bullets", ""))
                p["tags"] = _split_csv(form.get("tags", ""))
                p["alt"] = form.get("alt", "") or title

                cover = resolve_image_input(form.get("cover_image", ""), title)
                p["cover_image"] = cover
                p["image"] = cover
                p["images"] = [resolve_image_input(v, title) for v in _split_lines(form.get("images", ""))]
                p["links"] = _links_from_lines(form.get("links", ""))
                p["updated"] = datetime.now().isoformat(timespec="seconds")

                if not p.get("slug"):
                    p["slug"] = slugify(title)

                save_projects(projects)
                rebuild_all(projects)
                self._redirect("/", "Saved build.")
                return

            if path == "/repairs/add":
                title = (form.get("title") or "").strip()
                if not title:
                    self._redirect("/", "Repair title is required.")
                    return
                create_backup_note("web-repair-add")
                image_rel = resolve_image_input(form.get("image_path", ""), title)
                entry = {
                    "title": title,
                    "date": form.get("date", datetime.now().strftime("%Y-%m-%d")),
                    "status": form.get("status", "Fixed"),
                    "device": form.get("device", ""),
                    "symptom": form.get("symptom", ""),
                    "diagnosis": form.get("diagnosis", ""),
                    "fix": form.get("fix", ""),
                    "image": image_rel,
                    "alt": title,
                    "notes": form.get("notes", ""),
                    "tags": _split_csv(form.get("tags", "")),
                    "created": datetime.now().isoformat(timespec="seconds"),
                }
                repairs = load_repairs()
                repairs.insert(0, entry)
                save_repairs(repairs)
                rebuild_all()
                self._redirect("/", "Added repair entry.")
                return

            if path == "/repairs/delete":
                repairs = load_repairs()
                idx = _safe_index(form.get("idx", "-1"), len(repairs))
                if idx < 0:
                    self._redirect("/", "Invalid repair selection.")
                    return
                create_backup_note("web-repair-delete")
                repairs.pop(idx)
                save_repairs(repairs)
                rebuild_all()
                self._redirect("/", "Deleted repair entry.")
                return

            if path == "/repairs/save":
                repairs = load_repairs()
                idx = _safe_index(form.get("idx", "-1"), len(repairs))
                if idx < 0:
                    self._redirect("/", "Invalid repair selection.")
                    return

                create_backup_note("web-repair-save")
                entry = repairs[idx]
                title = (form.get("title") or entry.get("title") or "Repair").strip()
                entry["title"] = title
                entry["date"] = form.get("date", "")
                entry["status"] = form.get("status", "")
                entry["device"] = form.get("device", "")
                entry["symptom"] = form.get("symptom", "")
                entry["diagnosis"] = form.get("diagnosis", "")
                entry["fix"] = form.get("fix", "")
                entry["notes"] = form.get("notes", "")
                entry["tags"] = _split_csv(form.get("tags", ""))
                entry["image"] = resolve_image_input(form.get("image", ""), title)
                entry["alt"] = form.get("alt", "") or title
                entry["updated"] = datetime.now().isoformat(timespec="seconds")

                save_repairs(repairs)
                rebuild_all()
                self._redirect("/", "Saved repair entry.")
                return

            if path.startswith("/shop/"):
                self._handle_shop_post(path, form)
                return

            if path == "/story/add":
                projects = load_projects()
                idx = _safe_index(form.get("idx", "-1"), len(projects))
                if idx < 0:
                    self._redirect("/", "Invalid project selection.")
                    return
                create_backup_note("web-story-add")
                project = projects[idx]
                steps = project.get("steps") or []
                step_no = len(steps) + 1
                title = (form.get("title") or f"Part {step_no}").strip()
                image_rel = resolve_image_input(form.get("image_path", ""), f"{project.get('title','project')}-part-{step_no}")
                steps.append(
                    {
                        "title": title,
                        "text": form.get("text", ""),
                        "image": image_rel,
                        "alt": form.get("alt", "") or title,
                    }
                )
                project["steps"] = steps
                project["updated"] = datetime.now().isoformat(timespec="seconds")
                save_projects(projects)
                rebuild_all(projects)
                self._redirect(f"/story?idx={idx}", "Added story section.")
                return

            if path == "/story/save":
                projects = load_projects()
                idx = _safe_index(form.get("idx", "-1"), len(projects))
                if idx < 0:
                    self._redirect("/", "Invalid project selection.")
                    return
                steps = projects[idx].get("steps") or []
                step_idx = _safe_index(form.get("step_idx", "-1"), len(steps))
                if step_idx < 0:
                    self._redirect(f"/story?idx={idx}", "Invalid section selection.")
                    return

                create_backup_note("web-story-save")
                title = (form.get("title") or steps[step_idx].get("title") or "Part").strip()
                steps[step_idx]["title"] = title
                steps[step_idx]["text"] = form.get("text", "")
                steps[step_idx]["image"] = resolve_image_input(
                    form.get("image", ""), f"{projects[idx].get('title','project')}-part-{step_idx+1}"
                )
                steps[step_idx]["alt"] = form.get("alt", "") or title
                projects[idx]["steps"] = steps
                projects[idx]["updated"] = datetime.now().isoformat(timespec="seconds")

                save_projects(projects)
                rebuild_all(projects)
                self._redirect(f"/story?idx={idx}", "Saved story section.")
                return

            if path == "/story/delete":
                projects = load_projects()
                idx = _safe_index(form.get("idx", "-1"), len(projects))
                if idx < 0:
                    self._redirect("/", "Invalid project selection.")
                    return
                steps = projects[idx].get("steps") or []
                step_idx = _safe_index(form.get("step_idx", "-1"), len(steps))
                if step_idx < 0:
                    self._redirect(f"/story?idx={idx}", "Invalid section selection.")
                    return
                create_backup_note("web-story-delete")
                steps.pop(step_idx)
                projects[idx]["steps"] = steps
                projects[idx]["updated"] = datetime.now().isoformat(timespec="seconds")
                save_projects(projects)
                rebuild_all(projects)
                self._redirect(f"/story?idx={idx}", "Deleted story section.")
                return

            if path == "/story/clear":
                projects = load_projects()
                idx = _safe_index(form.get("idx", "-1"), len(projects))
                if idx < 0:
                    self._redirect("/", "Invalid project selection.")
                    return
                create_backup_note("web-story-clear")
                projects[idx]["steps"] = []
                projects[idx]["updated"] = datetime.now().isoformat(timespec="seconds")
                save_projects(projects)
                rebuild_all(projects)
                self._redirect(f"/story?idx={idx}", "Cleared story sections.")
                return

            self._redirect("/", "Unknown action.")

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer((host, port), AdminHandler)
    print(f"\nWeb UI running at http://{host}:{port}")
    print("Press Ctrl+C to stop the web UI server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb UI stopped.")
    finally:
        server.server_close()


def load_projects():
    return _load_json_list(DATA_PATH)


def save_projects(projects):
    _save_json(DATA_PATH, projects)


def load_repairs():
    return _load_json_list(REPAIRS_PATH)


def save_repairs(repairs):
    _save_json(REPAIRS_PATH, repairs)


def load_site():
    if not os.path.exists(SITE_PATH):
        return {
            "name": "Your Name",
            "tagline": "",
            "build_log_note": "",
            "about_text": "",
            "email": "",
            "instagram_url": "",
            "youtube_url": "",
            "tags": [],
        }
    try:
        with open(SITE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {
                "name": "Your Name",
                "tagline": "",
                "build_log_note": "",
                "about_text": "",
                "email": "",
                "instagram_url": "",
                "youtube_url": "",
                "tags": [],
            }
        # Ensure keys exist
        data.setdefault("tags", [])
        return data
    except json.JSONDecodeError:
        print("⚠️  JSON parse error in site.json. Using defaults.")
        return {
            "name": "Your Name",
            "tagline": "",
            "build_log_note": "",
            "about_text": "",
            "email": "",
            "instagram_url": "",
            "youtube_url": "",
            "tags": [],
        }


def save_site(site):
    _save_json(SITE_PATH, site)


# ---------- Helpers ----------
def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "item"


def prompt(msg: str, default: str | None = None, optional: bool = False) -> str:
    while True:
        if default is not None and default != "":
            val = input(f"{msg} [{default}]: ").strip()
            if val == "":
                return default
        else:
            val = input(f"{msg}: ").strip()

        if val or optional:
            return val
        print("Please enter a value (or Ctrl+C to cancel).")


def prompt_multiline(label: str, default: str | None = None) -> str:
    print(f"\n{label} (finish with a blank line):")
    if default:
        print("---- current ----")
        print(default)
        print("-----------------")

    lines = []
    while True:
        line = input()
        if line.strip() == "":
            break
        lines.append(line)

    if not lines and default is not None:
        return default
    return "\n".join(lines).strip()


def prompt_bullets(default_list=None):
    if default_list is None:
        default_list = []

    print("\nBullets (press Enter on blank line to finish).")
    if default_list:
        print("Current bullets:")
        for b in default_list:
            print(f"  - {b}")

    bullets = []
    while True:
        line = input("  - ").strip()
        if line == "":
            break
        bullets.append(line)

    return bullets if bullets else default_list


def prompt_tags(default_list=None):
    if default_list is None:
        default_list = []

    print("\nTags (optional). Enter tags one per line. Blank line to finish.")
    if default_list:
        print("Current tags:")
        for t in default_list:
            print(f"  - {t}")

    tags = []
    while True:
        t = input("  - ").strip()
        if t == "":
            break
        tags.append(t)

    return tags if tags else default_list


def choose_project_index(projects: list[dict]) -> int:
    if not projects:
        return -1

    while True:
        raw = prompt("Select build number", optional=True)
        if not raw:
            return -1
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(projects):
                return idx
        print(f"Enter a number between 1 and {len(projects)} (or press Enter to cancel).")


def choose_repair_index(repairs: list[dict]) -> int:
    if not repairs:
        return -1

    while True:
        raw = prompt("Select repair number", optional=True)
        if not raw:
            return -1
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(repairs):
                return idx
        print(f"Enter a number between 1 and {len(repairs)} (or press Enter to cancel).")


def prompt_yes_no(message: str, default: str = "n") -> bool:
    val = prompt(message, default=default, optional=True).strip().lower()
    return val in ["y", "yes", "true", "1"]


def prompt_links(default_links=None):
    if default_links is None:
        default_links = []

    print("\nLinks")
    if default_links:
        print("Current links:")
        for i, link in enumerate(default_links, start=1):
            print(f"  {i}. {link.get('label', 'Link')} -> {link.get('url', '')}")

    if prompt_yes_no("Keep current links? (y/n)", default="y"):
        return default_links

    links = []
    while True:
        label = prompt("Link label (or blank to finish)", optional=True)
        if not label:
            break
        url = prompt("Link URL")
        links.append({"label": label, "url": url})

    return links


def collect_extra_images(title: str, existing_images=None, subdir: str = ""):
    if existing_images is None:
        existing_images = []

    images = list(existing_images)
    if images:
        print("\nCurrent gallery images:")
        for i, img in enumerate(images, start=1):
            print(f"  {i}. {img}")

    mode = prompt("Gallery mode (keep / add / replace / clear)", default="keep", optional=True).strip().lower()
    if mode in ["clear", "remove"]:
        return []
    if mode in ["keep", ""]:
        return images
    if mode in ["replace", "reset"]:
        images = []

    while True:
        image_path = prompt("Extra image path (blank to finish)", optional=True)
        if not image_path:
            break
        try:
            image_rel = copy_image_into_site(image_path, title, subdir=subdir)
            images.append(image_rel)
            print(f"  added: {image_rel}")
        except FileNotFoundError as e:
            print(e)

    return images


def normalize_status(value: str) -> str:
    v = (value or "").strip().lower()
    if v in ["in progress", "progress", "in-progress", "inprogress", "ip"]:
        return "In Progress"
    if v in ["complete", "completed", "done", "finished", "c"]:
        return "Complete"
    if v in ["archived", "archive", "old", "a"]:
        return "Archived"
    return (value or "Complete").strip().title()


def status_badge(status: str) -> tuple[str, str]:
    s = (status or "Complete").strip().lower()
    if s.startswith("in"):
        return ("status-progress", "🛠 In Progress")
    if s.startswith("arch"):
        return ("status-archived", "🗃 Archived")
    return ("status-complete", "✅ Complete")


def ensure_project_slugs(projects: list[dict]) -> bool:
    changed = False
    used = set()

    for p in projects:
        base = slugify((p.get("slug") or p.get("title") or "project").strip())
        slug = base
        i = 2
        while slug in used:
            slug = f"{base}-{i}"
            i += 1

        used.add(slug)

        if p.get("slug") != slug:
            p["slug"] = slug
            changed = True

        if "steps" not in p or not isinstance(p.get("steps"), list):
            p["steps"] = []
            changed = True

    return changed


def copy_image_into_site(image_path: str, title: str, subdir: str = "") -> str:
    dest_dir = os.path.join(IMAGES_DIR, subdir) if subdir else IMAGES_DIR
    os.makedirs(dest_dir, exist_ok=True)

    # PowerShell drag/drop often includes quotes
    image_path = (image_path or "").strip().strip('"')

    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    ext = os.path.splitext(image_path)[1].lower()
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    base = slugify(title)
    dest_name = f"{date_prefix}-{base}{ext}"
    dest_path = os.path.join(dest_dir, dest_name)

    i = 2
    while os.path.exists(dest_path):
        dest_name = f"{date_prefix}-{base}-{i}{ext}"
        dest_path = os.path.join(dest_dir, dest_name)
        i += 1

    shutil.copy2(image_path, dest_path)
    rel = f"{subdir}/{dest_name}" if subdir else dest_name
    return f"images/{rel}"


# ---------- HTML generation ----------
def _lines_to_br(text: str) -> str:
    text = (text or "").strip()
    return "<br>".join([html.escape(line.strip(), quote=True) for line in text.splitlines() if line.strip()])


def _card_tags_block(tags: list[str]) -> tuple[str, str]:
    """
    Returns:
      - data-tags string (slugified) for JS filtering
      - HTML chips block (original strings) for display
    """
    tags = tags or []
    clean = [t for t in tags if str(t).strip()]
    data_tags = ",".join([slugify(t) for t in clean])
    if not clean:
        return data_tags, ""

    chips = "\n".join([f'            <span class="tag-chip">{html.escape(t, quote=True)}</span>' for t in clean])
    tags_html = f"""
          <div class="card-tags">
{chips}
          </div>"""
    return data_tags, tags_html


def _project_steps_html(steps: list[dict]) -> str:
    blocks = []
    for i, step in enumerate(steps or [], start=1):
        raw_title = (step.get("title") or f"Part {i}").strip()
        raw_title = re.sub(r"^step\b", "Part", raw_title, flags=re.IGNORECASE)
        title = html.escape(raw_title, quote=True)
        text = _lines_to_br(step.get("text", ""))
        image = html.escape((step.get("image") or "").strip(), quote=True)
        alt = html.escape((step.get("alt") or title).strip(), quote=True)

        image_html = f'\n      <img class="step-image" src="../{image}" alt="{alt}">' if image else ""
        text_html = f"\n      <p>{text}</p>" if text else ""

        blocks.append(f"""
    <article class="project-step">
      <h3>{i}. {title}</h3>{text_html}{image_html}
    </article>
""".rstrip())

    return "\n\n".join(blocks) + ("\n" if blocks else "")


def repair_card_html(r: dict) -> str:
    raw_title = r.get("title", "Untitled Repair")
    title = html.escape(raw_title, quote=True)
    alt = html.escape(r.get("alt", raw_title), quote=True)

    date = html.escape((r.get("date") or "").strip(), quote=True)
    status = html.escape((r.get("status") or "").strip(), quote=True)
    device = html.escape((r.get("device") or "").strip(), quote=True)

    symptom = _lines_to_br(r.get("symptom", ""))
    diagnosis = _lines_to_br(r.get("diagnosis", ""))
    fix = _lines_to_br(r.get("fix", ""))
    notes = _lines_to_br(r.get("notes", ""))

    img = html.escape((r.get("image") or "").strip(), quote=True)
    img_html = f'<img src="{img}" alt="{alt}">' if img else ""

    meta_bits = [b for b in [date, status] if b]
    meta_html = f'<p class="muted">{" • ".join(meta_bits)}</p>' if meta_bits else ""

    data_tags, tags_html = _card_tags_block(r.get("tags") or [])

    def line(label: str, value_html: str) -> str:
        value_html = (value_html or "").strip()
        if not value_html:
            return ""
        return f"<p><strong>{label}:</strong> {value_html}</p>"

    return f"""
      <div class="project-card" data-tags="{data_tags}">
        {img_html}
        <div class="project-info">
          <h3>{title}</h3>
          {meta_html}
          {tags_html}
          {line("Device", device)}
          {line("Symptom", symptom)}
          {line("Diagnosis", diagnosis)}
          {line("Fix", fix)}
          {f"<p>{notes}</p>" if notes else ""}
        </div>
      </div>
""".rstrip() + "\n"


def project_card_html(p: dict) -> str:
    desc_html = _lines_to_br(p.get("description", ""))

    bullets = p.get("bullets") or []
    bullets_html = ""
    if bullets:
        items = "\n".join([f"            <li>{html.escape(str(b), quote=True)}</li>" for b in bullets])
        bullets_html = f"""
          <ul class="bullets">
{items}
          </ul>"""

    links = p.get("links") or []
    links_html = ""
    if links:
        link_tags = []
        for link in links:
            label = html.escape((link.get("label") or "Link").strip(), quote=True)
            url = html.escape((link.get("url") or "").strip(), quote=True)
            if url:
                link_tags.append(f'            <a href="{url}" target="_blank" rel="noopener">{label}</a>')
        if link_tags:
            links_html = f"""
          <div class="links">
{os.linesep.join(link_tags)}
          </div>"""

    raw_title = p.get("title", "Untitled")
    title = html.escape(raw_title, quote=True)
    alt = html.escape(p.get("alt", raw_title), quote=True)

    status = normalize_status(p.get("status", "Complete"))
    badge_class, badge_text = status_badge(status)

    cover = html.escape((p.get("cover_image") or p.get("image") or "").strip(), quote=True)

    images = p.get("images") or []
    images = [html.escape(img.strip(), quote=True) for img in images if isinstance(img, str) and img.strip()]

    gallery_html = ""
    if images:
        gallery_id = f"gallery-{slugify(title)}-{abs(hash(cover)) % 100000}"
        thumbs = "\n".join([f'            <img src="{img}" alt="{alt}">' for img in images])
        gallery_html = f"""
          <button class="gallery-toggle" type="button" data-gallery-toggle="{gallery_id}">More photos</button>
          <div class="gallery" id="{gallery_id}">
{thumbs}
          </div>"""

    data_tags, tags_html = _card_tags_block(p.get("tags") or [])

    detail_href = f"projects/{p.get('slug', slugify(raw_title))}.html"

    return f"""
      <div class="project-card" data-tags="{data_tags}">
        <img class="project-thumb" src="{cover}" alt="{alt}">
        <div class="project-info">
          <h3>{title} <span class="status-badge {badge_class}">{badge_text}</span></h3>
          <p>{desc_html}</p>{tags_html}
          <a class="project-open" href="{detail_href}">Open project</a>{bullets_html}{links_html}{gallery_html}
        </div>
      </div>
""".rstrip() + "\n"


def project_detail_html(p: dict, site: dict, template: str) -> str:
    raw_title = p.get("title", "Untitled")
    title = html.escape(raw_title, quote=True)
    alt = html.escape(p.get("alt", raw_title), quote=True)
    desc = _lines_to_br(p.get("description", ""))
    cover = html.escape((p.get("cover_image") or p.get("image") or "").strip(), quote=True)

    status = normalize_status(p.get("status", "Complete"))
    badge_class, badge_text = status_badge(status)

    data_tags, tags_html = _card_tags_block(p.get("tags") or [])
    tags_html = tags_html.strip() if tags_html else ""

    bullets = p.get("bullets") or []
    bullets_html = ""
    if bullets:
        items = "\n".join([f"          <li>{html.escape(str(b), quote=True)}</li>" for b in bullets])
        bullets_html = f"""
        <ul class="bullets project-bullets">
{items}
        </ul>
""".strip()

    links = p.get("links") or []
    links_html = ""
    if links:
        link_tags = []
        for link in links:
            label = html.escape((link.get("label") or "Link").strip(), quote=True)
            url = html.escape((link.get("url") or "").strip(), quote=True)
            if url:
                link_tags.append(f'          <a href="{url}" target="_blank" rel="noopener">{label}</a>')
        if link_tags:
            links_html = f"""
        <div class="links">
{os.linesep.join(link_tags)}
        </div>
""".strip()

    # SEO: build meta description from plain text of description
    slug = p.get("slug") or slugify(raw_title)
    plain_desc = re.sub(r"<[^>]+>", "", p.get("description", "")).strip()
    meta_desc = html.escape((plain_desc[:157] + "...") if len(plain_desc) > 160 else plain_desc, quote=True)
    og_image = f"{SITE_URL}/{cover}" if cover else f"{SITE_URL}/images/og.png"

    content = replace_placeholders(template, site)
    mapping = {
        "{{PROJECT_TITLE}}": title,
        "{{PROJECT_DESCRIPTION}}": desc,
        "{{PROJECT_COVER_IMAGE}}": f"../{cover}" if cover else "",
        "{{PROJECT_ALT}}": alt,
        "{{PROJECT_STATUS_BADGE_CLASS}}": badge_class,
        "{{PROJECT_STATUS_BADGE_TEXT}}": badge_text,
        "{{PROJECT_CARD_TAGS}}": tags_html,
        "{{PROJECT_BULLETS}}": bullets_html,
        "{{PROJECT_LINKS}}": links_html,
        "{{PROJECT_META_DESCRIPTION}}": meta_desc,
        "{{PROJECT_OG_IMAGE}}": og_image,
        "{{PROJECT_SLUG}}": html.escape(slug, quote=True),
    }
    for key, value in mapping.items():
        content = content.replace(key, value)

    if PROJECT_STEPS_START not in content or PROJECT_STEPS_END not in content:
        raise ValueError(
            "Markers not found in project_template.html.\n"
            "Add:\n"
            "<!-- PROJECT_STEPS_START -->\n"
            "<!-- PROJECT_STEPS_END -->"
        )

    start_i = content.index(PROJECT_STEPS_START) + len(PROJECT_STEPS_START)
    end_i = content.index(PROJECT_STEPS_END)
    steps_html = _project_steps_html(p.get("steps") or [])
    content = content[:start_i] + "\n" + steps_html + content[end_i:]

    return content


def replace_placeholders(content: str, site: dict) -> str:
    mapping = {
        "{{NAME}}": html.escape(site.get("name", ""), quote=True),
        "{{TAGLINE}}": html.escape(site.get("tagline", ""), quote=True),
        "{{BUILD_LOG_NOTE}}": html.escape(site.get("build_log_note", ""), quote=True),
        "{{ABOUT_TEXT}}": html.escape(site.get("about_text", ""), quote=True),
        "{{EMAIL}}": html.escape(site.get("email", ""), quote=True),
        "{{INSTAGRAM_URL}}": html.escape(site.get("instagram_url", ""), quote=True),
        "{{YOUTUBE_URL}}": html.escape(site.get("youtube_url", ""), quote=True),
        "{{LEGAL_NAME}}": html.escape(site.get("legal_name", "") or site.get("name", ""), quote=True),
        "{{STATEMENT_DESCRIPTOR}}": html.escape(site.get("statement_descriptor", ""), quote=True),
        "{{SITE_URL}}": SITE_URL,
        "{{EMAIL_INLINE}}": email_inline_html(site),
    }
    for k, v in mapping.items():
        content = content.replace(k, v)
    return content


def inject_tags(content: str, tags: list[str]) -> str:
    # This injects the ABOUT section tags, not per-card tags
    if TAGS_START not in content or TAGS_END not in content:
        return content

    tag_html = "\n".join([f"        <span>{html.escape(str(t), quote=True)}</span>" for t in (tags or [])])

    s = content.index(TAGS_START) + len(TAGS_START)
    e = content.index(TAGS_END)
    return content[:s] + "\n" + tag_html + "\n      " + content[e:]


def rebuild_index_from_projects(projects):
    if ensure_project_slugs(projects):
        save_projects(projects)

    if not os.path.isfile(TEMPLATE_PATH):
        raise FileNotFoundError(
            f"template.html not found at {TEMPLATE_PATH}\n"
            "Create it by copying index.html -> template.html"
        )

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    if PROJECTS_START not in template or PROJECTS_END not in template:
        raise ValueError(
            "Markers not found in template.html.\n"
            "Add:\n"
            "<!-- PROJECTS_START -->\n"
            "<!-- PROJECTS_END -->"
        )

    start_i = template.index(PROJECTS_START) + len(PROJECTS_START)
    end_i = template.index(PROJECTS_END)
    cards = "".join(project_card_html(p) for p in projects)
    new_content = template[:start_i] + "\n" + cards + template[end_i:]

    if os.path.exists(SITE_PATH):
        site = load_site()
        new_content = replace_placeholders(new_content, site)
        new_content = inject_tags(new_content, site.get("tags", []))

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)


def rebuild_project_pages(projects):
    if ensure_project_slugs(projects):
        save_projects(projects)

    if not os.path.isfile(PROJECT_TEMPLATE_PATH):
        raise FileNotFoundError(
            f"project_template.html not found at {PROJECT_TEMPLATE_PATH}\n"
            "Create it by creating project_template.html"
        )

    with open(PROJECT_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    site = load_site() if os.path.exists(SITE_PATH) else load_site()

    os.makedirs(PROJECTS_DIR, exist_ok=True)
    keep_files = set()

    for p in projects:
        slug = p.get("slug") or slugify(p.get("title", "project"))
        out_name = f"{slug}.html"
        out_path = os.path.join(PROJECTS_DIR, out_name)
        keep_files.add(out_name)

        html_out = project_detail_html(p, site, template)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_out)

    for name in os.listdir(PROJECTS_DIR):
        if name.endswith(".html") and name not in keep_files:
            os.remove(os.path.join(PROJECTS_DIR, name))


def rebuild_repairs_page():
    if not os.path.isfile(REPAIRS_TEMPLATE_PATH):
        raise FileNotFoundError(
            f"repairs_template.html not found at {REPAIRS_TEMPLATE_PATH}\n"
            "Create it by creating repairs_template.html"
        )

    with open(REPAIRS_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    if REPAIRS_START not in template or REPAIRS_END not in template:
        raise ValueError(
            "Markers not found in repairs_template.html.\n"
            "Add:\n"
            "<!-- REPAIRS_START -->\n"
            "<!-- REPAIRS_END -->"
        )

    repairs = load_repairs()
    rs = template.index(REPAIRS_START) + len(REPAIRS_START)
    re_ = template.index(REPAIRS_END)
    repair_cards = "".join(repair_card_html(r) for r in repairs)
    new_content = template[:rs] + "\n" + repair_cards + template[re_:]

    if os.path.exists(SITE_PATH):
        site = load_site()
        new_content = replace_placeholders(new_content, site)
        new_content = inject_tags(new_content, site.get("tags", []))

    with open(REPAIRS_INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)


def rebuild_all(projects=None):
    if projects is None:
        projects = load_projects()
    rebuild_index_from_projects(projects)
    rebuild_project_pages(projects)
    rebuild_repairs_page()
    rebuild_shop()


# ---------- Shop: data ----------
def _default_shop() -> dict:
    return {"next_sku": 1001, "collections": [], "items": []}


def load_shop() -> dict:
    if not os.path.exists(SHOP_PATH):
        return _default_shop()
    try:
        with open(SHOP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print("⚠️  JSON parse error in shop.json. Using empty shop.")
        return _default_shop()
    if not isinstance(data, dict):
        return _default_shop()
    data.setdefault("next_sku", 1001)
    data.setdefault("collections", [])
    data.setdefault("items", [])
    return data


def save_shop(shop: dict):
    _save_json(SHOP_PATH, shop)


def next_sku(shop: dict) -> str:
    """Assign the next sequential part number. Numbers are never reused."""
    n = int(shop.get("next_sku", 1001))
    shop["next_sku"] = n + 1
    return f"RM-{n}"


def compute_ship_price(zone8_quote: float) -> float:
    """Worst-case UPS quote plus markup, rounded to a whole dollar."""
    try:
        return float(round(float(zone8_quote) * SHIP_MARKUP))
    except (TypeError, ValueError):
        return 0.0


def ensure_shop_slugs(shop: dict) -> bool:
    """Fill in missing slugs and SKUs. Returns True if anything changed."""
    changed = False
    seen = set()
    for item in shop.get("items", []):
        slug = (item.get("slug") or "").strip()
        if not slug:
            slug = slugify(item.get("title", "item"))
            changed = True
        base = slug
        i = 2
        while slug in seen:
            slug = f"{base}-{i}"
            i += 1
            changed = True
        seen.add(slug)
        if item.get("slug") != slug:
            item["slug"] = slug
            changed = True
        if not (item.get("sku") or "").strip():
            item["sku"] = next_sku(shop)
            changed = True
    for c in shop.get("collections", []):
        if not (c.get("slug") or "").strip():
            c["slug"] = slugify(c.get("title", "collection"))
            changed = True
    return changed


def collection_map(shop: dict) -> dict:
    return {c.get("slug"): c for c in shop.get("collections", []) if c.get("slug")}


def sorted_collections(shop: dict) -> list:
    return sorted(shop.get("collections", []), key=lambda c: (c.get("order", 999), c.get("title", "")))


def visible_items(shop: dict) -> list:
    """Everything except drafts, in-stock first, then newest sold last."""
    items = [i for i in shop.get("items", []) if (i.get("status") or "active") != "draft"]
    return sorted(items, key=lambda i: (0 if int(i.get("stock", 0) or 0) > 0 else 1, i.get("title", "")))


def items_in_collection(shop: dict, slug: str) -> list:
    return [i for i in visible_items(shop) if slug in (i.get("collections") or [])]


# ---------- Shop: presentation helpers ----------
def item_state(item: dict) -> str:
    """One of: draft, sold_out, low, in_stock."""
    if (item.get("status") or "active") == "draft":
        return "draft"
    stock = int(item.get("stock", 0) or 0)
    if stock <= 0:
        return "sold_out"
    if item.get("item_type") != "gear" and stock <= 2:
        return "low"
    return "in_stock"


def item_badge(item: dict) -> tuple[str, str]:
    state = item_state(item)
    stock = int(item.get("stock", 0) or 0)
    if state == "sold_out":
        return ("status-sold", "Sold" if item.get("item_type") == "gear" else "Sold out")
    if state == "low":
        return ("status-low", f"Only {stock} left")
    if state == "draft":
        return ("status-archived", "Draft")
    return ("status-instock", "In stock")


def item_has_payment_link(item: dict) -> bool:
    return bool((item.get("stripe_url") or "").strip() or (item.get("paypal_button_id") or "").strip())


def item_needs_payment_link(item: dict) -> bool:
    """In stock but with nothing to click - the case worth warning about."""
    return item_state(item) in ("in_stock", "low") and not item_has_payment_link(item)


def item_is_buyable(item: dict) -> bool:
    if item_state(item) not in ("in_stock", "low"):
        return False
    try:
        price = float(item.get("price", 0) or 0)
    except (TypeError, ValueError):
        return False
    if price <= 0:
        return False
    return item_has_payment_link(item)


def fmt_price(value) -> str:
    try:
        p = float(value or 0)
    except (TypeError, ValueError):
        return ""
    if p <= 0:
        return ""
    return f"${p:,.0f}" if abs(p - round(p)) < 0.005 else f"${p:,.2f}"


def item_ship_note(item: dict) -> str:
    ship = item.get("shipping") or {}
    price = fmt_price(ship.get("ship_price"))
    pickup = " · free local pickup" if ship.get("local_pickup", True) else ""
    if price:
        return f"+ {price} shipping{pickup}"
    return f"Shipping quoted at checkout{pickup}"


def _mailto(site: dict, subject: str) -> str:
    email = (site.get("email") or "").strip()
    if not email:
        return ""
    return f"mailto:{email}?subject={quote(subject, safe='')}"


def _item_search_text(item: dict, cmap: dict) -> str:
    parts = [
        item.get("sku", ""),
        item.get("mpn", ""),
        item.get("brand", ""),
        item.get("condition", ""),
        str(item.get("year", "")),
        item.get("item_type", ""),
    ]
    parts += list(item.get("fits_models") or [])
    parts += list(item.get("tags") or [])
    parts += [(cmap.get(s) or {}).get("title", s) for s in (item.get("collections") or [])]
    return " ".join(str(p) for p in parts if p)


def email_button_html(site: dict, indent: str = "") -> str:
    """Plain, selectable address on cards. No mailto: - that only does anything for
    people with a desktop mail client - and no copy button, because a copy that
    silently fails is worse than text the reader can just select."""
    email = (site.get("email") or "").strip()
    if not email:
        return ""
    e = html.escape(email, quote=True)
    return f'{indent}<span class="shop-email">{e}</span>'


def email_inline_html(site: dict, subject: str = "") -> str:
    """Visible address for body copy: readable and selectable, with a copy button,
    and still a mailto for anyone who does have a mail client."""
    email = (site.get("email") or "").strip()
    if not email:
        return ""
    e = html.escape(email, quote=True)
    href = f"mailto:{e}?subject={quote(subject, safe='')}" if subject else f"mailto:{e}"
    return (f'<span class="email-inline"><a href="{html.escape(href, quote=True)}">{e}</a>'
            f'<button type="button" class="copy-email copy-chip" data-email="{e}" '
            f'title="Copy address">Copy</button></span>')


def shop_buy_row_html(item: dict, site: dict, indent: str = "          ") -> str:
    """Buy buttons. Only rendered when the item is actually purchasable."""
    parts = []
    title = item.get("title", "this item")
    if item_is_buyable(item):
        stripe_url = (item.get("stripe_url") or "").strip()
        if stripe_url:
            parts.append(
                f'{indent}<a class="btn btn-primary btn-sm" href="{html.escape(stripe_url, quote=True)}"'
                f' target="_blank" rel="noopener">Buy — {fmt_price(item.get("price"))}</a>'
            )
        pp = (item.get("paypal_button_id") or "").strip()
        if pp:
            parts.append(
                f'{indent}<form action="https://www.paypal.com/cgi-bin/webscr" method="post" target="_blank" rel="noopener">\n'
                f'{indent}  <input type="hidden" name="cmd" value="_s-xclick">\n'
                f'{indent}  <input type="hidden" name="hosted_button_id" value="{html.escape(pp, quote=True)}">\n'
                f'{indent}  <button type="submit" class="btn btn-paypal btn-sm">PayPal</button>\n'
                f'{indent}</form>'
            )
    else:
        state = item_state(item)
        if state == "sold_out":
            msg = "Sold — email me if you want one like it" if item.get("item_type") == "gear" \
                else "Out of stock — email me to be notified"
        else:
            msg = "Email for price and availability"
        parts.append(f'{indent}<span class="shop-unavailable">{html.escape(msg, quote=True)}</span>')

    parts.append(email_button_html(site, indent=indent))

    return "\n".join(p for p in parts if p)


def shop_card_html(item: dict, site: dict, cmap: dict, asset_prefix: str = "", item_href: str = "") -> str:
    slug = item.get("slug") or slugify(item.get("title", "item"))
    href = item_href or f"{asset_prefix}shop/{slug}.html"
    raw_title = item.get("title", "Untitled")
    title = html.escape(raw_title, quote=True)
    alt = html.escape(item.get("alt", raw_title), quote=True)
    badge_class, badge_text = item_badge(item)
    state = item_state(item)

    cover = (item.get("cover_image") or "").strip()
    if cover:
        media_inner = f'<img class="shop-thumb" src="{html.escape(asset_prefix + cover, quote=True)}" alt="{alt}">'
    else:
        media_inner = '<div class="shop-thumb-empty">◎</div>'
    if state == "sold_out":
        label = "Sold" if item.get("item_type") == "gear" else "Sold out"
        media_inner += f'\n          <div class="sold-overlay">{label}</div>'

    meta_bits = []
    if item.get("brand"):
        meta_bits.append(f'<span><strong>{html.escape(str(item["brand"]), quote=True)}</strong></span>')
    if item.get("year"):
        meta_bits.append(f'<span>{html.escape(str(item["year"]), quote=True)}</span>')
    if item.get("condition"):
        meta_bits.append(f'<span>{html.escape(str(item["condition"]), quote=True)}</span>')
    if item.get("mpn"):
        meta_bits.append(f'<span>PN {html.escape(str(item["mpn"]), quote=True)}</span>')
    meta_html = ""
    if meta_bits:
        meta_html = '\n            <div class="shop-meta">' + " ".join(meta_bits) + "</div>"

    subtitle = item.get("subtitle") or ""
    subtitle_html = ""
    if subtitle:
        subtitle_html = f'\n            <p class="shop-subtitle">{html.escape(subtitle, quote=True)}</p>'

    price = fmt_price(item.get("price"))
    price_html = price if price else '<span class="shop-price-tbd">Email for price</span>'

    coll_slugs = [s for s in (item.get("collections") or []) if s]
    coll_labels = [(cmap.get(s) or {}).get("title", s) for s in coll_slugs]

    sku = html.escape(item.get("sku", ""), quote=True)
    sku_html = f'\n            <p class="shop-sku">{sku}</p>' if sku else ""

    return f"""
        <div class="shop-card{' is-sold' if state == 'sold_out' else ''}"
             data-collections="{html.escape(','.join(coll_slugs), quote=True)}"
             data-collection-labels="{html.escape(','.join(coll_labels), quote=True)}"
             data-in-stock="{'0' if state == 'sold_out' else '1'}"
             data-search-text="{html.escape(_item_search_text(item, cmap), quote=True)}">
          <a class="shop-card-media" href="{html.escape(href, quote=True)}">
          {media_inner}
          </a>
          <div class="shop-card-body">{sku_html}
            <h3><a href="{html.escape(href, quote=True)}">{title}</a> <span class="status-badge {badge_class}">{badge_text}</span></h3>{subtitle_html}{meta_html}
            <p class="shop-price">{price_html}</p>
            <p class="shop-ship-note">{html.escape(item_ship_note(item), quote=True)}</p>
            <div class="shop-buy-row">
{shop_buy_row_html(item, site)}
            </div>
          </div>
        </div>
"""


def collection_card_html(c: dict, count: int, in_stock: int) -> str:
    slug = c.get("slug", "")
    title = html.escape(c.get("title", slug), quote=True)
    blurb = html.escape(c.get("blurb", ""), quote=True)
    cover = (c.get("cover_image") or "").strip()
    if cover:
        media = f'<img class="collection-thumb" src="{html.escape(cover, quote=True)}" alt="{title}">'
    else:
        media = f'<div class="collection-thumb-empty">{title[:1].upper()}</div>'
    if count == 0:
        count_label = "Nothing listed yet"
    elif in_stock == 0:
        count_label = f"{count} listed · all sold"
    else:
        count_label = f"{in_stock} in stock"
    return f"""
          <a class="collection-card" href="shop/{html.escape(slug, quote=True)}.html">
            {media}
            <div class="collection-body">
              <h3>{title}</h3>
              <p>{blurb}</p>
              <span class="collection-count">{count_label}</span>
            </div>
          </a>
"""


def _splice(content: str, start_marker: str, end_marker: str, inner: str, label: str) -> str:
    if start_marker not in content or end_marker not in content:
        raise ValueError(f"Markers not found in {label}.\nAdd:\n{start_marker}\n{end_marker}")
    s = content.index(start_marker) + len(start_marker)
    e = content.index(end_marker)
    return content[:s] + "\n" + inner + content[e:]


# ---------- Shop: page generation ----------
def rebuild_shop_index(shop: dict, site: dict):
    if not os.path.isfile(SHOP_TEMPLATE_PATH):
        raise FileNotFoundError(f"shop_template.html not found at {SHOP_TEMPLATE_PATH}")

    with open(SHOP_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    cmap = collection_map(shop)
    items = visible_items(shop)

    cards = []
    for c in sorted_collections(shop):
        slug = c.get("slug", "")
        in_coll = items_in_collection(shop, slug)
        in_stock = sum(1 for i in in_coll if item_state(i) != "sold_out")
        cards.append(collection_card_html(c, len(in_coll), in_stock))
    content = _splice(content, COLLECTIONS_START, COLLECTIONS_END, "".join(cards), "shop_template.html")

    item_cards = "".join(shop_card_html(i, site, cmap) for i in items)
    content = _splice(content, SHOP_ITEMS_START, SHOP_ITEMS_END, item_cards, "shop_template.html")

    content = replace_placeholders(content, site)
    with open(SHOP_INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def rebuild_shop_collection_pages(shop: dict, site: dict) -> list[str]:
    if not os.path.isfile(SHOP_COLLECTION_TEMPLATE_PATH):
        raise FileNotFoundError(f"shop_collection_template.html not found at {SHOP_COLLECTION_TEMPLATE_PATH}")

    with open(SHOP_COLLECTION_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    cmap = collection_map(shop)
    os.makedirs(SHOP_DIR, exist_ok=True)
    written = []

    all_cols = sorted_collections(shop)
    for c in all_cols:
        slug = c.get("slug", "")
        title = c.get("title", slug)
        items = items_in_collection(shop, slug)

        nav_links = []
        for other in all_cols:
            oslug = other.get("slug", "")
            cls = ' class="is-active"' if oslug == slug else ""
            nav_links.append(
                f'        <a href="{html.escape(oslug, quote=True)}.html"{cls}>'
                f'{html.escape(other.get("title", oslug), quote=True)}</a>'
            )
        content = _splice(template, COLLECTION_NAV_START, COLLECTION_NAV_END,
                          "\n".join(nav_links) + "\n", "shop_collection_template.html")

        if items:
            cards = "".join(
                shop_card_html(i, site, cmap, asset_prefix="../", item_href=f"{i.get('slug')}.html")
                for i in items
            )
        else:
            cards = ('        <p class="shop-empty">Nothing listed in this collection right now — '
                     'check back, or email me and I\'ll tell you what I have on the shelf.</p>\n')
        content = _splice(content, SHOP_ITEMS_START, SHOP_ITEMS_END, cards, "shop_collection_template.html")

        blurb = c.get("blurb", "")
        cover = (c.get("cover_image") or "").strip()
        mapping = {
            "{{COLLECTION_TITLE}}": html.escape(title, quote=True),
            "{{COLLECTION_SLUG}}": html.escape(slug, quote=True),
            "{{COLLECTION_BLURB}}": html.escape(blurb, quote=True),
            "{{COLLECTION_META_DESCRIPTION}}": html.escape(
                (blurb or f"{title} for sale from Rudi Makes in Indianapolis.")[:160], quote=True),
            "{{COLLECTION_OG_IMAGE}}": f"{SITE_URL}/{cover}" if cover else f"{SITE_URL}/images/og.png",
        }
        content = replace_placeholders(content, site)
        for k, v in mapping.items():
            content = content.replace(k, v)

        out_name = f"{slug}.html"
        with open(os.path.join(SHOP_DIR, out_name), "w", encoding="utf-8") as f:
            f.write(content)
        written.append(out_name)

    return written


def _item_jsonld(item: dict, site: dict) -> str:
    slug = item.get("slug", "")
    cover = (item.get("cover_image") or "").strip()
    state = item_state(item)
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": item.get("title", ""),
        "sku": item.get("sku", ""),
        "description": re.sub(r"\s+", " ", (item.get("description") or "")).strip()[:400],
        "url": f"{SITE_URL}/shop/{slug}.html",
    }
    if item.get("brand"):
        data["brand"] = {"@type": "Brand", "name": item["brand"]}
    if item.get("mpn"):
        data["mpn"] = item["mpn"]
    if cover:
        data["image"] = f"{SITE_URL}/{cover}"
    try:
        price = float(item.get("price", 0) or 0)
    except (TypeError, ValueError):
        price = 0.0
    if price > 0:
        data["offers"] = {
            "@type": "Offer",
            "price": f"{price:.2f}",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock" if state in ("in_stock", "low")
                            else "https://schema.org/OutOfStock",
            "itemCondition": "https://schema.org/UsedCondition" if item.get("item_type") == "gear"
                             else "https://schema.org/NewCondition",
            "seller": {"@type": "Organization",
                       "name": site.get("legal_name") or site.get("name", "Rudi Makes")},
        }
    return json.dumps(data, indent=2, ensure_ascii=False)


def shop_item_detail_html(item: dict, shop: dict, site: dict, template: str) -> str:
    cmap = collection_map(shop)
    slug = item.get("slug", "")
    raw_title = item.get("title", "Untitled")
    title = html.escape(raw_title, quote=True)
    alt = html.escape(item.get("alt", raw_title), quote=True)
    badge_class, badge_text = item_badge(item)
    cover = (item.get("cover_image") or "").strip()

    content = template

    # Gallery thumbs
    images = [img.strip() for img in (item.get("images") or []) if isinstance(img, str) and img.strip()]
    if images:
        thumbs = "\n".join(
            f'            <img src="../{html.escape(img, quote=True)}" alt="{alt}">' for img in images
        )
        gallery = f'          <div class="item-thumbs">\n{thumbs}\n          </div>\n'
    else:
        gallery = ""
    content = _splice(content, ITEM_GALLERY_START, ITEM_GALLERY_END, gallery, "shop_item_template.html")

    # Buy row
    content = _splice(content, ITEM_BUY_START, ITEM_BUY_END,
                      f'          <div class="shop-buy-row">\n{shop_buy_row_html(item, site)}\n          </div>\n',
                      "shop_item_template.html")

    # Spec table
    specs = []
    ship = item.get("shipping") or {}
    for label, value in (
        ("Part number", item.get("sku")),
        ("Manufacturer PN", item.get("mpn")),
        ("Brand", item.get("brand")),
        ("Year", item.get("year")),
        ("Condition", item.get("condition")),
        ("In stock", item.get("stock") if item.get("item_type") != "gear" else None),
        ("Ships in", ship.get("box_in")),
        ("Shipping weight", f'{ship.get("weight_lb")} lb' if ship.get("weight_lb") else None),
    ):
        if value in (None, "", 0):
            continue
        specs.append(
            f'            <li><span>{html.escape(str(label), quote=True)}</span>'
            f'<span>{html.escape(str(value), quote=True)}</span></li>'
        )
    specs_html = f'          <ul class="item-specs">\n' + "\n".join(specs) + "\n          </ul>\n" if specs else ""
    content = _splice(content, ITEM_SPECS_START, ITEM_SPECS_END, specs_html, "shop_item_template.html")

    # Service notes
    service = (item.get("service_notes") or "").strip()
    service_html = f"          <h3>What I Did To It</h3>\n          <p>{_lines_to_br(service)}</p>\n" if service else ""
    content = _splice(content, ITEM_SERVICE_START, ITEM_SERVICE_END, service_html, "shop_item_template.html")

    # Includes
    includes = [str(x) for x in (item.get("includes") or []) if str(x).strip()]
    if includes:
        lis = "\n".join(f'            <li>{html.escape(x, quote=True)}</li>' for x in includes)
        includes_html = f'          <h3>What\'s Included</h3>\n          <ul class="bullets">\n{lis}\n          </ul>\n'
    else:
        includes_html = ""
    content = _splice(content, ITEM_INCLUDES_START, ITEM_INCLUDES_END, includes_html, "shop_item_template.html")

    # Fitment
    fits = [str(x) for x in (item.get("fits_models") or []) if str(x).strip()]
    if fits:
        lis = "\n".join(f'            <li>{html.escape(x, quote=True)}</li>' for x in fits)
        fits_html = f'          <h3>Fits</h3>\n          <ul class="fits-list">\n{lis}\n          </ul>\n'
    else:
        fits_html = ""
    content = _splice(content, ITEM_FITS_START, ITEM_FITS_END, fits_html, "shop_item_template.html")

    # Breadcrumb collection link
    coll_slugs = [s for s in (item.get("collections") or []) if s in cmap]
    if coll_slugs:
        c = cmap[coll_slugs[0]]
        crumb = (f'<a href="{html.escape(c.get("slug", ""), quote=True)}.html">'
                 f'{html.escape(c.get("title", ""), quote=True)}</a>\n        <span>→</span>')
    else:
        crumb = ""

    _, tags_html = _card_tags_block(item.get("tags") or [])

    plain = re.sub(r"<[^>]+>", "", item.get("description", "")).strip()
    plain = re.sub(r"\s+", " ", plain)
    meta_desc = (plain[:157] + "...") if len(plain) > 160 else plain

    content = replace_placeholders(content, site)
    mapping = {
        "{{ITEM_TITLE}}": title,
        "{{ITEM_SLUG}}": html.escape(slug, quote=True),
        "{{ITEM_SKU}}": html.escape(item.get("sku", ""), quote=True),
        "{{ITEM_SUBTITLE}}": html.escape(item.get("subtitle", ""), quote=True),
        "{{ITEM_ALT}}": alt,
        "{{ITEM_DESCRIPTION}}": _lines_to_br(item.get("description", "")),
        "{{ITEM_BULLETS}}": _shop_bullets_html(item.get("bullets") or []),
        "{{ITEM_CARD_TAGS}}": (tags_html or "").strip(),
        "{{ITEM_COVER_IMAGE}}": f"../{html.escape(cover, quote=True)}" if cover else "",
        "{{ITEM_BADGE_CLASS}}": badge_class,
        "{{ITEM_BADGE_TEXT}}": badge_text,
        "{{ITEM_PRICE}}": fmt_price(item.get("price")) or '<span class="shop-price-tbd">Email for price</span>',
        "{{ITEM_SHIP_NOTE}}": html.escape(item_ship_note(item), quote=True),
        "{{ITEM_META_DESCRIPTION}}": html.escape(meta_desc, quote=True),
        "{{ITEM_OG_IMAGE}}": f"{SITE_URL}/{cover}" if cover else f"{SITE_URL}/images/og.png",
        "{{ITEM_BREADCRUMB_COLLECTION}}": crumb,
        "{{ITEM_MAIL_SUBJECT}}": quote(f"{raw_title} ({item.get('sku', '')})".strip(), safe=""),
        "{{ITEM_JSONLD}}": _item_jsonld(item, site),
    }
    for k, v in mapping.items():
        content = content.replace(k, v)
    return content


def _shop_bullets_html(bullets: list) -> str:
    items = [str(b) for b in bullets if str(b).strip()]
    if not items:
        return ""
    lis = "\n".join(f'            <li>{html.escape(b, quote=True)}</li>' for b in items)
    return f'<ul class="bullets project-bullets">\n{lis}\n          </ul>'


def rebuild_shop_item_pages(shop: dict, site: dict) -> list[str]:
    if not os.path.isfile(SHOP_ITEM_TEMPLATE_PATH):
        raise FileNotFoundError(f"shop_item_template.html not found at {SHOP_ITEM_TEMPLATE_PATH}")

    with open(SHOP_ITEM_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    os.makedirs(SHOP_DIR, exist_ok=True)
    written = []
    for item in visible_items(shop):
        slug = item.get("slug") or slugify(item.get("title", "item"))
        out_name = f"{slug}.html"
        with open(os.path.join(SHOP_DIR, out_name), "w", encoding="utf-8") as f:
            f.write(shop_item_detail_html(item, shop, site, template))
        written.append(out_name)
    return written


def rebuild_shop():
    """Regenerate shop.html, shop/<collection>.html, and shop/<item>.html."""
    shop = load_shop()
    if ensure_shop_slugs(shop):
        save_shop(shop)
    site = load_site()

    rebuild_shop_index(shop, site)
    keep = set()
    keep.update(rebuild_shop_collection_pages(shop, site))
    keep.update(rebuild_shop_item_pages(shop, site))

    # Drop pages whose collection or item no longer exists
    if os.path.isdir(SHOP_DIR):
        for name in os.listdir(SHOP_DIR):
            if name.endswith(".html") and name not in keep:
                os.remove(os.path.join(SHOP_DIR, name))

    update_sitemap(shop)


def update_sitemap(shop: dict | None = None):
    """Keep sitemap.xml in step with the generated shop pages."""
    sitemap_path = os.path.join(ROOT, "sitemap.xml")
    if not os.path.isfile(sitemap_path):
        return
    if shop is None:
        shop = load_shop()

    with open(sitemap_path, "r", encoding="utf-8") as f:
        xml = f.read()

    # Strip any previously generated shop block, then re-add it.
    xml = re.sub(r"\n?  <!-- SHOP_URLS_START -->.*?<!-- SHOP_URLS_END -->", "", xml, flags=re.DOTALL)

    today = datetime.now().strftime("%Y-%m-%d")
    urls = [f"{SITE_URL}/shop.html"]
    urls += [f"{SITE_URL}/shop/{c.get('slug')}.html" for c in sorted_collections(shop) if c.get("slug")]
    urls += [f"{SITE_URL}/shop/{i.get('slug')}.html" for i in visible_items(shop) if i.get("slug")]

    entries = "\n".join(
        f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n  </url>"
        for u in urls
    )
    block = f"\n  <!-- SHOP_URLS_START -->\n{entries}\n  <!-- SHOP_URLS_END -->"

    if "</urlset>" not in xml:
        return
    xml = xml.replace("</urlset>", f"{block}\n</urlset>")
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write(xml)


# ---------- Commands ----------
def list_projects(projects):
    if not projects:
        print("No projects yet.")
        return
    print("\nBuilds:")
    for i, p in enumerate(projects, start=1):
        status = normalize_status(p.get("status", "Complete"))
        tags = p.get("tags") or []
        tag_str = ", ".join(tags) if tags else ""
        print(f"  {i}. {p.get('title','Untitled')}  [{status}]" + (f"  ({tag_str})" if tag_str else ""))


def list_repairs(repairs):
    if not repairs:
        print("No repair logs yet.")
        return
    print("\nTroubleshooting:")
    for i, r in enumerate(repairs, start=1):
        title = r.get("title", "Untitled Repair")
        date = (r.get("date") or "").strip()
        status = (r.get("status") or "").strip()
        tags = r.get("tags") or []
        extra = " • ".join([x for x in [date, status] if x])
        tag_str = ", ".join(tags) if tags else ""
        line = f"  {i}. {title}"
        if extra:
            line += f"  [{extra}]"
        if tag_str:
            line += f"  ({tag_str})"
        print(line)


def input_project():
    create_backup_note("input-project")
    projects = load_projects()

    print("\n=== New Build ===")
    title = prompt("Title")
    status = normalize_status(prompt("Status (Complete / In Progress / Archived)", default="Complete"))
    alt = prompt("Image alt text (what’s in the photo)", default=title, optional=True)

    image_path = prompt("Path to image file (drag/drop the file here)")
    image_rel = copy_image_into_site(image_path, title)

    description = prompt_multiline("Description (you can type multiple lines)")
    bullets = prompt_bullets()
    tags = prompt_tags()

    links = []
    if prompt_yes_no("Add links now? (y/n)", default="n"):
        links = prompt_links([])

    gallery_images = collect_extra_images(title, existing_images=[])

    project = {
        "title": title,
        "slug": slugify(title),
        "status": status,
        "cover_image": image_rel,
        "image": image_rel,      # legacy/backwards compat
        "images": gallery_images,
        "alt": alt,
        "description": description,
        "bullets": bullets,
        "tags": tags,            # <-- NEW: per-card tags for filtering
        "links": links,
        "steps": [],
        "created": datetime.now().isoformat(timespec="seconds"),
    }

    projects.insert(0, project)
    save_projects(projects)

    rebuild_all(projects)
    print("\nAdded build and rebuilt site pages ✅")


def edit_project():
    create_backup_note("edit-project")
    projects = load_projects()
    if not projects:
        print("No builds yet.")
        return

    print("\n=== Edit Build ===")
    list_projects(projects)
    idx = choose_project_index(projects)
    if idx < 0:
        print("Cancelled.")
        return

    p = projects[idx]
    old_title = p.get("title", "Untitled")
    print(f"\nEditing: {old_title}")

    new_title = prompt("Title", default=old_title)
    p["title"] = new_title
    p["status"] = normalize_status(prompt("Status", default=p.get("status", "Complete")))

    p["description"] = prompt_multiline("Description (multi-line)", default=p.get("description", ""))

    bullets_mode = prompt("Bullets (keep / edit / clear)", default="keep", optional=True).strip().lower()
    if bullets_mode in ["edit", "e"]:
        p["bullets"] = prompt_bullets(default_list=p.get("bullets", []))
    elif bullets_mode in ["clear", "remove"]:
        p["bullets"] = []

    tags_mode = prompt("Tags (keep / edit / clear)", default="keep", optional=True).strip().lower()
    if tags_mode in ["edit", "e"]:
        p["tags"] = prompt_tags(default_list=p.get("tags", []))
    elif tags_mode in ["clear", "remove"]:
        p["tags"] = []

    p["links"] = prompt_links(default_links=p.get("links", []))

    if prompt_yes_no("Replace cover image? (y/n)", default="n"):
        image_path = prompt("Path to new cover image")
        try:
            image_rel = copy_image_into_site(image_path, new_title)
            p["cover_image"] = image_rel
            p["image"] = image_rel
        except FileNotFoundError as e:
            print(e)
            print("Keeping existing cover image.")

    p["images"] = collect_extra_images(new_title, existing_images=p.get("images", []))

    if prompt_yes_no("Update image alt text? (y/n)", default="n"):
        p["alt"] = prompt("Image alt text", default=p.get("alt", new_title), optional=True)

    if new_title != old_title and (not p.get("slug") or p.get("slug") == slugify(old_title)):
        p["slug"] = slugify(new_title)

    p["updated"] = datetime.now().isoformat(timespec="seconds")
    save_projects(projects)
    rebuild_all(projects)
    print("\nUpdated build and rebuilt site pages ✅")


def delete_project():
    create_backup_note("delete-project")
    projects = load_projects()
    if not projects:
        print("No builds yet.")
        return

    print("\n=== Delete Build ===")
    list_projects(projects)
    idx = choose_project_index(projects)
    if idx < 0:
        print("Cancelled.")
        return

    title = projects[idx].get("title", "Untitled")
    if not prompt_yes_no(f"Delete '{title}' permanently? (y/n)", default="n"):
        print("Cancelled.")
        return

    projects.pop(idx)
    save_projects(projects)
    rebuild_all(projects)
    print("\nDeleted build and rebuilt site pages ✅")


def edit_project_steps():
    create_backup_note("edit-story")
    projects = load_projects()
    if not projects:
        print("No builds yet.")
        return

    print("\n=== Edit Build Story Sections ===")
    list_projects(projects)
    idx = choose_project_index(projects)
    if idx < 0:
        print("Cancelled.")
        return

    project = projects[idx]
    existing_steps = project.get("steps") or []
    print(f"\nSelected: {project.get('title', 'Untitled')} ({len(existing_steps)} existing story sections)")

    mode = prompt("Mode (add / replace / clear)", default="add", optional=True).strip().lower()
    if mode in ["clear", "remove"]:
        project["steps"] = []
        project["updated"] = datetime.now().isoformat(timespec="seconds")
        save_projects(projects)
        rebuild_all(projects)
        print("\nCleared all story sections and rebuilt pages ✅")
        return

    if mode in ["replace", "reset"]:
        steps = []
    else:
        steps = list(existing_steps)

    while True:
        step_no = len(steps) + 1
        step_title = prompt(f"Story section {step_no} title", default=f"Part {step_no}", optional=True)
        step_text = prompt_multiline("Story text (multi-line)", default="")

        add_photo = prompt("Add section photo? (y/n)", default="n", optional=True).lower()
        step_image = ""
        step_alt = ""
        if add_photo == "y":
            image_path = prompt("Path to image file (drag/drop)")
            step_image = copy_image_into_site(image_path, f"{project.get('title', 'project')}-step-{step_no}")
            step_alt = prompt("Section image alt text", default=step_title, optional=True)

        steps.append(
            {
                "title": step_title,
                "text": step_text,
                "image": step_image,
                "alt": step_alt,
            }
        )

        more = prompt("Add another section? (y/n)", default="y", optional=True).lower()
        if more != "y":
            break

    project["steps"] = steps
    project["updated"] = datetime.now().isoformat(timespec="seconds")
    save_projects(projects)

    rebuild_all(projects)
    print("\nSaved build story sections and rebuilt pages ✅")


def input_repair():
    create_backup_note("input-repair")
    repairs = load_repairs()

    print("\n=== New Circuit Troubleshooting Entry ===")
    title = prompt("Title (short)", default="Circuit Troubleshooting", optional=True)
    date = prompt("Date (YYYY-MM-DD)", default=datetime.now().strftime("%Y-%m-%d"), optional=True)
    status = prompt("Status (In Progress / Fixed / Monitoring)", default="Fixed", optional=True)

    device = prompt("Device / Board", optional=True)
    symptom = prompt_multiline("Symptom (multi-line)", default="")
    diagnosis = prompt_multiline("Diagnosis (multi-line)", default="")
    fix = prompt_multiline("Fix / What worked (multi-line)", default="")

    add_photo = prompt("Add a photo? (y/n)", default="y", optional=True).lower()
    image_rel = ""
    alt = ""
    if add_photo == "y":
        image_path = prompt("Path to image file (drag/drop)")
        image_rel = copy_image_into_site(image_path, title)
        alt = prompt("Image alt text", default=title, optional=True)

    notes = prompt_multiline("Extra notes (optional)", default="")
    tags = prompt_tags()

    entry = {
        "title": title,
        "date": date,
        "status": status,
        "device": device,
        "symptom": symptom,
        "diagnosis": diagnosis,
        "fix": fix,
        "image": image_rel,
        "alt": alt,
        "notes": notes,
        "tags": tags,  # <-- NEW: per-card tags for filtering
        "created": datetime.now().isoformat(timespec="seconds"),
    }

    repairs.insert(0, entry)
    save_repairs(repairs)

    rebuild_all()
    print("\nAdded troubleshooting entry and updated repairs.html ✅")


def edit_repair():
    create_backup_note("edit-repair")
    repairs = load_repairs()
    if not repairs:
        print("No repair logs yet.")
        return

    print("\n=== Edit Troubleshooting Entry ===")
    list_repairs(repairs)
    idx = choose_repair_index(repairs)
    if idx < 0:
        print("Cancelled.")
        return

    r = repairs[idx]
    title = r.get("title", "Circuit Troubleshooting")
    print(f"\nEditing: {title}")

    r["title"] = prompt("Title", default=title, optional=True)
    r["date"] = prompt("Date (YYYY-MM-DD)", default=r.get("date", ""), optional=True)
    r["status"] = prompt("Status", default=r.get("status", "Fixed"), optional=True)
    r["device"] = prompt("Device / Board", default=r.get("device", ""), optional=True)
    r["symptom"] = prompt_multiline("Symptom (multi-line)", default=r.get("symptom", ""))
    r["diagnosis"] = prompt_multiline("Diagnosis (multi-line)", default=r.get("diagnosis", ""))
    r["fix"] = prompt_multiline("Fix / What worked (multi-line)", default=r.get("fix", ""))
    r["notes"] = prompt_multiline("Extra notes", default=r.get("notes", ""))

    tags_mode = prompt("Tags (keep / edit / clear)", default="keep", optional=True).strip().lower()
    if tags_mode in ["edit", "e"]:
        r["tags"] = prompt_tags(default_list=r.get("tags", []))
    elif tags_mode in ["clear", "remove"]:
        r["tags"] = []

    image_mode = prompt("Photo (keep / replace / clear)", default="keep", optional=True).strip().lower()
    if image_mode in ["replace", "r"]:
        image_path = prompt("Path to image file")
        try:
            r["image"] = copy_image_into_site(image_path, r.get("title", "repair"))
            r["alt"] = prompt("Image alt text", default=r.get("alt", r.get("title", "Repair")), optional=True)
        except FileNotFoundError as e:
            print(e)
            print("Keeping existing image.")
    elif image_mode in ["clear", "remove"]:
        r["image"] = ""
        r["alt"] = ""

    r["updated"] = datetime.now().isoformat(timespec="seconds")
    save_repairs(repairs)
    rebuild_all()
    print("\nUpdated troubleshooting entry and rebuilt site pages ✅")


def delete_repair():
    create_backup_note("delete-repair")
    repairs = load_repairs()
    if not repairs:
        print("No repair logs yet.")
        return

    print("\n=== Delete Troubleshooting Entry ===")
    list_repairs(repairs)
    idx = choose_repair_index(repairs)
    if idx < 0:
        print("Cancelled.")
        return

    title = repairs[idx].get("title", "Untitled Repair")
    if not prompt_yes_no(f"Delete '{title}' permanently? (y/n)", default="n"):
        print("Cancelled.")
        return

    repairs.pop(idx)
    save_repairs(repairs)
    rebuild_all()
    print("\nDeleted troubleshooting entry and rebuilt site pages ✅")


def edit_site():
    create_backup_note("edit-site")
    site = load_site()

    print("\n=== Edit Site Settings ===")
    site["name"] = prompt("Name", default=site.get("name", "Your Name"))
    site["tagline"] = prompt("Tagline", default=site.get("tagline", ""))
    site["build_log_note"] = prompt("Build log note", default=site.get("build_log_note", ""))
    site["about_text"] = prompt_multiline("About text (multi-line)", default=site.get("about_text", ""))
    site["email"] = prompt("Email", default=site.get("email", ""))
    site["instagram_url"] = prompt("Instagram URL", default=site.get("instagram_url", ""))
    site["youtube_url"] = prompt("YouTube URL", default=site.get("youtube_url", ""))

    print("\nAbout tags (these show in the About section).")
    site["tags"] = prompt_tags(default_list=site.get("tags", []))

    save_site(site)

    rebuild_all()
    print("\nSaved site settings and updated index.html + repairs.html ✅")


def show_backups():
    backups = list_backups()
    if not backups:
        print("No backups yet.")
        return
    print("\nBackups (newest first):")
    for i, name in enumerate(backups, start=1):
        print(f"  {i}. {name}")


def undo_last_change():
    backups = list_backups()
    if not backups:
        print("No backups available.")
        return

    target = backups[0]
    if not prompt_yes_no(f"Restore latest backup '{target}'? (y/n)", default="y"):
        print("Cancelled.")
        return

    if not restore_backup(target):
        print("Restore failed.")
        return

    rebuild_all()
    print(f"\nRestored backup: {target} ✅")


def restore_backup_interactive():
    backups = list_backups()
    if not backups:
        print("No backups available.")
        return

    show_backups()
    raw = prompt("Select backup number", optional=True)
    if not raw or not raw.isdigit():
        print("Cancelled.")
        return

    idx = int(raw) - 1
    if idx < 0 or idx >= len(backups):
        print("Invalid selection.")
        return

    target = backups[idx]
    if not prompt_yes_no(f"Restore '{target}'? (y/n)", default="n"):
        print("Cancelled.")
        return

    if not restore_backup(target):
        print("Restore failed.")
        return

    rebuild_all()
    print(f"\nRestored backup: {target} ✅")


# ---------- Shop commands ----------
def _shop_choose_item(shop: dict, action: str = "choose") -> int:
    items = shop.get("items", [])
    if not items:
        print("No shop items yet.")
        return -1
    list_items(shop)
    raw = prompt(f"\nNumber to {action} (blank to cancel)", optional=True).strip()
    if not raw:
        return -1
    return _safe_index(raw, len(items))


def _prompt_collections(shop: dict, default_list=None) -> list:
    cols = sorted_collections(shop)
    if not cols:
        print("No collections defined yet — run edit-collections first.")
        return []
    print("\nCollections:")
    for i, c in enumerate(cols, start=1):
        print(f"  {i}. {c.get('title')}  ({c.get('slug')})")
    default_slugs = list(default_list or [])
    default_nums = ",".join(
        str(i) for i, c in enumerate(cols, start=1) if c.get("slug") in default_slugs
    )
    raw = prompt("Collection numbers (comma separated)", default=default_nums, optional=True).strip()
    if not raw:
        return default_slugs
    chosen = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= len(cols):
            slug = cols[int(part) - 1].get("slug")
            if slug and slug not in chosen:
                chosen.append(slug)
    return chosen


def _prompt_shipping(title: str, existing=None) -> dict:
    ship = dict(existing or {})
    print("\n--- Shipping ---")
    print("Box it, weigh it, then get a UPS quote from Indianapolis to a west-coast ZIP")
    print("(that's Zone 8, the worst case). Enter that quote and I'll add the 20% markup.")
    weight = prompt("Shipping weight (lb)", default=str(ship.get("weight_lb", "") or ""), optional=True).strip()
    box = prompt("Box size (L x W x H in)", default=str(ship.get("box_in", "") or ""), optional=True).strip()
    quote_raw = prompt("UPS Zone 8 quote ($)", default=str(ship.get("ups_zone8_quote", "") or ""), optional=True).strip()

    try:
        ship["weight_lb"] = float(weight) if weight else 0.0
    except ValueError:
        ship["weight_lb"] = 0.0
    ship["box_in"] = box
    try:
        ship["ups_zone8_quote"] = float(quote_raw.lstrip("$")) if quote_raw else 0.0
    except ValueError:
        ship["ups_zone8_quote"] = 0.0

    computed = compute_ship_price(ship["ups_zone8_quote"])
    if computed:
        print(f"  → shipping price: ${computed:,.0f}  (${ship['ups_zone8_quote']:,.2f} x {SHIP_MARKUP})")
    override = prompt("Shipping price to charge ($)", default=f"{computed:.0f}" if computed else "", optional=True).strip()
    try:
        ship["ship_price"] = float(override.lstrip("$")) if override else computed
    except ValueError:
        ship["ship_price"] = computed
    ship["local_pickup"] = prompt_yes_no("Offer free local pickup? (y/n)",
                                         default="y" if ship.get("local_pickup", True) else "n")
    return ship


def list_items(shop: dict):
    items = shop.get("items", [])
    if not items:
        print("No shop items yet.")
        return
    cmap = collection_map(shop)
    print("\nShop items:")
    for i, item in enumerate(items, start=1):
        state = item_state(item)
        flag = {"draft": "DRAFT ", "sold_out": "SOLD  ", "low": "LOW   ", "in_stock": "STOCK "}[state]
        price = fmt_price(item.get("price")) or "no price"
        cols = ", ".join((cmap.get(s) or {}).get("title", s) for s in (item.get("collections") or []))
        stock = item.get("stock", 0)
        warn = "  ⚠ no buy link" if item_needs_payment_link(item) else ""
        print(f"  {i}. [{flag}] {item.get('sku', '?'):<9} {item.get('title', 'Untitled')}")
        print(f"      {price} · qty {stock} · {cols or 'no collection'}{warn}")


def input_item():
    create_backup_note("input-item")
    shop = load_shop()

    print("\n=== Add Shop Item ===")
    title = prompt("Title (e.g. Roland Juno-106)")
    subtitle = prompt("One-line subtitle", optional=True)

    kind = prompt("Type (gear / part / kit)", default="gear", optional=True).strip().lower()
    if kind not in ("gear", "part", "kit"):
        kind = "gear"

    collections = _prompt_collections(shop)
    brand = prompt("Brand / manufacturer", optional=True)
    mpn = prompt("Manufacturer part number (e.g. 80017A)", optional=True)
    year = prompt("Year", optional=True)
    condition = prompt("Condition", default="Excellent" if kind == "gear" else "New", optional=True)

    print("\nModels this fits (helps people search - e.g. Juno-106, HS-60)")
    fits = _split_csv(prompt("Fits models (comma separated)", optional=True))

    price_raw = prompt("Price ($)", optional=True).strip()
    try:
        price = float(price_raw.lstrip("$")) if price_raw else 0.0
    except ValueError:
        price = 0.0

    stock_default = "1" if kind == "gear" else "0"
    stock_raw = prompt("Quantity in stock", default=stock_default, optional=True).strip()
    stock = int(stock_raw) if stock_raw.isdigit() else int(stock_default)

    description = prompt_multiline("Description (multi-line)")
    bullets = prompt_bullets()
    service_notes = prompt_multiline("What you serviced/did to it (optional)", default="")
    includes = _split_lines(prompt_multiline("What's included (one per line, optional)", default=""))
    tags = prompt_tags()

    cover = ""
    alt = title
    cover_path = prompt("Cover photo path (blank to skip)", optional=True)
    if cover_path:
        try:
            cover = copy_image_into_site(cover_path, title, subdir="shop")
            alt = prompt("Cover image alt text", default=title, optional=True)
        except FileNotFoundError as e:
            print(e)
    images = collect_extra_images(title, subdir="shop")

    shipping = _prompt_shipping(title)

    print("\n--- Payment links ---")
    print("Leave both blank for now and the item saves as a DRAFT (not published).")
    stripe_url = prompt("Stripe Payment Link URL", optional=True).strip()
    paypal_id = prompt("PayPal hosted button ID", optional=True).strip()

    status = "active" if (stripe_url or paypal_id) else "draft"
    if status == "draft":
        print("  → saved as DRAFT (add a payment link with edit-item to publish)")

    item = {
        "sku": next_sku(shop),
        "slug": slugify(title),
        "title": title,
        "subtitle": subtitle,
        "collections": collections,
        "item_type": kind,
        "brand": brand,
        "mpn": mpn,
        "fits_models": fits,
        "year": year,
        "condition": condition,
        "price": price,
        "stock": stock,
        "status": status,
        "cover_image": cover,
        "alt": alt,
        "images": images,
        "description": description,
        "bullets": bullets,
        "service_notes": service_notes,
        "includes": includes,
        "tags": tags,
        "shipping": shipping,
        "stripe_url": stripe_url,
        "paypal_button_id": paypal_id,
        "sold_date": None,
        "created": datetime.now().isoformat(timespec="seconds"),
    }

    shop["items"].insert(0, item)
    save_shop(shop)
    rebuild_all()
    print(f"\nAdded {item['sku']} — {title} ✅")
    if status == "active":
        print(f"View at shop/{item['slug']}.html")


def edit_item():
    create_backup_note("edit-item")
    shop = load_shop()
    print("\n=== Edit Shop Item ===")
    idx = _shop_choose_item(shop, "edit")
    if idx < 0:
        print("Cancelled.")
        return

    it = shop["items"][idx]
    print(f"\nEditing {it.get('sku')} — {it.get('title')}")

    it["title"] = prompt("Title", default=it.get("title", ""), optional=True)
    it["subtitle"] = prompt("Subtitle", default=it.get("subtitle", ""), optional=True)
    kind = prompt("Type (gear / part / kit)", default=it.get("item_type", "gear"), optional=True).strip().lower()
    it["item_type"] = kind if kind in ("gear", "part", "kit") else it.get("item_type", "gear")
    it["collections"] = _prompt_collections(shop, it.get("collections"))
    it["brand"] = prompt("Brand", default=it.get("brand", ""), optional=True)
    it["mpn"] = prompt("Manufacturer part number", default=it.get("mpn", ""), optional=True)
    it["year"] = prompt("Year", default=str(it.get("year", "")), optional=True)
    it["condition"] = prompt("Condition", default=it.get("condition", ""), optional=True)

    fits_default = ", ".join(it.get("fits_models") or [])
    it["fits_models"] = _split_csv(prompt("Fits models (comma separated)", default=fits_default, optional=True))

    price_raw = prompt("Price ($)", default=str(it.get("price", 0) or ""), optional=True).strip()
    try:
        it["price"] = float(price_raw.lstrip("$")) if price_raw else 0.0
    except ValueError:
        pass

    stock_raw = prompt("Quantity in stock", default=str(it.get("stock", 0)), optional=True).strip()
    if stock_raw.isdigit():
        it["stock"] = int(stock_raw)

    it["description"] = prompt_multiline("Description", default=it.get("description", ""))
    it["service_notes"] = prompt_multiline("What you serviced/did to it", default=it.get("service_notes", ""))

    bullets_mode = prompt("Bullets (keep / edit / clear)", default="keep", optional=True).strip().lower()
    if bullets_mode in ["edit", "e"]:
        it["bullets"] = prompt_bullets(default_list=it.get("bullets", []))
    elif bullets_mode in ["clear", "remove"]:
        it["bullets"] = []

    includes_mode = prompt("Included items (keep / edit / clear)", default="keep", optional=True).strip().lower()
    if includes_mode in ["edit", "e"]:
        it["includes"] = _split_lines(prompt_multiline("What's included (one per line)",
                                                       default="\n".join(it.get("includes") or [])))
    elif includes_mode in ["clear", "remove"]:
        it["includes"] = []

    tags_mode = prompt("Tags (keep / edit / clear)", default="keep", optional=True).strip().lower()
    if tags_mode in ["edit", "e"]:
        it["tags"] = prompt_tags(default_list=it.get("tags", []))
    elif tags_mode in ["clear", "remove"]:
        it["tags"] = []

    cover_mode = prompt("Cover photo (keep / replace / clear)", default="keep", optional=True).strip().lower()
    if cover_mode in ["replace", "r"]:
        p = prompt("Path to image file")
        try:
            it["cover_image"] = copy_image_into_site(p, it.get("title", "item"), subdir="shop")
            it["alt"] = prompt("Alt text", default=it.get("alt", it.get("title", "")), optional=True)
        except FileNotFoundError as e:
            print(e)
            print("Keeping existing cover.")
    elif cover_mode in ["clear", "remove"]:
        it["cover_image"] = ""

    it["images"] = collect_extra_images(it.get("title", "item"), it.get("images", []), subdir="shop")

    if prompt_yes_no("Update shipping? (y/n)", default="n"):
        it["shipping"] = _prompt_shipping(it.get("title", "item"), it.get("shipping"))

    it["stripe_url"] = prompt("Stripe Payment Link URL", default=it.get("stripe_url", ""), optional=True).strip()
    it["paypal_button_id"] = prompt("PayPal hosted button ID", default=it.get("paypal_button_id", ""), optional=True).strip()

    if it.get("stripe_url") or it.get("paypal_button_id"):
        if it.get("status") == "draft" and prompt_yes_no("Publish this item now? (y/n)", default="y"):
            it["status"] = "active"
    else:
        print("  ⚠ No payment link — item will show 'email for price' instead of Buy buttons.")

    it["updated"] = datetime.now().isoformat(timespec="seconds")
    save_shop(shop)
    rebuild_all()
    print("\nUpdated shop item ✅")


def set_stock():
    """Fast restock for parts and kits."""
    create_backup_note("set-stock")
    shop = load_shop()
    print("\n=== Set Stock ===")
    idx = _shop_choose_item(shop, "restock")
    if idx < 0:
        print("Cancelled.")
        return

    it = shop["items"][idx]
    print(f"\n{it.get('sku')} — {it.get('title')}  (currently {it.get('stock', 0)})")
    raw = prompt("New quantity", default=str(it.get("stock", 0))).strip()
    if not raw.isdigit():
        print("Not a number. Cancelled.")
        return

    it["stock"] = int(raw)
    if it["stock"] > 0:
        it["sold_date"] = None
    it["updated"] = datetime.now().isoformat(timespec="seconds")
    save_shop(shop)
    rebuild_all()
    print(f"\n{it.get('sku')} stock set to {it['stock']} ✅")


def mark_sold():
    """Run this the moment a sale notification lands."""
    create_backup_note("mark-sold")
    shop = load_shop()
    print("\n=== Mark Sold ===")
    idx = _shop_choose_item(shop, "mark sold")
    if idx < 0:
        print("Cancelled.")
        return

    it = shop["items"][idx]
    kind = it.get("item_type", "gear")
    if kind == "gear":
        it["stock"] = 0
    else:
        sold_raw = prompt("How many sold?", default="1").strip()
        sold = int(sold_raw) if sold_raw.isdigit() else 1
        it["stock"] = max(0, int(it.get("stock", 0) or 0) - sold)

    if it["stock"] == 0:
        it["sold_date"] = datetime.now().strftime("%Y-%m-%d")

    save_shop(shop)
    rebuild_all()
    print(f"\n{it.get('sku')} — {it.get('title')}: {it['stock']} left ✅")
    if it["stock"] == 0:
        print("\n⚠ Now go deactivate the OTHER processor's button so it can't sell twice:")
        if it.get("stripe_url"):
            print("   Stripe:  dashboard.stripe.com → Payment Links → deactivate")
        if it.get("paypal_button_id"):
            print("   PayPal:  paypal.com → Pay & Get Paid → PayPal Buttons → remove")
    print("Then pack it, ship it, and email the tracking number.")


def delete_item():
    create_backup_note("delete-item")
    shop = load_shop()
    print("\n=== Delete Shop Item ===")
    idx = _shop_choose_item(shop, "delete")
    if idx < 0:
        print("Cancelled.")
        return

    it = shop["items"][idx]
    title = it.get("title", "Untitled")
    if not prompt_yes_no(f"Delete '{title}' ({it.get('sku')}) permanently? (y/n)", default="n"):
        print("Cancelled.")
        return

    slug = it.get("slug", "")
    shop["items"].pop(idx)
    save_shop(shop)

    page = os.path.join(SHOP_DIR, f"{slug}.html")
    if slug and os.path.exists(page):
        os.remove(page)

    rebuild_all()
    print("\nDeleted shop item ✅  (its part number is retired, not reused)")


def edit_collections():
    create_backup_note("edit-collections")
    shop = load_shop()

    while True:
        cols = sorted_collections(shop)
        print("\n=== Collections ===")
        if cols:
            for i, c in enumerate(cols, start=1):
                n = len(items_in_collection(shop, c.get("slug", "")))
                print(f"  {i}. {c.get('title')}  ({c.get('slug')}) — {n} item(s)")
        else:
            print("  none yet")
        print("\n  a) add   e) edit   d) delete   q) done")
        cmd = prompt("Choose", default="q", optional=True).strip().lower()

        if cmd in ("q", "", "done"):
            break
        elif cmd == "a":
            title = prompt("Collection title")
            if not title:
                continue
            c = {
                "slug": slugify(title),
                "title": title,
                "blurb": prompt("Short blurb", optional=True),
                "cover_image": "",
                "order": len(shop["collections"]) + 1,
            }
            cover = prompt("Cover photo path (blank to skip)", optional=True)
            if cover:
                try:
                    c["cover_image"] = copy_image_into_site(cover, title, subdir="shop/collections")
                except FileNotFoundError as e:
                    print(e)
            shop["collections"].append(c)
        elif cmd == "e" and cols:
            raw = prompt("Number to edit", optional=True).strip()
            i = _safe_index(raw, len(cols))
            if i < 0:
                continue
            c = cols[i]
            c["title"] = prompt("Title", default=c.get("title", ""), optional=True)
            c["blurb"] = prompt("Blurb", default=c.get("blurb", ""), optional=True)
            order_raw = prompt("Sort order", default=str(c.get("order", 999)), optional=True).strip()
            if order_raw.isdigit():
                c["order"] = int(order_raw)
            mode = prompt("Cover photo (keep / replace / clear)", default="keep", optional=True).strip().lower()
            if mode in ("replace", "r"):
                p = prompt("Path to image file")
                try:
                    c["cover_image"] = copy_image_into_site(p, c.get("title", "collection"),
                                                            subdir="shop/collections")
                except FileNotFoundError as e:
                    print(e)
            elif mode in ("clear", "remove"):
                c["cover_image"] = ""
        elif cmd == "d" and cols:
            raw = prompt("Number to delete", optional=True).strip()
            i = _safe_index(raw, len(cols))
            if i < 0:
                continue
            c = cols[i]
            n = len(items_in_collection(shop, c.get("slug", "")))
            if n and not prompt_yes_no(f"{n} item(s) reference this. Delete anyway? (y/n)", default="n"):
                continue
            if not prompt_yes_no(f"Delete '{c.get('title')}'? (y/n)", default="n"):
                continue
            slug = c.get("slug", "")
            shop["collections"] = [x for x in shop["collections"] if x.get("slug") != slug]
            for item in shop["items"]:
                item["collections"] = [s for s in (item.get("collections") or []) if s != slug]
            page = os.path.join(SHOP_DIR, f"{slug}.html")
            if slug and os.path.exists(page):
                os.remove(page)

    save_shop(shop)
    rebuild_all()
    print("\nCollections updated ✅")


def print_menu():
    print("\nCommands:")
    print("  1) input-project   (add new build)")
    print("  2) edit-project    (edit build details)")
    print("  3) edit-story      (add/replace build story sections with photos + text)")
    print("  4) list-projects   (show builds list)")
    print("  5) rebuild         (regenerate index.html + repairs.html + project pages)")
    print("  6) edit-site       (name, about, contact, tags)")
    print("  7) input-repair    (add troubleshooting entry)")
    print("  8) list-repairs    (show troubleshooting list)")
    print("  9) edit-repair     (edit troubleshooting entry)")
    print(" 10) delete-project  (remove build + project page)")
    print(" 11) delete-repair   (remove troubleshooting entry)")
    print(" 12) undo-last       (restore latest backup)")
    print(" 13) list-backups    (show JSON backups)")
    print(" 14) restore-backup  (choose backup to restore)")
    print(" 15) publish-github  (git add/commit/push all changes)")
    print(" 16) web-ui          (open browser admin menu)")
    print("  --- shop ---")
    print(" 17) list-items      (show shop inventory)")
    print(" 18) input-item      (add gear, part, or mod kit)")
    print(" 19) edit-item       (edit a listing / add payment links)")
    print(" 20) mark-sold       (someone bought it - run this first)")
    print(" 21) set-stock       (restock a part or kit)")
    print(" 22) delete-item     (remove a listing + its page)")
    print(" 23) edit-collections(add/edit/remove shop collections)")
    print("  q) quit")


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip().lower()
        if arg in ["web-ui", "web", "ui"]:
            host = "127.0.0.1"
            port = 8081
            if len(sys.argv) > 2 and sys.argv[2].strip():
                host = sys.argv[2].strip()
            if len(sys.argv) > 3 and sys.argv[3].strip().isdigit():
                port = int(sys.argv[3].strip())
            start_web_ui(host=host, port=port)
            return

    while True:
        print_menu()
        cmd = prompt("\nEnter command").lower().strip()

        if cmd in ["q", "quit", "exit", "0"]:
            print("Goodbye.")
            break
        if cmd in ["1", "input-project", "add", "new"]:
            input_project()
        elif cmd in ["2", "edit-project", "project-edit"]:
            edit_project()
        elif cmd in ["3", "edit-story", "project-steps", "steps"]:
            edit_project_steps()
        elif cmd in ["4", "list-projects", "list"]:
            list_projects(load_projects())
        elif cmd in ["5", "rebuild", "build"]:
            rebuild_all()
            print("\nRebuilt index.html + repairs.html + shop.html + projects/*.html + shop/*.html ✅")
        elif cmd in ["6", "edit-site", "site"]:
            edit_site()
        elif cmd in ["7", "input-repair", "repair", "new-repair"]:
            input_repair()
        elif cmd in ["8", "list-repairs", "repairs", "list-repair"]:
            list_repairs(load_repairs())
        elif cmd in ["9", "edit-repair"]:
            edit_repair()
        elif cmd in ["10", "delete-project", "remove-project"]:
            delete_project()
        elif cmd in ["11", "delete-repair", "remove-repair"]:
            delete_repair()
        elif cmd in ["12", "undo-last", "undo"]:
            undo_last_change()
        elif cmd in ["13", "list-backups", "backups"]:
            show_backups()
        elif cmd in ["14", "restore-backup", "restore"]:
            restore_backup_interactive()
        elif cmd in ["15", "publish-github", "publish", "push"]:
            publish_to_github()
        elif cmd in ["16", "web-ui", "web", "ui"]:
            host = prompt("Web host", default="127.0.0.1", optional=True)
            port_raw = prompt("Web port", default="8081", optional=True)
            port = 8081
            if port_raw.isdigit():
                port = int(port_raw)
            start_web_ui(host=host or "127.0.0.1", port=port)
        elif cmd in ["17", "list-items", "items", "inventory"]:
            list_items(load_shop())
        elif cmd in ["18", "input-item", "add-item", "new-item"]:
            input_item()
        elif cmd in ["19", "edit-item"]:
            edit_item()
        elif cmd in ["20", "mark-sold", "sold"]:
            mark_sold()
        elif cmd in ["21", "set-stock", "restock", "stock"]:
            set_stock()
        elif cmd in ["22", "delete-item", "remove-item"]:
            delete_item()
        elif cmd in ["23", "edit-collections", "collections"]:
            edit_collections()
        else:
            print("Unknown command.")


if __name__ == "__main__":
    main()
