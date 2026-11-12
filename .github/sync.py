"""Sincronizza le auto del sito con il negozio Subito di Nico Automotive.
Uso: python .github/sync.py [--build] [--dry]   (--build: rigenera solo i file, --dry: non scrive)"""
import datetime, html, io, json, os, re, sys, time
from urllib.request import Request, urlopen

SHOP = "https://impresapiu.subito.it/shops/52560-nico-automotive"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
      "Accept-Language": "it-IT,it;q=0.9", "Cache-Control": "no-cache"}
SITE = "https://www.nicoautomotive.com/"
MESI = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()
BODY = {"city": "Berlina", "wagon": "Station wagon", "suv": "SUV", "mpv": "Monovolume"}
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def get(url, binary=False, tries=3):
    for t in range(tries):
        try:
            with urlopen(Request(url, headers=UA), timeout=30) as r:
                b = r.read()
                return b if binary else b.decode("utf-8", "replace")
        except Exception as e:
            err = e
            time.sleep(3 * (t + 1))
    raise RuntimeError(f"{url}: {err}")


def ad_id(url):
    return re.search(r"(\d+)\.htm$", url).group(1)


def read_shop():
    """Elenco URL annunci + contatore, con pagine successive se servono."""
    urls, count = [], None
    for page in range(1, 6):
        h = get(f"{SHOP}?page={page}&_={int(time.time())}")
        if count is None:
            m = re.search(r"(\d+)\s*annunci", h)
            count = int(m.group(1)) if m else None
        new = [u for u in dict.fromkeys(re.findall(r"https://www\.subito\.it/auto/[\w\-]+\.htm", h)) if u not in urls]
        if not new:
            break
        urls += new
        if count and len(urls) >= count:
            break
    if not count or len(urls) != count:
        sys.exit(f"STOP: contatore {count} ma trovati {len(urls)} annunci, nessuna modifica")
    return urls


def jsonld(h):
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', h, re.S):
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        for x in (d if isinstance(d, list) else d.get("@graph", [d])):
            if isinstance(x, dict) and x.get("@type") in ("Product", "Car", "Vehicle"):
                return x
    return {}


def features(h):
    """Coppie etichetta -> valore dal JSON Next.js (features dell'annuncio)."""
    out = {}
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    if m:
        def walk(o):
            if isinstance(o, dict):
                if "label" in o and isinstance(o.get("values"), list) and o["values"]:
                    v = o["values"][0]
                    out.setdefault(str(o["label"]).lower(), str(v.get("value", v.get("key", ""))) if isinstance(v, dict) else str(v))
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(json.loads(m.group(1)))
    return out


def read_ad(url):
    h = get(url)
    p, f = jsonld(h), features(h)
    offer = p.get("offers") or {}
    offer = offer[0] if isinstance(offer, list) else offer
    price = offer.get("price")
    if not price or re.search(r"annuncio (non (è più )?disponibile|scaduto|rimosso)", h, re.I):
        return None
    imgs = p.get("image") or []
    imgs = [imgs] if isinstance(imgs, str) else imgs
    return dict(price=int(float(price)), name=html.unescape(p.get("name", "")), f=f,
                imgs=[re.sub(r"\?.*", "", i) + "?rule=fullscreen-1x-auto" for i in imgs])


def num(s):
    d = re.sub(r"\D", "", s or "")
    return int(d) if d else None


def new_car(url, a):
    f = a["f"]
    g = lambda *ks: next((f[k] for k in ks if f.get(k)), "")
    make = g("marca").title() or a["name"].split()[0]
    model = g("modello") or a["name"].split()[1]
    ver = g("versione") or re.sub(rf"^\s*{re.escape(make)}\s+{re.escape(model)}\s*", "", a["name"], flags=re.I) or a["name"]
    reg = g("immatricolazione")
    m = re.search(r"(\d{1,2})/(\d{4})", reg)
    reg = f"{int(m.group(1)):02d}/{m.group(2)}" if m else (re.search(r"\d{4}", reg) or [""])[0]
    car = dict(make=make, model=model, ver=ver.strip(), price=a["price"], reg=reg, km=num(g("km", "chilometri")) or 0,
               fuel=g("carburante").capitalize(), euro=g("classe emissioni", "classe emissione").replace("euro", "Euro"),
               gear=g("cambio").capitalize())
    cv = num(re.sub(r"[,.]\d+$", "", g("potenza (cv)", "potenza cv"))) or num((re.search(r"(\d+)\s*CV", g("potenza")) or [None, ""])[1])
    if cv: car["cv"] = cv
    if g("colore"): car["color"] = g("colore").capitalize()
    if num(g("numero proprietari", "proprietari")): car["owners"] = "Unico proprietario" if num(g("numero proprietari", "proprietari")) == 1 else f"{num(g('numero proprietari', 'proprietari'))} proprietari"
    c = g("carrozzeria").lower()
    car["body"] = "wagon" if "station" in c else "mpv" if "monovolume" in c else "suv" if ("suv" in c or "fuoristrada" in c) else "city"
    car["sub"], car["ad"] = url, ad_id(url)
    if not (car["reg"] and car["km"] and car["fuel"] and car["gear"]):
        raise RuntimeError(f"dati incompleti per {url}: {car} / {f}")
    return car


def save_photos(car, imgs):
    from PIL import Image
    logo = Image.open("img/logo-wm.png").convert("RGBA"); logo.load()
    n = 0
    for u in imgs:
        for t in range(3):
            try:
                im = Image.open(io.BytesIO(get(u, True))); im.load(); break
            except Exception:
                im = None; time.sleep(2)
        if im is None:
            continue
        im = im.convert("RGB"); im.thumbnail((1200, 900), Image.LANCZOS)
        s = int(min(im.size) * 0.55); w = logo.copy(); w.thumbnail((s, s), Image.LANCZOS)
        w.putalpha(w.getchannel("A").point(lambda a: int(a * 0.22)))
        im.paste(w, ((im.width - w.width) // 2, (im.height - w.height) // 2), w)
        im.save(f"img/{car['ad']}_{n}.jpg", "JPEG", quality=78, optimize=True, progressive=True)
        n += 1
    if not n:
        raise RuntimeError(f"nessuna foto per {car['sub']}")
    car["n"] = n


# ---------- scrittura file ----------
fmt = lambda n: f"{n:,}".replace(",", ".")
eur = lambda n: "€ " + fmt(n)
esc = lambda s: html.escape(str(s), quote=True).replace("&#x27;", "'")
is_auto = lambda c: c["gear"].startswith("Automatico")
year = lambda c: int(c["reg"].split("/")[-1])


def card(i, c):
    return f'''
    <button class="car" type="button" data-id="{i}" aria-label="{esc(c['make']+' '+c['model']+', '+eur(c['price']))}">
      <div class="ph"><img src="img/{c['ad']}_0.jpg" alt="{esc(c['make']+' '+c['model']+' '+c['ver']+' usata in vendita a Santeramo in Colle')}" loading="lazy">
        <span class="badge">{esc(c['fuel'])}{' · Automatico' if is_auto(c) else ''}</span>
        {'<span class="badge g">Unico proprietario</span>' if c.get('owners') == 'Unico proprietario' else ''}
      </div>
      <div class="body">
        <span class="mk">{esc(c['make'])}</span>
        <h3>{esc(c['model'])}</h3>
        <p class="ver">{esc(c['ver'])}</p>
        <div class="specs-row"><span>{year(c)}</span><span>{fmt(c['km'])} km</span><span>{str(c['cv'])+' CV' if c.get('cv') else esc(c['euro'])}</span></div>
        <div class="price-row"><span class="price">{eur(c['price'])}</span><span class="more">Dettagli →</span></div>
      </div>
    </button>'''


def sub_once(pat, rep, s):
    s2, n = re.subn(pat, lambda m: rep, s, count=1, flags=re.S)
    if n != 1:
        raise RuntimeError(f"segnaposto non trovato: {pat}")
    return s2


def build(cars, dry=False):
    today = datetime.date.today()
    s = open("index.html", encoding="utf-8").read()
    data = "[\n" + ",\n".join(" " + json.dumps(c, ensure_ascii=False) for c in cars) + "\n]"
    s = sub_once(r"/\*CARS\*/.*?/\*END\*/", f"/*CARS*/{data}/*END*/", s)
    s = sub_once(r"<!--GRID-->.*?<!--/GRID-->", "<!--GRID-->" + "".join(card(i, c) for i, c in enumerate(cars)) + "<!--/GRID-->", s)
    s = re.sub(r'(<b id="f-count">)[^<]*', lambda m: m.group(1) + str(len(cars)), s)
    s = re.sub(r'(<b id="f-from">)[^<]*', lambda m: m.group(1) + eur(min(c["price"] for c in cars)), s)
    s = re.sub(r'(<b id="f-brands">)[^<]*', lambda m: m.group(1) + str(len({c["make"] for c in cars})), s)
    s = re.sub(r'(<p id="count"[^>]*>)[^<]*', lambda m: m.group(1) + f"{len(cars)} auto trovat" + ("a" if len(cars) == 1 else "e"), s)
    m = re.search(r'(<script type="application/ld\+json">)(.*?)(</script>)', s, re.S)
    ld = json.loads(m.group(2))
    for g in ld["@graph"]:
        if g.get("@type") == "ItemList":
            g["itemListElement"] = [{"@type": "ListItem", "position": i + 1, "item": {
                "@type": "Car", "name": f"{c['make']} {c['model']} {c['ver']}", "brand": {"@type": "Brand", "name": c["make"]},
                "model": c["model"], "vehicleModelDate": str(year(c)),
                "mileageFromOdometer": {"@type": "QuantitativeValue", "value": c["km"], "unitCode": "KMT"},
                "fuelType": c["fuel"], "vehicleTransmission": c["gear"], "itemCondition": "https://schema.org/UsedCondition",
                "image": f"{SITE}img/{c['ad']}_0.jpg", "url": c["sub"],
                "offers": {"@type": "Offer", "price": c["price"], "priceCurrency": "EUR", "availability": "https://schema.org/InStock",
                           "seller": {"@id": f"{SITE}#dealer"}}, **({"color": c["color"]} if c.get("color") else {})}} for i, c in enumerate(cars)]
    s = s[:m.start(2)] + json.dumps(ld, ensure_ascii=False) + s[m.end(2):]
    t = open("llms.txt", encoding="utf-8").read()
    rows = "\n".join(f"- [{c['make']} {c['model']} {c['ver']}]({c['sub']}): {eur(c['price'])}, {c['reg']}, {fmt(c['km'])} km, "
                     f"{c['fuel'].lower()}, {c['gear'].lower()}" for c in cars)
    t = re.sub(r"(## Auto in vendita\n\n[^\n]*\n\n)(?:- [^\n]*\n)+", lambda m: m.group(1) + rows + "\n", t, count=1)
    t = re.sub(r"Informazioni aggiornate al [^.]*\.", f"Informazioni aggiornate al {today.day} {MESI[today.month-1]} {today.year}.", t)
    x = re.sub(r"<lastmod>[^<]*</lastmod>", f"<lastmod>{today.isoformat()}</lastmod>", open("sitemap.xml").read())
    if not dry:
        open("index.html", "w", encoding="utf-8").write(s)
        open("llms.txt", "w", encoding="utf-8").write(t)
        open("sitemap.xml", "w").write(x)


def load():
    s = open("index.html", encoding="utf-8").read()
    return json.loads(re.search(r"/\*CARS\*/(.*?)/\*END\*/", s, re.S).group(1))


def main():
    cars = load()
    if "--build" in sys.argv:
        return build(cars)
    if "--test" in sys.argv:  # verifica lettura di un annuncio, senza modifiche
        u = sys.argv[sys.argv.index("--test") + 1]; a = read_ad(u)
        return print(json.dumps(new_car(u, a), ensure_ascii=False), len(a["imgs"]), "foto", a["imgs"][:2])
    dry = "--dry" in sys.argv
    urls = read_shop()
    print(f"Subito: {len(urls)} annunci")
    have = {c["ad"]: c for c in cars}
    live = {ad_id(u): u for u in urls}
    log = []
    for c in [c for c in cars if c["ad"] not in live]:
        log.append(f"rimossa {c['make']} {c['model']} {c['ver']}")
        cars.remove(c)
        if not dry:
            for k in range(c.get("n", 0)):
                if os.path.exists(f"img/{c['ad']}_{k}.jpg"): os.remove(f"img/{c['ad']}_{k}.jpg")
    for ad, u in live.items():
        a = read_ad(u)
        time.sleep(1)
        if a is None:
            sys.exit(f"STOP: {u} è nel negozio ma l'annuncio non risulta attivo, nessuna modifica")
        if ad in have:
            if have[ad]["price"] != a["price"]:
                log.append(f"prezzo {have[ad]['make']} {have[ad]['model']}: {eur(have[ad]['price'])} → {eur(a['price'])}")
                have[ad]["price"] = a["price"]
        else:
            c = new_car(u, a)
            print("nuova:", json.dumps(c, ensure_ascii=False), len(a["imgs"]), "foto")
            if not dry:
                save_photos(c, a["imgs"])
            cars.append(c)
            log.append(f"aggiunta {c['make']} {c['model']} {c['ver']} ({eur(c['price'])})")
    if not log:
        print(f"Sito già allineato con Subito ({len(cars)} auto)")
        return
    cars.sort(key=lambda c: c["price"])
    build(cars, dry)
    msg = f"Sincronizza con Subito ({len(cars)} auto): " + "; ".join(log)
    print(msg)
    if not dry and os.environ.get("GITHUB_OUTPUT"):
        open(os.environ["GITHUB_OUTPUT"], "a").write(f"msg={msg}\n")


if __name__ == "__main__":
    main()
