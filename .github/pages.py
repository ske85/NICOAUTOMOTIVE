"""Genera le pagine statiche del sito a partire dall'elenco auto in index.html:
- una pagina per ogni auto            /auto/<slug>/
- pagine per zona                     /auto-usate-<città>/
- pagine per esigenza                 /suv-usati/ ecc.
- assets/site.css, sitemap.xml e il blocco di link in home.
Il risultato dipende solo dai dati: se nulla cambia, i file restano identici.
"""
import html, json, os, re, shutil, subprocess, sys, unicodedata
from urllib.parse import quote

sys.dont_write_bytecode = True
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SITE = "https://www.nicoautomotive.com/"
TEL, TEL_TXT, WA_NUM = "+393392651438", "339 265 1438", "393392651438"
ADDR = "Via Gioia zona PIP lotto S7, 70029 Santeramo in Colle (BA)"
MAPS = "https://www.google.com/maps/dir/?api=1&destination=" + quote("NICO AUTOMOTIVE, Via Gioia zona PIP lotto S7, 70029 Santeramo in Colle BA")
FONTS = "https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600;700&family=Inter+Tight:wght@400;500;600&display=swap"
MESI = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()
BODY = {"city": "Berlina", "wagon": "Station wagon", "suv": "SUV", "mpv": "Monovolume"}

esc = lambda s: html.escape(str(s), quote=True)
fmt = lambda n: f"{int(n):,}".replace(",", ".")
eur = lambda n: "€ " + fmt(n)
year = lambda c: int(c["reg"].split("/")[-1])
is_auto = lambda c: c["gear"].startswith("Automatico")
name = lambda c: f"{c['make']} {c['model']} {c['ver']}"


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def wa(text):
    return f"https://wa.me/{WA_NUM}?text=" + quote(text)


# ---------- dati delle pagine per zona e per esigenza ----------
ZONES = [
    ("Bari", 45, "tre quarti d'ora",
     "Da Bari il salone si raggiunge in circa tre quarti d'ora, passando per Cassano delle Murge. Molti clienti baresi vengono da noi perché trovano auto controllate una per una e un rapporto diretto con chi le vende, senza passaggi intermedi."),
    ("Altamura", 18, "venti minuti",
     "Altamura è a una ventina di minuti dal salone. Se vuoi vedere un'auto dopo il lavoro, chiamaci prima: te la facciamo trovare pronta per la prova su strada."),
    ("Matera", 22, "venticinque minuti",
     "Da Matera si arriva a Santeramo in circa venticinque minuti. Seguiamo spesso clienti lucani e ci occupiamo noi del passaggio di proprietà, anche con residenza in Basilicata."),
    ("Gioia del Colle", 15, "un quarto d'ora",
     "Gioia del Colle è a un quarto d'ora: il salone si trova proprio sulla via che collega i due paesi, nella zona PIP di Santeramo."),
    ("Acquaviva delle Fonti", 20, "venti minuti",
     "Da Acquaviva delle Fonti il salone dista circa venti minuti di strada. Puoi passare anche solo per una valutazione gratuita della tua auto in permuta."),
    ("Cassano delle Murge", 14, "un quarto d'ora",
     "Cassano delle Murge è il paese più vicino: in un quarto d'ora sei da noi. Se hai poco tempo, scrivici su WhatsApp l'auto che ti interessa e ti mandiamo altre foto o un video."),
    ("Gravina in Puglia", 30, "mezz'ora",
     "Da Gravina in Puglia si arriva in circa mezz'ora, passando per Altamura. Prima di metterti in viaggio chiedici conferma della disponibilità: le auto più richieste restano poco in salone."),
    ("Laterza", 22, "venticinque minuti",
     "Laterza e il versante tarantino della Murgia sono a circa venticinque minuti. Per chi arriva dalla provincia di Taranto siamo spesso il salone di auto usate più comodo da raggiungere."),
]
NEEDS = [
    ("auto-usate-sotto-10000-euro", "Auto usate sotto i 10.000 euro", "Auto usate sotto i 10.000 € a Santeramo in Colle (Bari)",
     lambda c: c["price"] < 10000,
     "Le auto del salone con prezzo sotto i 10.000 euro: citycar e utilitarie adatte come prima auto, seconda auto di famiglia o per chi fa molta città. Anche su queste auto valgono la garanzia di 12 mesi e la possibilità di pagare a rate."),
    ("suv-usati", "SUV usati", "SUV usati a Santeramo in Colle (Bari)",
     lambda c: c["body"] == "suv",
     "I SUV e i crossover disponibili in salone, dai modelli compatti a quelli di fascia alta. Ogni SUV viene controllato prima della consegna e può essere provato su strada."),
    ("auto-usate-cambio-automatico", "Auto usate con cambio automatico", "Auto usate con cambio automatico a Santeramo in Colle (Bari)",
     is_auto,
     "Le auto con cambio automatico disponibili in questo momento. Il cambio automatico è comodo nel traffico e sui lunghi viaggi: vieni a provarlo su strada prima di decidere."),
    ("auto-ibride-usate", "Auto ibride usate", "Auto ibride ed elettrificate usate a Santeramo in Colle (Bari)",
     lambda c: c["fuel"].lower().startswith(("ibrid", "elettric")),
     "Le auto ibride e plug-in presenti in salone. Consumano meno in città e, a seconda del Comune, possono avere agevolazioni su bollo, parcheggi e zone a traffico limitato: verifica sempre le regole in vigore dove abiti."),
]
zone_slug = lambda z: "auto-usate-" + slugify(z[0])


# ---------- pezzi comuni ----------
def head(title, desc, path, image, ld):
    url = SITE + path
    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="Nico Automotive">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}{image}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="/img/logo.png">
<script type="application/ld+json">{json.dumps({"@context": "https://schema.org", "@graph": ld}, ensure_ascii=False)}</script>
<link rel="preload" href="/assets/fonts/montserrat-latin-600-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/site.css">
</head>
<body>
<header class="top">
  <div class="wrap">
    <a class="brand" href="/" aria-label="Nico Automotive, pagina iniziale">
      <img src="/img/logo-96.png" alt="Logo Nico Automotive" width="46" height="46">
      <span class="brand-text"><b>NICO</b><span>AUTOMOTIVE</span></span>
    </a>
    <nav>
      <a class="nl" href="/#auto">Auto in vendita</a>
      <a class="nl" href="/#salone">Il salone</a>
      <a class="nl" href="/#contatti">Contatti</a>
      <a class="btn solid" href="tel:{TEL}">{TEL_TXT}</a>
    </nav>
  </div>
</header>
<main class="page">
"""


def crumbs(items):
    parts = [f'<a href="/">Nico Automotive</a>'] + [f'<a href="/{p}">{esc(t)}</a>' if p else f"<span>{esc(t)}</span>" for t, p in items]
    return '<nav class="crumbs" aria-label="Percorso">' + " › ".join(parts) + "</nav>"


def crumbs_ld(items):
    els = [("Nico Automotive", SITE)] + [(t, SITE + p) for t, p in items]
    return {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": t, "item": u} for i, (t, u) in enumerate(els)]}


def links_block(cars):
    z = " · ".join(f'<a href="/{zone_slug(x)}/">Auto usate {esc(x[0])}</a>' for x in ZONES)
    n = " · ".join(f'<a href="/{s}/">{esc(t)}</a>' for s, t, *_ in NEEDS)
    a = " · ".join(f'<a href="/auto/{c["slug"]}/">{esc(c["make"] + " " + c["model"])} {year(c)}</a>' for c in cars)
    return f"""
      <span class="eyebrow">Dove siamo e cosa cerchi</span>
      <h2 class="lk-h">Auto usate in <strong class="goldtext">provincia di Bari</strong> e dintorni</h2>
      <p class="lk"><b>Per zona:</b> {z}</p>
      <p class="lk"><b>Per esigenza:</b> {n}</p>
      <p class="lk"><b>Schede auto:</b> {a}</p>
    """


def foot(cars):
    return f"""
  <section class="seo zones"><div class="wrap">{links_block(cars)}</div></section>
</main>
<footer><div class="wrap"><span style="display:flex;gap:10px;align-items:center"><img src="/img/logo-96.png" alt="" width="34" height="34" loading="lazy">Nico Automotive · {esc(ADDR)}</span><span>Tel. <a href="tel:{TEL}">{TEL_TXT}</a> · <a href="/">Tutte le auto</a></span><span class="legal">Nico Automotive di Lella Nicola · Ditta individuale · P.IVA 07044350721 · Via Gioia zona PIP lotto S7, 70029 Santeramo in Colle (BA) · PEC <a href="mailto:lellanicola@pec.it">lellanicola@pec.it</a> · © 2026 Tutti i diritti riservati · <a href="/note-legali/">Note legali</a> · <a href="/privacy/">Privacy</a></span></div></footer>
</body>
</html>
"""


def card(c):
    return f"""
    <a class="car" href="/auto/{c['slug']}/" aria-label="{esc(c['make'] + ' ' + c['model'] + ', ' + eur(c['price']))}">
      <div class="ph"><img src="/img/{c['pid']}_t.jpg" alt="{esc(name(c) + ' usata in vendita a Santeramo in Colle')}" width="640" height="480" loading="lazy" decoding="async" onerror="this.onerror=null;this.src=this.src.replace('_t.jpg','_0.jpg')">
        <span class="badge">{esc(c['fuel'])}{' · Automatico' if is_auto(c) else ''}</span>
        {'<span class="badge g">Unico proprietario</span>' if c.get('owners') == 'Unico proprietario' else ''}
      </div>
      <div class="body">
        <span class="mk">{esc(c['make'])}</span>
        <h3>{esc(c['model'])}</h3>
        <p class="ver">{esc(c['ver'])}</p>
        <div class="specs-row"><span>{year(c)}</span><span>{fmt(c['km'])} km</span><span>{str(c['cv']) + ' CV' if c.get('cv') else esc(c['euro'])}</span></div>
        <div class="price-row"><span class="price">{eur(c['price'])}</span><span class="more">Dettagli →</span></div>
        <p class="pnote">Prezzo IVA inclusa, passaggio di proprietà escluso</p>
      </div>
    </a>"""


PERKS = """
    <div class="perks">
      <div><h3>Garanzia 12 mesi</h3><p>Ogni auto è controllata prima della consegna ed è coperta da garanzia.</p></div>
      <div><h3>Finanziamento</h3><p>Rate su misura, anche senza anticipo, con risposta in tempi brevi.</p></div>
      <div><h3>Permuta</h3><p>Valutiamo gratis la tua auto e la scaliamo dal prezzo.</p></div>
      <div><h3>Prova su strada</h3><p>Vieni in salone e prova l'auto prima di decidere.</p></div>
    </div>"""


def car_ld(c, x):
    d = {"@type": "Car", "@id": f"{SITE}auto/{c['slug']}/#car", "name": name(c), "brand": {"@type": "Brand", "name": c["make"]}, "model": c["model"],
         "vehicleModelDate": str(year(c)), "dateVehicleFirstRegistered": f"{year(c)}-{c['reg'][:2]}",
         "mileageFromOdometer": {"@type": "QuantitativeValue", "value": c["km"], "unitCode": "KMT"},
         "fuelType": c["fuel"], "vehicleTransmission": c["gear"], "bodyType": BODY[c["body"]], "itemCondition": "https://schema.org/UsedCondition",
         "image": [f"{SITE}img/{c['pid']}_{k}.jpg" for k in range(min(c.get("n", 1), 6))], "url": f"{SITE}auto/{c['slug']}/",
         "offers": {"@type": "Offer", "price": c["price"], "priceCurrency": "EUR",
                    "priceSpecification": {"@type": "PriceSpecification", "price": c["price"], "priceCurrency": "EUR", "valueAddedTaxIncluded": True}, "availability": "https://schema.org/InStock",
                    "url": f"{SITE}auto/{c['slug']}/", "seller": {"@id": SITE + "#dealer"}}}
    if c.get("color"): d["color"] = c["color"]
    if c.get("cv"): d["vehicleEngine"] = {"@type": "EngineSpecification", "enginePower": {"@type": "QuantitativeValue", "value": c["cv"], "unitCode": "BHP"}}
    if x.get("seats"): d["seatingCapacity"] = x["seats"]
    return d


def fit(options, n=62):
    """Il primo titolo che entra nei risultati di Google senza essere tagliato."""
    return next((t for t in options if len(t) <= n), options[-1])


def prose(d):
    """Vero solo se la descrizione contiene frasi scritte dal venditore, non il solo elenco delle dotazioni."""
    return any(len(l) > 70 or ". " in l for l in d.split("\n")[1:])


def car_page(c, x, cars):
    path = f"auto/{c['slug']}/"
    n = c.get("n", 1)
    photos = [f"/img/{c['pid']}_{k}.jpg" for k in range(n)]
    title = fit([f"{name(c)} usata {year(c)} a {eur(c['price'])} | Nico Automotive", f"{name(c)} usata {year(c)} | Nico Automotive",
                 f"{name(c)} usata {year(c)}", f"{c['make']} {c['model']} usata {year(c)} a {eur(c['price'])} | Nico Automotive"])
    desc = (f"{name(c)} usata, {c['reg']}, {fmt(c['km'])} km, {c['fuel'].lower()}, cambio {c['gear'].lower()}. In vendita a {eur(c['price'])} IVA inclusa "
            f"da Nico Automotive a Santeramo in Colle (Bari), con garanzia 12 mesi, permuta e finanziamento.")
    specs = [("Immatricolazione", c["reg"]), ("Chilometri", fmt(c["km"]) + " km"), ("Alimentazione", c["fuel"]), ("Cambio", c["gear"]),
             ("Classe", c["euro"]), ("Carrozzeria", BODY[c["body"]])]
    if c.get("cv"): specs.append(("Potenza", f"{c['cv']} CV" + (f" ({x['kw']} kW)" if x.get("kw") else "")))
    if x.get("cc"): specs.append(("Cilindrata", fmt(x["cc"]) + " cc"))
    if x.get("trans"): specs.append(("Trazione", x["trans"]))
    if c.get("color"): specs.append(("Colore", c["color"]))
    if x.get("doors"): specs.append(("Porte", x["doors"]))
    if x.get("seats"): specs.append(("Posti", x["seats"]))
    if c.get("owners"): specs.append(("Proprietari", c["owners"]))
    specs = [(k, v) for k, v in specs if v]
    alt = f"{name(c)} usata, Nico Automotive Santeramo in Colle"
    msg = f"Ciao Nico, sono interessato alla {name(c)} a {eur(c['price'])}. È ancora disponibile?"
    opts = x.get("opts") or []
    others = sorted((o for o in cars if o is not c), key=lambda o: (o["body"] != c["body"], abs(o["price"] - c["price"])))[:3]
    many = n > 1
    out = head(title, desc, path, f"img/{c['pid']}_0.jpg", [car_ld(c, x), crumbs_ld([("Auto usate", "#auto"), (name(c), path)])])
    out += f"""  <div class="wrap">
    {crumbs([("Auto usate", "#auto"), (c["make"] + " " + c["model"], "")])}
    <div class="vdp">
      <div class="vdp-gal">
        <div class="gal-main"><img id="galImg" src="{photos[0]}" alt="{esc(alt)}" width="1200" height="900" fetchpriority="high">
          {'<button class="gal-nav p" type="button" id="gp" aria-label="Foto precedente">‹</button><button class="gal-nav n" type="button" id="gn" aria-label="Foto successiva">›</button><span class="gal-count" id="gc">1 / ' + str(n) + '</span>' if many else ''}
        </div>
      </div>
      <div class="vdp-info">
        <span class="eyebrow">{esc(c['make'])} · usata</span>
        <h1>{esc(c['make'] + ' ' + c['model'])} <span class="ver">{esc(c['ver'])} · usata {year(c)}</span></h1>
        <span class="price">{eur(c['price'])}</span>
        <p class="pnote vdp-pnote">Prezzo IVA inclusa, passaggio di proprietà escluso</p>
        <div class="actions">
          <a class="btn wa" href="{wa(msg)}" target="_blank" rel="noopener">Chiedi su WhatsApp</a>
          <a class="btn solid" href="tel:{TEL}">Chiama {TEL_TXT}</a>
        </div>
        <dl class="specs">{''.join(f'<div><dt>{k}</dt><dd>{esc(v)}</dd></div>' for k, v in specs)}</dl>
        <p class="note">In vendita presso Nico Automotive, {esc(ADDR)}. <a href="{MAPS}" target="_blank" rel="noopener">Indicazioni stradali</a></p>
      </div>
    </div>
    <section class="vdp-sec">
      <h2>{esc(name(c))}: <strong class="goldtext">scheda dell'auto</strong></h2>
      <p>{esc(c['make'])} {esc(c['model'])} {esc(c['ver'])} usata, immatricolata a {MESI[int(c['reg'][:2]) - 1]} {year(c)}, con {fmt(c['km'])} km. Alimentazione {esc(c['fuel'].lower())}, cambio {esc(c['gear'].lower())}{', ' + esc(c['euro']) if c.get('euro') else ''}{', colore ' + esc(c['color'].lower()) if c.get('color') else ''}. L'auto è visibile nel salone di Santeramo in Colle, in provincia di Bari, e si può provare su strada su appuntamento.</p>
      {'<h3>Dotazioni</h3><ul class="opts">' + ''.join(f'<li>{esc(o)}</li>' for o in opts) + '</ul>' if opts else ''}
      {'<details class="vdp-desc"><summary>Descrizione del venditore</summary><p>' + esc(x['desc']).replace(chr(10), '<br>') + '</p></details>' if prose(x.get('desc', '')) else ''}
    </section>
    {PERKS}
    {'<section class="vdp-sec"><h2>Tutte le <strong class="goldtext">foto</strong></h2><div class="photos">' + ''.join(f'<a href="{p}" data-k="{k}"><img src="{p}" alt="{esc(alt)} - foto {k + 1}" width="1200" height="900" loading="lazy" decoding="async"></a>' for k, p in enumerate(photos) if k) + '</div></section>' if many else ''}
    <section class="vdp-sec">
      <h2>Altre auto <strong class="goldtext">in salone</strong></h2>
      <div class="grid">{''.join(card(o) for o in others)}</div>
      <p class="more-link"><a class="btn" href="/#auto">Vedi tutte le {len(cars)} auto</a></p>
    </section>
  </div>
"""
    if many:
        out += f"""<script>
(function(){{var P={json.dumps(photos)},i=0,m=document.getElementById("galImg"),c=document.getElementById("gc");
function s(k){{i=(k+P.length)%P.length;m.src=P[i];c.textContent=(i+1)+" / "+P.length;}}
document.getElementById("gp").onclick=function(){{s(i-1)}};document.getElementById("gn").onclick=function(){{s(i+1)}};
document.querySelectorAll(".photos a").forEach(function(a){{a.addEventListener("click",function(e){{e.preventDefault();s(+a.dataset.k);m.scrollIntoView({{behavior:"smooth",block:"center"}});}});}});
document.addEventListener("keydown",function(e){{if(e.key==="ArrowRight")s(i+1);if(e.key==="ArrowLeft")s(i-1);}});}})();
</script>
"""
    return out + foot(cars)


def list_page(path, title, h1, lead, paras, cars, shown, faq, all_cars):
    ld = [crumbs_ld([(h1, path)]),
          {"@type": "ItemList", "name": h1, "numberOfItems": len(shown),
           "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"{SITE}auto/{c['slug']}/", "name": name(c)} for i, c in enumerate(shown)]},
          {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}]
    grid = ('<div class="grid">' + "".join(card(c) for c in shown) + "</div>") if shown else (
        '<div class="empty">In questo momento non abbiamo auto di questo tipo in salone. Dicci cosa cerchi: troviamo noi l\'auto giusta, in Italia e all\'estero.</div>')
    out = head(title, lead, path, "img/hero.jpg", ld)
    out += f"""  <div class="wrap">
    {crumbs([(h1, "")])}
    <section class="lp-head">
      <span class="eyebrow">Nico Automotive · Santeramo in Colle (BA)</span>
      <h1>{h1}</h1>
      {''.join(f'<p>{p}</p>' for p in paras)}
      <div class="actions">
        <a class="btn solid" href="tel:{TEL}">Chiama {TEL_TXT}</a>
        <a class="btn wa" href="{wa('Ciao Nico, vorrei informazioni sulle auto disponibili.')}" target="_blank" rel="noopener">Scrivici su WhatsApp</a>
        <a class="btn" href="{MAPS}" target="_blank" rel="noopener">Indicazioni stradali</a>
      </div>
    </section>
    <section class="vdp-sec">
      <h2>{len(shown)} auto <strong class="goldtext">disponibili ora</strong></h2>
      {grid}
      {'' if len(shown) == len(all_cars) else '<p class="more-link"><a class="btn" href="/#auto">Vedi tutte le ' + str(len(all_cars)) + ' auto</a></p>'}
    </section>
    {PERKS}
    <section class="vdp-sec">
      <h2>Domande <strong class="goldtext">frequenti</strong></h2>
      <div class="faq">{''.join(f'<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in faq)}</div>
    </section>
  </div>
"""
    return out + foot(all_cars)


LEGAL = {
"note-legali": ("Note legali", "Note legali | Nico Automotive", "Note legali del sito nicoautomotive.com: titolare, diritti su testi e foto, valore delle informazioni sulle auto in vendita.", [
 ("Titolare del sito", "Il sito www.nicoautomotive.com è gestito da <b>Nico Automotive di Lella Nicola</b>, ditta individuale, con sede in Via Gioia zona PIP lotto S7, 70029 Santeramo in Colle (BA). Partita IVA 07044350721. PEC: <a href=\"mailto:lellanicola@pec.it\">lellanicola@pec.it</a>. Telefono: <a href=\"tel:+393392651438\">339 265 1438</a>."),
 ("Diritti su testi, foto e marchio", "Testi, fotografie delle auto e del salone, logo, grafica e ogni altro contenuto di questo sito sono di proprietà di Nico Automotive o usati con autorizzazione, e sono protetti dalla legge sul diritto d'autore (L. 633/1941). <b>È vietato copiare, scaricare, ripubblicare o modificare</b> tutto o parte di questi contenuti, in particolare le fotografie, su altri siti, portali di annunci o social network, senza il consenso scritto del titolare. Sono consentiti la consultazione e la condivisione dei link alle pagine del sito."),
 ("Informazioni sulle auto e prezzi", "Le schede delle auto, i prezzi, le foto e le caratteristiche tecniche hanno valore indicativo. Possono contenere errori o non essere aggiornate, ad esempio se un'auto è appena stata venduta. I prezzi indicati sono <b>IVA inclusa, passaggio di proprietà escluso</b>. Le informazioni pubblicate <b>non costituiscono offerta al pubblico</b> ai sensi dell'art. 1336 del Codice Civile: disponibilità, prezzo finale, dotazioni e condizioni di vendita vanno sempre confermati in salone prima dell'acquisto e sono definiti solo nel contratto di vendita."),
 ("Garanzia", "Le auto usate vendute ai consumatori sono coperte dalla garanzia legale di conformità prevista dal Codice del Consumo (D.Lgs. 206/2005). Durata e condizioni sono indicate nel contratto di vendita."),
 ("Link ad altri siti", "Il sito contiene collegamenti a servizi esterni, come WhatsApp, Google Maps, Subito, Facebook e Trustpilot. Nico Automotive non è responsabile dei contenuti né del trattamento dei dati svolto da questi servizi, che seguono le loro condizioni e informative."),
]),
"privacy": ("Privacy", "Informativa privacy | Nico Automotive", "Informativa sul trattamento dei dati personali dei visitatori del sito nicoautomotive.com (art. 13 GDPR).", [
 ("Titolare del trattamento", "Nico Automotive di Lella Nicola, ditta individuale, Via Gioia zona PIP lotto S7, 70029 Santeramo in Colle (BA), P.IVA 07044350721. Per qualsiasi richiesta sui dati personali: PEC <a href=\"mailto:lellanicola@pec.it\">lellanicola@pec.it</a> oppure telefono <a href=\"tel:+393392651438\">339 265 1438</a>."),
 ("Quali dati raccogliamo", "Il sito non ha moduli di registrazione e non raccoglie dati personali direttamente. Il server che ospita il sito (GitHub Pages, servizio di GitHub Inc.) registra in modo automatico dati tecnici necessari al funzionamento, come l'indirizzo IP e il tipo di browser, per motivi di sicurezza. Il sito <b>non usa cookie di profilazione né strumenti di statistica</b>, e i caratteri tipografici sono ospitati sul sito stesso."),
 ("Contatti via WhatsApp, telefono ed email", "Se ci contatti tramite i pulsanti WhatsApp, il telefono o la PEC, riceviamo i dati che scegli di inviarci (nome, numero, messaggio, auto di interesse). Li usiamo solo per risponderti e per gestire la tua richiesta o l'eventuale trattativa di vendita (art. 6.1.b GDPR), e li conserviamo per il tempo necessario a questi scopi e agli obblighi di legge. Il messaggio WhatsApp passa attraverso il servizio di WhatsApp (Meta), che lo tratta secondo la propria informativa."),
 ("Mappa di Google", "La mappa nella pagina dei contatti viene caricata solo se clicchi su <i>Mostra la mappa</i>. Da quel momento Google può raccogliere dati di navigazione e installare propri cookie, secondo l'informativa di Google (policies.google.com/privacy). Se non clicchi, nessun dato viene inviato a Google."),
 ("Link esterni", "I collegamenti a Subito, Facebook, Trustpilot e alle recensioni Google portano a siti di terzi, che trattano i dati secondo le proprie informative."),
 ("I tuoi diritti", "Puoi chiedere in qualsiasi momento di accedere ai tuoi dati, correggerli, cancellarli, limitarne il trattamento, opporti o riceverli in formato portabile (artt. 15-22 GDPR), scrivendo alla PEC indicata sopra. Hai anche il diritto di presentare reclamo al Garante per la protezione dei dati personali (www.garanteprivacy.it)."),
 ("Aggiornamenti", "Questa informativa può essere aggiornata. Ultima modifica: 14 novembre 2026."),
]),
}


def legal_page(slug, cars):
    label, title, desc, secs = LEGAL[slug]
    out = head(title, desc, slug + "/", "img/hero.jpg", [crumbs_ld([(label, slug + "/")])])
    out += f"""  <div class="wrap">
    {crumbs([(label, "")])}
    <section class="lp-head"><span class="eyebrow">Nico Automotive</span><h1>{label}</h1></section>
    {''.join(f'<section class="vdp-sec legal-sec"><h2>{h}</h2><p>{t}</p></section>' for h, t in secs)}
  </div>
"""
    return out + foot(cars)


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    if old != text:
        open(path, "w", encoding="utf-8").write(text)


EXTRA_CSS = """
/* Pagine interne */
a.car{text-decoration:none}
main.page{padding-top:18px}
.crumbs{font-size:13px;color:var(--stone);padding:6px 0 18px}
.crumbs a{color:var(--stone)}.crumbs a:hover{color:var(--gold)}
.vdp{display:grid;grid-template-columns:1.25fr 1fr;gap:28px;align-items:start}
@media (max-width:900px){.vdp{grid-template-columns:1fr;gap:18px}}
.vdp-gal .gal-main{border-radius:14px;overflow:hidden;border:1px solid var(--line)}
.vdp-info h1{font-family:var(--display);font-weight:600;font-size:clamp(28px,4vw,40px);line-height:1.08;margin:6px 0 0}
.vdp-info h1 .ver{display:block;font:400 16px/1.4 var(--body);color:var(--stone);margin:8px 0 12px}
.vdp-info .price{display:block;font-size:34px;margin-bottom:4px}
.vdp-pnote{margin:0 0 16px!important}
.vdp-info .actions{margin-bottom:18px}
.vdp-sec{padding:44px 0 8px}
.vdp-sec h2,.lp-head h1{font-family:var(--display);font-weight:300;font-size:clamp(24px,3.4vw,34px);margin:0 0 14px;text-wrap:balance}
.vdp-sec h2 strong{font-weight:700}
.vdp-sec>h3{font-family:var(--display);font-size:16px;font-weight:600;color:var(--gold);margin:22px 0 10px}
.vdp-sec p,.lp-head p{color:#c9cbce;max-width:70ch;margin:0 0 14px}
.opts{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:8px}
.opts li{background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:5px 12px;font-size:14px}
.vdp-desc{margin-top:18px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:14px 0}
.vdp-desc summary{cursor:pointer;font-weight:600}
.vdp-desc p{margin:12px 0 0;max-width:none}
.photos{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}
@media (max-width:560px){.photos{grid-template-columns:1fr 1fr;gap:6px}}
.photos a{display:block;border-radius:8px;overflow:hidden;background:var(--panel);aspect-ratio:4/3}
.photos img{width:100%;height:100%;object-fit:cover}
.more-link{margin:22px 0 0}
.lp-head{padding:6px 0 4px}
.lp-head h1{font-size:clamp(30px,4.6vw,46px);font-weight:600;margin:10px 0 16px}
.lp-head .actions{margin-top:20px}
section.zones{padding:44px 0;margin-top:44px}
.legal-sec{padding:26px 0 0}
.legal-sec h2{font-size:22px!important;font-weight:600!important}
.legal-sec a{color:var(--gold)}
.lk-h{font-size:clamp(22px,3vw,30px)!important}
.lk{max-width:none!important;line-height:2;font-size:15px}
.lk b{color:var(--white)}
.lk a{color:#c9cbce;text-decoration:none;border-bottom:1px solid var(--line)}
.lk a:hover{color:var(--gold);border-color:var(--gold)}
"""


def main():
    index = open("index.html", encoding="utf-8").read()
    cars = json.loads(re.search(r"/\*CARS\*/(.*?)/\*END\*/", index, re.S).group(1))
    used, missing = {c["slug"] for c in cars if c.get("slug")}, False
    for c in cars:
        if not c.get("slug"):
            base = slugify(f"{name(c)} {year(c)}"); s, k = base, 2
            while s in used: s, k = f"{base}-{k}", k + 1
            c["slug"] = s; used.add(s); missing = True
    if missing:  # salva gli indirizzi delle pagine nell'elenco auto e rigenera la home
        json.dump(cars, open("/tmp/cars_slug.json", "w", encoding="utf-8"), ensure_ascii=False)
        subprocess.run(["node", "-e", """
const fs=require('fs'),B=require('./.github/build.js');
const r=B.build({index:fs.readFileSync('index.html','utf8'),llms:fs.readFileSync('llms.txt','utf8'),sitemap:fs.readFileSync('sitemap.xml','utf8')},
  JSON.parse(fs.readFileSync('/tmp/cars_slug.json','utf8')), new Date(Date.now()+3600e3));
fs.writeFileSync('index.html',r.index);fs.writeFileSync('llms.txt',r.llms);fs.writeFileSync('sitemap.xml',r.sitemap);"""], check=True)
        index = open("index.html", encoding="utf-8").read()
    cars.sort(key=lambda c: c["price"])
    extra = json.load(open("data/extra.json", encoding="utf-8")) if os.path.exists("data/extra.json") else {}

    css = re.search(r"<style>(.*?)</style>", index, re.S).group(1)
    write("assets/site.css", css.strip() + "\n" + EXTRA_CSS)

    for c in cars:
        write(f"auto/{c['slug']}/index.html", car_page(c, extra.get(c.get("mg", ""), {}), cars))
    if os.path.isdir("auto"):
        for d in os.listdir("auto"):
            if d not in used and os.path.isdir(os.path.join("auto", d)):
                shutil.rmtree(os.path.join("auto", d))

    urls = []
    for z in ZONES:
        town, km, mins, text = z; path = zone_slug(z) + "/"
        faq = [(f"Quanto dista Nico Automotive da {town}?", f"Il salone è a Santeramo in Colle, in {ADDR.split(',')[0]}, a circa {km} km da {town}: in auto ci vuole più o meno {mins}."),
               (f"Posso dare in permuta la mia auto se abito a {town}?", "Sì. Valutiamo gratuitamente la tua auto in salone e scaliamo il valore dal prezzo di quella che scegli. Del passaggio di proprietà ci occupiamo noi."),
               ("Le auto hanno la garanzia?", "Sì, le auto usate sono coperte da garanzia di 12 mesi e vengono controllate prima della consegna."),
               ("Non trovo l'auto che cerco: potete procurarla?", "Sì. Se il modello che vuoi non è in salone lo cerchiamo noi su richiesta, in Italia e all'estero, con le caratteristiche e il budget che ci indichi.")]
        write(path + "index.html", list_page(
            path, f"Auto usate {town}: {len(cars)} auto a {km} km | Nico Automotive",
            f"Auto usate a {town}",
            f"Cerchi un'auto usata a {town}? Nico Automotive è a Santeramo in Colle, a circa {km} km: {len(cars)} auto controllate e garantite a partire da {eur(min(c['price'] for c in cars)) if cars else '—'}, con permuta e finanziamento.",
            [f"Nico Automotive è una concessionaria di auto usate a Santeramo in Colle, a circa {km} km da {town}. In salone trovi {len(cars)} auto selezionate e controllate, con garanzia di 12 mesi, possibilità di permuta e finanziamento.", text],
            cars, cars, faq, cars))
        urls.append(path)
    for slug, label, h1, test, text in NEEDS:
        shown = [c for c in cars if test(c)]; path = slug + "/"
        faq = [("Dove posso vedere queste auto?", f"Nel salone Nico Automotive, {ADDR}. Siamo aperti dal lunedì al venerdì 9–13 e 16–20, il sabato 9–13."),
               ("Posso pagare a rate?", "Sì, proponiamo finanziamenti con rate su misura, anche senza anticipo."),
               ("Ritirate la mia auto in permuta?", "Sì. La valutazione è gratuita e il valore viene scalato dal prezzo dell'auto che scegli."),
               ("Non trovo il modello che cerco: potete procurarlo?", "Sì, cerchiamo auto su richiesta in Italia e all'estero in base alle tue esigenze e al tuo budget.")]
        write(path + "index.html", list_page(
            path, fit([f"{h1} | Nico Automotive", f"{label} a Santeramo (BA) | Nico Automotive", f"{label} | Nico Automotive"]), h1,
            f"{label} da Nico Automotive a Santeramo in Colle (Bari): {len(shown)} disponibili ora, con garanzia 12 mesi, permuta e finanziamento.",
            [text], cars, shown, faq, cars))
        urls.append(path)
    urls += [f"auto/{c['slug']}/" for c in cars]
    for slug in LEGAL:
        write(slug + "/index.html", legal_page(slug, cars))
    urls += [slug + "/" for slug in LEGAL]

    # home: blocco di link interni
    block = "<!--LINKS-->" + links_block(cars) + "<!--/LINKS-->"
    new_index, k = re.subn(r"<!--LINKS-->.*?<!--/LINKS-->", lambda m: block, index, flags=re.S)
    if k == 1: write("index.html", new_index)

    old_sm = open("sitemap.xml", encoding="utf-8").read()
    lastmod = re.search(r"<lastmod>([^<]*)</lastmod>", old_sm).group(1)
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
          f"  <url>\n    <loc>{SITE}</loc>\n    <lastmod>{lastmod}</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>1.0</priority>\n  </url>"]
    sm += [f"  <url><loc>{SITE}{u}</loc><priority>{'0.8' if u.startswith('auto/') else '0.7'}</priority></url>" for u in urls]
    write("sitemap.xml", "\n".join(sm) + "\n</urlset>\n")
    print(f"pagine: {len(cars)} auto, {len(ZONES)} zone, {len(NEEDS)} esigenze")


if __name__ == "__main__":
    main()
