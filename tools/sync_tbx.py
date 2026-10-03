#!/usr/bin/env python3
"""
Copy the TBX investor page into this site as the TBX press kit, at
tbx/press/ (served as rudimakes.com/tbx/press/, unlisted and noindex).

rudimakes.com/tbx/ itself is the hand-written TBX world page (tbx/index.html)
and is never touched by this script. The press page shares its media with it
through tbx/assets/, so this script refreshes that folder too.

The page is authored in the TBX project (~/Documents/tbx/landing), so it can be
previewed on its own. Run this after changing the landing page:

    python3 tools/sync_tbx.py [path/to/landing]
"""
import re
import shutil
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Documents/tbx/landing"
ASSETS = SITE / "tbx" / "assets"
DST = SITE / "tbx" / "press"
URL = "https://rudimakes.com/tbx/press/"

STRIP_CSS = """
/* rudimakes.com press strip (added by tools/sync_tbx.py) */
.site-strip { background: #14120F; border-bottom: 1px solid var(--line); }
.site-strip .wrap { height: 44px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.site-strip a { font: 400 .75rem/1 "IBM Plex Mono", ui-monospace, monospace; letter-spacing: .04em; color: #EFE7DA; opacity: .7; text-decoration: none; }
.site-strip a:hover { color: #F0A02B; opacity: 1; }
"""

STRIP_HTML = """<div class="site-strip">
  <div class="wrap">
    <a href="../">&larr; tbx</a>
    <a href="../../">filament</a>
  </div>
</div>
"""


def to_press(page: str) -> str:
    """Rewrite the landing page for its home one folder below tbx/."""
    # drop any strip a previous sync added
    page = re.sub(r"\n/\* rudimakes\.com [^*]*\*/.*?(?=</style>)", "\n", page, count=1, flags=re.S)
    page = re.sub(r'<div class="site-strip">.*?</nav>\s*</div>\s*</div>\s*', "", page, count=1, flags=re.S)
    # media lives one level up, shared with the world page
    page = re.sub(r'(["(])assets/', r"\1../assets/", page)
    page = page.replace("</style>", STRIP_CSS + "</style>", 1)
    page = page.replace('<header class="bar">', STRIP_HTML + '<header class="bar">', 1)
    page = re.sub(r'\s*<link rel="canonical"[^>]*>', "", page)
    page = page.replace(
        "</title>",
        '</title>\n<link rel="canonical" href="' + URL + '">\n<meta name="robots" content="noindex">',
        1,
    )
    page = re.sub(r'(<meta property="og:url" content=")[^"]*', r"\g<1>" + URL, page)
    # og:image must be absolute for link previews
    page = re.sub(
        r'(<meta property="og:image" content=")(?:https://rudimakes\.com/tbx/|\.\./)?(?!https?:)([^"]*)',
        lambda m: m.group(1) + "https://rudimakes.com/tbx/" + m.group(2).replace("../", ""),
        page,
    )
    return page


def main():
    page = (SRC / "index.html").read_text(encoding="utf-8")
    if ASSETS.exists():
        shutil.rmtree(ASSETS)
    shutil.copytree(SRC / "assets", ASSETS)
    DST.mkdir(parents=True, exist_ok=True)
    (DST / "index.html").write_text(to_press(page), encoding="utf-8")
    print("synced", SRC, "->", DST)


if __name__ == "__main__":
    main()
