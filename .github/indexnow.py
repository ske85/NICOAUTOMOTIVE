"""Avvisa Bing (e gli altri motori IndexNow) delle pagine cambiate tra due commit.
Uso: python .github/indexnow.py <commit_prima> <commit_dopo>
     python .github/indexnow.py --worktree   (modifiche non ancora salvate, usato dall'aggiornamento auto)"""
import json, os, subprocess, sys
from urllib.request import Request, urlopen

KEY = "800c402685195a2d35f83f53c233e1ee"
SITE = "https://www.nicoautomotive.com/"
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import re
if sys.argv[1] == "--all":
    files = [u.replace(SITE, "") + ("index.html" if u.endswith("/") else "") for u in re.findall(r"<loc>([^<]+)</loc>", open("sitemap.xml").read())]
elif sys.argv[1] == "--worktree":
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True, check=True).stdout
    files = [l[3:].strip('"') for l in out.splitlines()]
else:
    a, b = sys.argv[1], sys.argv[2]
    if set(a) == {"0"}:
        a = b + "~1"
    files = subprocess.run(["git", "diff", "--name-only", "--no-renames", a, b], capture_output=True, text=True, check=True).stdout.split()
urls = []
for f in files:
    if f.endswith("index.html") and not f.startswith((".github/", "admin/")):
        urls.append(SITE + f[: -len("index.html")])
    elif f in ("sitemap.xml", "llms.txt"):
        urls.append(SITE + f)
urls = sorted(set(urls))[:10000]
if not urls:
    sys.exit(print("IndexNow: nessuna pagina cambiata"))
body = json.dumps({"host": "www.nicoautomotive.com", "key": KEY, "keyLocation": f"{SITE}{KEY}.txt", "urlList": urls}).encode()
try:
    with urlopen(Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"}), timeout=30) as r:
        print(f"IndexNow: inviate {len(urls)} pagine, risposta {r.status}")
except Exception as e:  # noqa: BLE001  (un errore qui non deve bloccare la pubblicazione)
    print(f"IndexNow non riuscito: {e}")
