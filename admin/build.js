// Rigenera index.html, llms.txt e sitemap.xml a partire dall'elenco auto.
// Usato dalla pagina /admin (browser) e da Node per le prove.
(function (root) {
  const SITE = "https://www.nicoautomotive.com/";
  const MESI = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split(" ");
  const fmt = n => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const eur = n => "€ " + fmt(n);
  const esc = s => String(s).replace(/[&<>"]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));
  const isAuto = c => c.gear.startsWith("Automatico");
  const year = c => +c.reg.split("/").pop();

  function parseCars(index) {
    const m = index.match(/\/\*CARS\*\/([\s\S]*?)\/\*END\*\//);
    if (!m) throw new Error("Elenco auto non trovato in index.html");
    return JSON.parse(m[1]);
  }

  const card = (c, i) => `
    <button class="car" type="button" data-id="${i}" aria-label="${esc(c.make + " " + c.model + ", " + eur(c.price))}">
      <div class="ph"><img src="img/${c.pid}_0.jpg" alt="${esc(c.make + " " + c.model + " " + c.ver + " usata in vendita a Santeramo in Colle")}" loading="lazy">
        <span class="badge">${esc(c.fuel)}${isAuto(c) ? " · Automatico" : ""}</span>
        ${c.owners === "Unico proprietario" ? '<span class="badge g">Unico proprietario</span>' : ""}
      </div>
      <div class="body">
        <span class="mk">${esc(c.make)}</span>
        <h3>${esc(c.model)}</h3>
        <p class="ver">${esc(c.ver)}</p>
        <div class="specs-row"><span>${year(c)}</span><span>${fmt(c.km)} km</span><span>${c.cv ? c.cv + " CV" : esc(c.euro)}</span></div>
        <div class="price-row"><span class="price">${eur(c.price)}</span><span class="more">Dettagli →</span></div>
      </div>
    </button>`;

  function replaceOnce(s, re, fn, what) {
    let n = 0;
    const out = s.replace(re, (...a) => { n++; return fn(...a); });
    if (n !== 1) throw new Error("Segnaposto non trovato: " + what);
    return out;
  }

  function build(files, cars, today = new Date()) {
    cars = cars.slice().sort((a, b) => a.price - b.price);
    let s = files.index;
    const data = "[\n" + cars.map(c => " " + JSON.stringify(c)).join(",\n") + "\n]";
    s = replaceOnce(s, /\/\*CARS\*\/[\s\S]*?\/\*END\*\//, () => "/*CARS*/" + data + "/*END*/", "CARS");
    s = replaceOnce(s, /<!--GRID-->[\s\S]*?<!--\/GRID-->/, () => "<!--GRID-->" + cars.map(card).join("") + "<!--/GRID-->", "GRID");
    const set = (re, v, w) => { s = replaceOnce(s, re, (m, a) => a + v, w); };
    set(/(<b id="f-count">)[^<]*/, cars.length, "f-count");
    set(/(<b id="f-from">)[^<]*/, cars.length ? eur(Math.min(...cars.map(c => c.price))) : "—", "f-from");
    set(/(<b id="f-brands">)[^<]*/, new Set(cars.map(c => c.make)).size, "f-brands");
    set(/(<p id="count"[^>]*>)[^<]*/, cars.length === 1 ? "1 auto trovata" : cars.length + " auto trovate", "count");
    s = replaceOnce(s, /(<script type="application\/ld\+json">)([\s\S]*?)(<\/script>)/, (m, a, json, z) => {
      const ld = JSON.parse(json);
      for (const g of ld["@graph"]) if (g["@type"] === "ItemList") g.itemListElement = cars.map((c, i) => ({
        "@type": "ListItem", position: i + 1, item: Object.assign({
          "@type": "Car", name: `${c.make} ${c.model} ${c.ver}`, brand: { "@type": "Brand", name: c.make }, model: c.model,
          vehicleModelDate: String(year(c)), mileageFromOdometer: { "@type": "QuantitativeValue", value: c.km, unitCode: "KMT" },
          fuelType: c.fuel, vehicleTransmission: c.gear, itemCondition: "https://schema.org/UsedCondition",
          image: `${SITE}img/${c.pid}_0.jpg`, url: c.sub || SITE,
          offers: { "@type": "Offer", price: c.price, priceCurrency: "EUR", availability: "https://schema.org/InStock", seller: { "@id": SITE + "#dealer" } }
        }, c.color ? { color: c.color } : {})
      }));
      return a + JSON.stringify(ld) + z;
    }, "JSON-LD");
    const rows = cars.map(c => `- [${c.make} ${c.model} ${c.ver}](${c.sub || SITE}): ${eur(c.price)}, ${c.reg}, ${fmt(c.km)} km, ${c.fuel.toLowerCase()}, ${c.gear.toLowerCase()}`).join("\n");
    let t = replaceOnce(files.llms, /(## Auto in vendita\n\n[^\n]*\n\n)(?:- [^\n]*\n)*/, (m, a) => a + rows + "\n", "llms");
    t = t.replace(/Elenco sincronizzato con il negozio Subito di Nico Automotive\./, "Elenco aggiornato dal salone Nico Automotive.");
    t = t.replace(/Informazioni aggiornate al [^.]*\./, `Informazioni aggiornate al ${today.getDate()} ${MESI[today.getMonth()]} ${today.getFullYear()}.`);
    const iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
    const x = files.sitemap.replace(/<lastmod>[^<]*<\/lastmod>/, `<lastmod>${iso}</lastmod>`);
    return { index: s, llms: t, sitemap: x, cars };
  }

  const api = { parseCars, build, eur, fmt };
  if (typeof module !== "undefined") module.exports = api; else root.SiteBuild = api;
})(this);
