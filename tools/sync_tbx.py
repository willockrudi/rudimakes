#!/usr/bin/env python3
"""
Copy the TBX investor page into this site at tbx/ (served as rudimakes.com/tbx/).

The page itself is authored in the TBX project (~/Documents/tbx/landing), so it
can be previewed on its own. This script copies it here and adds the
rudimakes.com navigation strip above the page's own channel bar, plus the
canonical/og URLs for its new home. Run it after changing the landing page:

    python3 tools/sync_tbx.py [path/to/landing]
"""
import re
import shutil
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Documents/tbx/landing"
DST = SITE / "tbx"
URL = "https://rudimakes.com/tbx/"

STRIP_CSS = """
/* rudimakes.com site strip (added by tools/sync_tbx.py) */
.site-strip { background: #0F0E0C; border-bottom: 1px solid var(--line); }
.site-strip .wrap { height: 52px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.site-strip .fil { display: flex; align-items: center; line-height: 0; flex: none; }
.site-strip .fil img { height: 26px; width: auto; }
.site-strip nav { display: flex; gap: 2px; overflow-x: auto; scrollbar-width: none; }
.site-strip nav::-webkit-scrollbar { display: none; }
.site-strip nav a { font: 500 .875rem/1 var(--text); color: var(--mute); text-decoration: none; padding: 8px 12px; border-radius: 999px; white-space: nowrap; }
.site-strip nav a:hover { color: var(--paper); background: var(--surface); }
.site-strip nav a[aria-current="page"] { color: var(--paper); box-shadow: inset 0 0 0 1px var(--line); }
@media (max-width: 560px) { .site-strip .fil img { height: 22px; } .site-strip nav a { padding: 8px 9px; font-size: .8125rem; } .site-strip nav a.opt { display: none; } }
"""

STRIP_HTML = """<div class="site-strip">
  <div class="wrap">
    <a class="fil" href="../" aria-label="Filament, rudimakes.com home"><img src="../images/filament-logo-dark.svg" alt="filament" width="104" height="32"></a>
    <nav aria-label="rudimakes.com">
      <a href="./" aria-current="page">TBX</a>
      <a href="../services.html">Services</a>
      <a href="../repairs.html">Repair Log</a>
      <a class="opt" href="../#about">About</a>
      <a href="../#contact">Contact</a>
    </nav>
  </div>
</div>
"""


def main():
    page = (SRC / "index.html").read_text(encoding="utf-8")
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC / "assets", DST / "assets")

    page = page.replace("</style>", STRIP_CSS + "</style>", 1)
    page = page.replace('<header class="bar">', STRIP_HTML + '<header class="bar">', 1)
    if 'rel="canonical"' not in page:
        page = page.replace("</title>", '</title>\n<link rel="canonical" href="' + URL + '">', 1)
    page = re.sub(r'(<meta property="og:url" content=")[^"]*', r"\g<1>" + URL, page)
    # og:image must be absolute for link previews
    page = re.sub(r'(<meta property="og:image" content=")(?!https?:)([^"]*)', lambda m: m.group(1) + URL + m.group(2), page)
    (DST / "index.html").write_text(page, encoding="utf-8")
    print("synced", SRC, "->", DST)


if __name__ == "__main__":
    main()
