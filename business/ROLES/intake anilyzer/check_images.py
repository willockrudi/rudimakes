import os, re

def check(html_file):
    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()

    paths = re.findall(r'<img[^>]+src="([^"]+)"', html)
    missing = []
    for p in paths:
        # only check local paths
        if p.startswith("http"):
            continue
        disk_path = os.path.join(os.path.dirname(html_file), p.replace("/", os.sep))
        if not os.path.exists(disk_path):
            missing.append(p)

    print(f"\n{html_file}:")
    if not missing:
        print("  ✅ No missing local images.")
    else:
        print("  ❌ Missing images:")
        for m in missing:
            print("   ", m)

check("index.html")
if os.path.exists("repairs.html"):
    check("repairs.html")
