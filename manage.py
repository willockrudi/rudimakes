
import json
import os
import re
import shutil
import html
import subprocess
from datetime import datetime

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
        print("Tip: make sure git auth is set up (SSH key or GitHub token).")
        return

    print("\n✅ Published to GitHub successfully.")


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
        else:
            print("Unknown command.")


if __name__ == "__main__":
    main()
