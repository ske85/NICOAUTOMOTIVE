"""Aggiorna le auto del sito dal feed XML ufficiale di Multigestionale Motori (Subito).

Il codice cliente si legge dalla variabile d'ambiente MG_CC (segreto GitHub), mai dal codice.
Uso: python .github/mg_sync.py [--dry]
"""
import io, json, os, re, subprocess, sys, time
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://motori.multigestionale.com/api/xml/"
DRY = "--dry" in sys.argv
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def get(url, binary=False, tries=3):
    err = None
    for t in range(tries):
        try:
            with urlopen(Request(url, headers={"User-Agent": "NicoAutomotive-site-sync/1.0"}), timeout=60) as r:
                b = r.read()
                return b if binary else b.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(3 * (t + 1))
    raise RuntimeError(f"download non riuscito: {type(err).__name__}")


def read_feed():
    cc = os.environ.get("MG_CC", "").strip()
    if not cc:
        print("In attesa del segreto MG_CC: nessuna modifica"); sys.exit(0)
    xml = get(API + "?" + urlencode({"cc": cc, "show": "all", "engine": "car"}))
    if not xml.strip():
        sys.exit("STOP: feed vuoto (codice errato o servizio non disponibile), nessuna modifica")
    root = ET.fromstring(xml)
    ads = []
    for e in root.findall("element"):
        t = lambda k: (e.findtext(k) or "").strip()
        ads.append(dict(
            id=t("ad_number"), make=t("make"), model=t("model"), version=t("version"), cls=t("vehicle_class"),
            cat=t("vehicle_category"), reg=t("first_registration_date"), km=t("mileage"), cv=t("power_cv"),
            fuel=t("fuel_type"), color=t("color"), price=t("price"), euro=t("emissions_class"), gear=t("gearbox"),
            owners=t("owners_count"), imgs=[(i.text or "").strip() for i in e.findall("images/element") if (i.text or "").strip()],
        ))
    return ads


num = lambda s: int(re.sub(r"\D", "", s or "") or 0)


def reg_of(s):
    m = re.match(r"(\d{1,2})-(\d{4})", s or "")
    return f"{int(m.group(1)):02d}/{m.group(2)}" if m else ""


def fuel_of(s):
    s = s.lower()
    if "plug" in s: return "Ibrida plug-in"
    if "elettrica/" in s or "ibrid" in s: return "Ibrida"
    if s.startswith("elettric"): return "Elettrica"
    return {"benzina": "Benzina", "diesel": "Diesel", "gpl": "GPL", "metano": "Metano"}.get(s, s.capitalize())


def body_of(cat):
    c = cat.lower()
    if "station" in c: return "wagon"
    if "monovolume" in c or "multispazio" in c: return "mpv"
    if "suv" in c or "fuoristrada" in c or "pick" in c: return "suv"
    return "city"


def new_car(a):
    ver = a["version"]
    if ver.lower().startswith(a["model"].lower()):
        ver = ver[len(a["model"]):].strip() or ver
    car = dict(make=a["make"], model=a["model"], ver=ver, price=num(a["price"]), reg=reg_of(a["reg"]), km=num(a["km"]),
               fuel=fuel_of(a["fuel"]), euro=a["euro"] if a["euro"].lower().startswith("euro") else "",
               gear="Manuale" if a["gear"].lower().startswith("manual") else "Automatico")
    if num(a["cv"]): car["cv"] = num(a["cv"])
    if a["color"] and a["color"].lower() not in ("altro", "non specificato"): car["color"] = a["color"].capitalize()
    o = num(a["owners"])
    if o: car["owners"] = "Unico proprietario" if o == 1 else f"{o} proprietari"
    car["body"] = body_of(a["cat"])
    car["pid"], car["mg"] = "mg" + a["id"], a["id"]
    if not (car["price"] and car["reg"] and car["make"] and car["model"]):
        raise RuntimeError(f"dati incompleti per l'annuncio {a['id']}")
    return car


def save_photos(car, imgs):
    from PIL import Image
    logo = Image.open("img/logo-wm.png").convert("RGBA"); logo.load()
    n = 0
    for u in imgs[:30]:
        try:
            im = Image.open(io.BytesIO(get(u, True))); im.load()
        except Exception:  # noqa: BLE001
            continue
        im = im.convert("RGB"); im.thumbnail((1200, 900), Image.LANCZOS)
        s = int(min(im.size) * 0.55); w = logo.copy(); w.thumbnail((s, s), Image.LANCZOS)
        w.putalpha(w.getchannel("A").point(lambda v: int(v * 0.22)))
        im.paste(w, ((im.width - w.width) // 2, (im.height - w.height) // 2), w)
        im.save(f"img/{car['pid']}_{n}.jpg", "JPEG", quality=78, optimize=True, progressive=True)
        n += 1
    if not n:
        raise RuntimeError(f"nessuna foto scaricata per l'annuncio {car['mg']}")
    car["n"] = n


def main():
    index = open("index.html", encoding="utf-8").read()
    cars = json.loads(re.search(r"/\*CARS\*/(.*?)/\*END\*/", index, re.S).group(1))
    ads = [a for a in read_feed() if a["cls"].lower() != "noleggio"]
    if not ads:
        sys.exit("STOP: il feed non contiene auto, nessuna modifica (protezione contro svuotamento del sito)")

    by_mg = {c["mg"]: c for c in cars if c.get("mg")}
    free = [c for c in cars if not c.get("mg")]
    out, log = [], []
    for a in ads:
        c = by_mg.get(a["id"])
        if c is None:  # auto già sul sito ma non ancora collegata: stessa marca, immatricolazione e km
            c = next((x for x in free if x["make"].lower() == a["make"].lower() and x["reg"] == reg_of(a["reg"]) and x["km"] == num(a["km"])), None)
            if c is not None:
                free.remove(c); c["mg"] = a["id"]; log.append(f"collegata: {c['make']} {c['model']}")
        if c is None:
            c = new_car(a)
            if not DRY: save_photos(c, a["imgs"])
            log.append(f"NUOVA: {c['make']} {c['model']} {c['ver']} € {c['price']}")
        else:
            for k, v in (("price", num(a["price"])), ("km", num(a["km"]))):
                if v and c.get(k) != v:
                    log.append(f"{k} {c['make']} {c['model']}: {c.get(k)} -> {v}"); c[k] = v
        out.append(c)
    keep = {c["pid"] for c in out}
    gone = [c for c in cars if c["pid"] not in keep]
    for c in gone:
        log.append(f"VENDUTA/rimossa: {c['make']} {c['model']} {c['ver']}")
    print("\n".join(log) or "nessuna modifica")
    if DRY or not log:
        return
    json.dump(out, open("/tmp/cars.json", "w", encoding="utf-8"), ensure_ascii=False)
    subprocess.run(["node", "-e", """
const fs=require('fs'),B=require('./admin/build.js');
const r=B.build({index:fs.readFileSync('index.html','utf8'),llms:fs.readFileSync('llms.txt','utf8'),sitemap:fs.readFileSync('sitemap.xml','utf8')},
  JSON.parse(fs.readFileSync('/tmp/cars.json','utf8')), new Date(Date.now()+3600e3));
fs.writeFileSync('index.html',r.index);fs.writeFileSync('llms.txt',r.llms);fs.writeFileSync('sitemap.xml',r.sitemap);"""], check=True)
    for c in gone:
        for f in os.listdir("img"):
            if re.fullmatch(re.escape(c["pid"]) + r"_\d+\.jpg", f):
                os.remove(os.path.join("img", f))


if __name__ == "__main__":
    main()
