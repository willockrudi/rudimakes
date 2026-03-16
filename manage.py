
import json
import os
import re
import shutil
import html
import subprocess
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))

# Main Builds page
INDEX_PATH = os.path.join(ROOT, "index.html")
TEMPLATE_PATH = os.path.join(ROOT, "template.html")
PROJECT_TEMPLATE_PATH = os.path.join(ROOT, "project_template.html")
PROJECTS_DIR = os.path.join(ROOT, "projects")

# Troubleshooting page
REPAIRS_INDEX_PATH = os.path.join(ROOT, "repairs.html")
REPAIRS_TEMPLATE_PATH = os.path.join(ROOT, "repairs_template.html")

# Data files
DATA_PATH = os.path.join(ROOT, "projects.json")
REPAIRS_PATH = os.path.join(ROOT, "repairs.json")
SITE_PATH = os.path.join(ROOT, "site.json")

# Assets
IMAGES_DIR = os.path.join(ROOT, "images")
BACKUPS_DIR = os.path.join(ROOT, ".backups")

# Markers
PROJECTS_START = "<!-- PROJECTS_START -->"
PROJECTS_END = "<!-- PROJECTS_END -->"
REPAIRS_START = "<!-- REPAIRS_START -->"
REPAIRS_END = "<!-- REPAIRS_END -->"
TAGS_START = "<!-- TAGS_START -->"
TAGS_END = "<!-- TAGS_END -->"
PROJECT_STEPS_START = "<!-- PROJECT_STEPS_START -->"
PROJECT_STEPS_END = "<!-- PROJECT_STEPS_END -->"


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
    return [DATA_PATH, REPAIRS_PATH, SITE_PATH]


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


def _web_layout(title: str, body: str, message: str = "") -> str:
    message_html = ""
    if message:
        message_html = f'<p style="padding:10px;border-radius:8px;background:#eef6ff;border:1px solid #c7ddff;">{html.escape(message)}</p>'

    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; margin: 0; background: #f5f6f8; color: #1f2937; }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(320px,1fr)); gap: 16px; }}
    .card {{ background: white; border-radius: 12px; padding: 16px; box-shadow: 0 4px 14px rgba(0,0,0,0.06); }}
    h1,h2,h3 {{ margin: 0 0 12px; }}
    label {{ display: block; margin: 8px 0 4px; font-size: 14px; color: #374151; }}
    input,textarea,select {{ width: 100%; padding: 10px; border: 1px solid #d1d5db; border-radius: 8px; box-sizing: border-box; }}
    textarea {{ min-height: 90px; }}
    button {{ margin-top: 10px; border: none; background: #2563eb; color: white; padding: 10px 12px; border-radius: 8px; cursor: pointer; }}
    button.alt {{ background: #4b5563; }}
    button.warn {{ background: #dc2626; }}
    .row {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .row form {{ margin: 0; }}
    .list {{ margin: 0; padding-left: 18px; }}
    .muted {{ color: #6b7280; font-size: 13px; }}
    a {{ color: #2563eb; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>RudiMakes Admin</h1>
    <p class="muted">Web UI for projects, repairs, rebuild, and publish.</p>
    {message_html}
    {body}
  </div>
</body>
</html>
""".strip()


def start_web_ui(host: str = "127.0.0.1", port: int = 8081):
    def parse_form(handler: BaseHTTPRequestHandler) -> dict[str, str]:
        length = int(handler.headers.get("Content-Length", "0") or "0")
        raw = handler.rfile.read(length).decode("utf-8") if length > 0 else ""
        parsed = parse_qs(raw, keep_blank_values=True)
        return {k: (v[0] if v else "") for k, v in parsed.items()}

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

        def _render_home(self, message: str = ""):
            projects = load_projects()
            repairs = load_repairs()
            site = load_site()

            project_items = "\n".join([
                f"<li><strong>{html.escape(p.get('title','Untitled'))}</strong> "
                f"<span class='muted'>[{html.escape(p.get('status','Complete'))}]</span> "
                f"<a href='/project/edit?idx={i}'>Edit</a> "
                f"<a href='/story?idx={i}'>Story</a>"
                f"<form method='post' action='/projects/delete' style='display:inline; margin-left:8px;'>"
                f"<input type='hidden' name='idx' value='{i}' />"
                f"<button class='warn' type='submit'>Delete</button></form></li>"
                for i, p in enumerate(projects)
            ]) or "<li class='muted'>No builds yet.</li>"

            repair_items = "\n".join([
                f"<li><strong>{html.escape(r.get('title','Untitled Repair'))}</strong>"
                f" <a href='/repair/edit?idx={i}'>Edit</a>"
                f"<form method='post' action='/repairs/delete' style='display:inline; margin-left:8px;'>"
                f"<input type='hidden' name='idx' value='{i}' />"
                f"<button class='warn' type='submit'>Delete</button></form></li>"
                for i, r in enumerate(repairs)
            ]) or "<li class='muted'>No repairs yet.</li>"

            body = f"""
<div class='grid'>
  <div class='card'>
    <h2>Site Actions</h2>
    <div class='row'>
      <form method='post' action='/actions/rebuild'><button type='submit'>Rebuild Site</button></form>
      <form method='post' action='/actions/publish'>
        <input type='text' name='commit_message' placeholder='Commit message (optional)' />
        <button type='submit'>Publish GitHub</button>
      </form>
    </div>
  </div>

  <div class='card'>
    <h2>Edit Site Info</h2>
    <form method='post' action='/site/save'>
      <label>Name</label><input name='name' value='{html.escape(site.get('name',''))}' />
      <label>Tagline</label><input name='tagline' value='{html.escape(site.get('tagline',''))}' />
      <label>Build Note</label><input name='build_log_note' value='{html.escape(site.get('build_log_note',''))}' />
      <label>About</label><textarea name='about_text'>{html.escape(site.get('about_text',''))}</textarea>
      <label>Email</label><input name='email' value='{html.escape(site.get('email',''))}' />
      <label>Instagram URL</label><input name='instagram_url' value='{html.escape(site.get('instagram_url',''))}' />
      <label>YouTube URL</label><input name='youtube_url' value='{html.escape(site.get('youtube_url',''))}' />
      <label>About Tags (comma-separated)</label><input name='tags' value='{html.escape(', '.join(site.get('tags') or []))}' />
      <button type='submit'>Save Site</button>
    </form>
  </div>

  <div class='card'>
    <h2>Add Build</h2>
    <form method='post' action='/projects/add'>
      <label>Title</label><input name='title' required />
      <label>Status</label>
      <select name='status'><option>Complete</option><option>In Progress</option><option>Archived</option></select>
      <label>Description</label><textarea name='description'></textarea>
      <label>Bullets (one per line)</label><textarea name='bullets'></textarea>
      <label>Tags (comma-separated)</label><input name='tags' />
      <label>Cover image path or URL</label><input name='image_path' placeholder='images/test-photo.svg or /full/path/img.jpg' />
      <button type='submit'>Add Build</button>
    </form>
  </div>

  <div class='card'>
    <h2>Add Repair</h2>
    <form method='post' action='/repairs/add'>
      <label>Title</label><input name='title' required />
      <label>Date</label><input name='date' value='{datetime.now().strftime('%Y-%m-%d')}' />
      <label>Status</label><input name='status' value='Fixed' />
      <label>Device</label><input name='device' />
      <label>Symptom</label><textarea name='symptom'></textarea>
      <label>Diagnosis</label><textarea name='diagnosis'></textarea>
      <label>Fix</label><textarea name='fix'></textarea>
      <label>Notes</label><textarea name='notes'></textarea>
      <label>Tags (comma-separated)</label><input name='tags' />
      <label>Photo path or URL</label><input name='image_path' />
      <button type='submit'>Add Repair</button>
    </form>
  </div>

  <div class='card'>
    <h2>Builds</h2>
    <ol class='list'>{project_items}</ol>
  </div>

  <div class='card'>
    <h2>Repairs</h2>
    <ol class='list'>{repair_items}</ol>
  </div>
</div>
"""
            self._send_html(_web_layout("RudiMakes Admin", body, message))

        def _render_story(self, idx: int, message: str = ""):
            projects = load_projects()
            if idx < 0 or idx >= len(projects):
                self._redirect("/", "Invalid project selection")
                return

            project = projects[idx]
            steps = project.get("steps") or []
            section_items = "\n".join([
                f"<li><strong>{i+1}. {html.escape(s.get('title','Part'))}</strong>"
                f" <a href='/story/edit?idx={idx}&step_idx={i}'>Edit</a>"
                f"<form method='post' action='/story/delete' style='display:inline; margin-left:8px;'>"
                f"<input type='hidden' name='idx' value='{idx}' />"
                f"<input type='hidden' name='step_idx' value='{i}' />"
                f"<button class='warn' type='submit'>Delete</button></form></li>"
                for i, s in enumerate(steps)
            ]) or "<li class='muted'>No story sections yet.</li>"

            body = f"""
<div class='card'>
  <h2>Build Story: {html.escape(project.get('title','Untitled'))}</h2>
  <p><a href='/'>← Back to dashboard</a></p>
  <ol class='list'>{section_items}</ol>
  <form method='post' action='/story/clear'>
    <input type='hidden' name='idx' value='{idx}' />
    <button class='warn' type='submit'>Clear All Sections</button>
  </form>
</div>

<div class='card'>
  <h3>Add Story Section</h3>
  <form method='post' action='/story/add'>
    <input type='hidden' name='idx' value='{idx}' />
    <label>Section title</label><input name='title' placeholder='Part {len(steps)+1}' />
    <label>Section text</label><textarea name='text'></textarea>
    <label>Image path or URL</label><input name='image_path' />
    <label>Image alt text</label><input name='alt' />
    <button type='submit'>Add Section</button>
  </form>
</div>
"""
            self._send_html(_web_layout("Build Story", body, message))

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
<div class='card'>
    <h2>Edit Build: {html.escape(p.get('title','Untitled'))}</h2>
    <p><a href='/'>← Back to dashboard</a></p>
    <form method='post' action='/projects/save'>
        <input type='hidden' name='idx' value='{idx}' />
        <label>Title</label><input name='title' value='{html.escape(p.get('title',''))}' required />
        <label>Status</label><select name='status'>{status_opts}</select>
        <label>Description</label><textarea name='description'>{html.escape(p.get('description',''))}</textarea>
        <label>Bullets (one per line)</label><textarea name='bullets'>{html.escape(chr(10).join(p.get('bullets') or []))}</textarea>
        <label>Tags (comma-separated)</label><input name='tags' value='{html.escape(', '.join(p.get('tags') or []))}' />
        <label>Cover image path or URL</label><input name='cover_image' value='{html.escape(p.get('cover_image') or p.get('image') or '')}' />
        <label>Alt text</label><input name='alt' value='{html.escape(p.get('alt') or p.get('title') or '')}' />
        <label>Gallery image paths/URLs (one per line)</label><textarea name='images'>{html.escape(chr(10).join(p.get('images') or []))}</textarea>
        <label>Links (one per line: label|url)</label><textarea name='links'>{html.escape(_links_to_lines(p.get('links') or []))}</textarea>
        <button type='submit'>Save Build</button>
    </form>
</div>
"""
                        self._send_html(_web_layout("Edit Build", body, message))

                def _render_repair_edit(self, idx: int, message: str = ""):
                        repairs = load_repairs()
                        if idx < 0 or idx >= len(repairs):
                                self._redirect("/", "Invalid repair selection")
                                return

                        r = repairs[idx]
                        body = f"""
<div class='card'>
    <h2>Edit Repair: {html.escape(r.get('title','Untitled Repair'))}</h2>
    <p><a href='/'>← Back to dashboard</a></p>
    <form method='post' action='/repairs/save'>
        <input type='hidden' name='idx' value='{idx}' />
        <label>Title</label><input name='title' value='{html.escape(r.get('title',''))}' required />
        <label>Date</label><input name='date' value='{html.escape(r.get('date',''))}' />
        <label>Status</label><input name='status' value='{html.escape(r.get('status',''))}' />
        <label>Device</label><input name='device' value='{html.escape(r.get('device',''))}' />
        <label>Symptom</label><textarea name='symptom'>{html.escape(r.get('symptom',''))}</textarea>
        <label>Diagnosis</label><textarea name='diagnosis'>{html.escape(r.get('diagnosis',''))}</textarea>
        <label>Fix</label><textarea name='fix'>{html.escape(r.get('fix',''))}</textarea>
        <label>Notes</label><textarea name='notes'>{html.escape(r.get('notes',''))}</textarea>
        <label>Tags (comma-separated)</label><input name='tags' value='{html.escape(', '.join(r.get('tags') or []))}' />
        <label>Photo path or URL</label><input name='image' value='{html.escape(r.get('image') or '')}' />
        <label>Alt text</label><input name='alt' value='{html.escape(r.get('alt') or r.get('title') or '')}' />
        <button type='submit'>Save Repair</button>
    </form>
</div>
"""
                        self._send_html(_web_layout("Edit Repair", body, message))

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
                        body = f"""
<div class='card'>
    <h2>Edit Story Section: {html.escape(projects[idx].get('title','Untitled'))}</h2>
    <p><a href='/story?idx={idx}'>← Back to story</a></p>
    <form method='post' action='/story/save'>
        <input type='hidden' name='idx' value='{idx}' />
        <input type='hidden' name='step_idx' value='{step_idx}' />
        <label>Section title</label><input name='title' value='{html.escape(s.get('title',''))}' />
        <label>Section text</label><textarea name='text'>{html.escape(s.get('text',''))}</textarea>
        <label>Image path or URL</label><input name='image' value='{html.escape(s.get('image',''))}' />
        <label>Alt text</label><input name='alt' value='{html.escape(s.get('alt',''))}' />
        <button type='submit'>Save Section</button>
    </form>
</div>
"""
                        self._send_html(_web_layout("Edit Story Section", body, message))

        def do_GET(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            message = (query.get("msg") or [""])[0]

            if parsed.path == "/":
                self._render_home(message)
                return

            if parsed.path == "/story":
                idx_raw = (query.get("idx") or ["-1"])[0]
                idx = _safe_index(idx_raw, len(load_projects()))
                self._render_story(idx, message)
                return

            self._send_html(_web_layout("Not Found", "<div class='card'><h2>404</h2></div>"), status=404)

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


def collect_extra_images(title: str, existing_images=None):
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
            image_rel = copy_image_into_site(image_path, title)
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


def copy_image_into_site(image_path: str, title: str) -> str:
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # PowerShell drag/drop often includes quotes
    image_path = (image_path or "").strip().strip('"')

    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    ext = os.path.splitext(image_path)[1].lower()
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    base = slugify(title)
    dest_name = f"{date_prefix}-{base}{ext}"
    dest_path = os.path.join(IMAGES_DIR, dest_name)

    i = 2
    while os.path.exists(dest_path):
        dest_name = f"{date_prefix}-{base}-{i}{ext}"
        dest_path = os.path.join(IMAGES_DIR, dest_name)
        i += 1

    shutil.copy2(image_path, dest_path)
    return f"images/{dest_name}"


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
    print("  q) quit")


def main():
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
            print("\nRebuilt index.html + repairs.html + projects/*.html ✅")
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
        else:
            print("Unknown command.")


if __name__ == "__main__":
    main()
