"""Der Viewer wird wirklich GESTARTET und geprüft — nicht sein Quelltext.

## Warum es das gibt

Zwei Funktionen sind in dieser Sitzung fertig gebaut, getestet und committet
worden — und haben trotzdem **nichts** getan:

1. **#23, Peer-Kontext**: `ensureLoaded()` wies `rep.peer` nie zu. Die Shards
   trugen 6.177 Kontextzellen, der Viewer las eine leere Map.
2. **#23 und #24, Tooltips**: beide riefen `nf(v, min, max)` mit vertauschten
   Argumenten auf. `toLocaleString` wirft dann *maximumFractionDigits value is
   out of range* — und der Fehler reisst das **gesamte Rendern der Tabelle**
   mit. Keine Zelle erschien mehr.

Beide Male waren die Tests grün. Sie prüften den Shard-Inhalt und den
Quelltext des Viewers; dass aus beidem zusammen nichts wird, konnten sie nicht
sehen. Ein Test, der nur die Zutaten prüft, sagt nichts über das Gericht.

Deshalb dieser Lauf: echter Browser, echte Artefakte, und die Frage „steht
danach etwas da?".

Aufruf: python3 scripts/check_viewer_runtime.py
Rückgabe: 0 wenn alles steht, sonst 1 mit Begründung.
"""

from pathlib import Path
import functools
import gzip
import http.server
import os
import re
import socketserver
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent.parent
VIEWER_DIR = ROOT / "processed" / "zweig_a"
DATA = VIEWER_DIR / "data"
PORT = 8799
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

# Die Startseite darf diese Datei NICHT brauchen. 9,41 MB, und die erste
# Ansicht fasst kein einziges Zelllabel an.
NICHT_BEIM_START = "labels.json"


class _H(http.server.SimpleHTTPRequestHandler):
    """Liefert gzip aus, wie GitHub Pages — sonst misst man Rohbytes, die so
    nie über die Leitung gehen."""

    def log_message(self, *a):
        pass

    def do_GET(self):
        pfad = self.translate_path(self.path)
        if not os.path.isfile(pfad):
            return super().do_GET()
        daten = Path(pfad).read_bytes()
        typ = self.guess_type(pfad)
        if "gzip" in (self.headers.get("Accept-Encoding") or "") and (
                typ.startswith("text/") or "json" in typ or "javascript" in typ):
            daten = gzip.compress(daten, 6)
            self.send_response(200)
            self.send_header("Content-Encoding", "gzip")
        else:
            self.send_response(200)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(daten)))
        self.end_headers()
        self.wfile.write(daten)


def _serve():
    socketserver.TCPServer.allow_reuse_address = True
    h = functools.partial(_H, directory=str(VIEWER_DIR))
    srv = socketserver.TCPServer(("", PORT), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def pruefe_export(res):
    """Der Export (#50) — und zwar sein INHALT, nicht sein Vorhandensein.

    Eine CSV ohne die Caveats, die im Viewer danebenstehen, ist gefährlicher als
    keine: sie wandert als scheinbar sauberer Datensatz weiter. Geprüft wird
    deshalb, dass die Warnungen drin sind, dass die Marken je ZEILE stehen (ein
    Kopfkommentar sagt nicht, welche Zeile betroffen ist) und dass die Datei
    sich mit `comment='#'` wieder einlesen lässt.
    """
    import csv as _csv
    import io

    fehler = []
    text = res.get("csv") or ""
    if not res.get("knopf"):
        fehler.append("kein Export-Knopf in der Benchmark-Leiste (#50)")
    if not text:
        fehler.append("benchmarkCSV() liefert nichts")
        return fehler

    kopf = [z for z in text.splitlines() if z.startswith("#")]
    daten = [z for z in text.splitlines() if not z.startswith("#")]
    print(f"  CSV-Export: {len(kopf)} Kommentarzeilen · {len(daten)-1} Datenzeilen")

    for pflicht, was in [("Aufsichtsmetrik", "der Vergleichbarkeits-Caveat"),
                         ("nicht null", "der Hinweis „Fehlt ≠ Null\""),
                         ("skalenbefund", "die Erklärung der Skalenspalte"),
                         ("Ansicht: http", "die Rück-URL auf die eigene Ansicht"),
                         ("Filter/Zustand", "der Filterzustand")]:
        if pflicht not in text:
            fehler.append(f"CSV-Export ohne {was}")

    try:
        zeilen = list(_csv.DictReader(io.StringIO("\n".join(daten))))
    except Exception as e:                       # noqa: BLE001
        fehler.append(f"CSV nicht lesbar: {e}")
        return fehler
    if not zeilen:
        fehler.append("CSV-Export ohne Datenzeilen")
        return fehler
    fehlend = [s for s in ("institut", "lei", "stichtag", "framework",
                           "skalenbefund", "plausibilitaet") if s not in zeilen[0]]
    for spalte in fehlend:
        fehler.append(f"CSV-Export ohne Spalte '{spalte}' — ein Caveat im Kopf "
                      "sagt nicht, WELCHE Zeile betroffen ist")
    if None in zeilen[0]:
        # DictReader legt ueberzaehlige Felder unter None ab: die Kopfzeile hat
        # weniger Spalten als die Datenzeilen. Ohne diesen Zweig stuerzt die
        # Zahlenpruefung unten ab, statt den Fehler zu melden — ein Absturz ist
        # kein Befund, er sieht nur aus wie einer.
        fehler.append("CSV-Kopfzeile und Datenzeilen haben verschiedene Spaltenzahlen")
        return fehler
    # Gleitkomma-Rest: `387.59999999999997` behauptet 17 SIGNIFIKANTE Stellen
    # fuer einen Wert, der im Meldebogen vier hatte. Gezaehlt werden
    # signifikante Stellen, nicht Nachkommastellen — `0.00057464628999` hat 14
    # Nachkommastellen und ist mit 8 signifikanten voellig in Ordnung.
    def signifikant(w):
        z = w.lstrip("-").replace(".", "").lstrip("0")
        return len(z.rstrip("0")) if z else 0
    lang = [(s, w) for z in zeilen for s, w in z.items()
            if w and re.fullmatch(r"-?\d*\.?\d+", w) and signifikant(w) > 12]
    if lang:
        fehler.append(f"{len(lang)} Zahlen im Export mit Gleitkomma-Rest, z. B. "
                      f"{lang[0][0]}={lang[0][1]} — das ist Binärrest, keine Genauigkeit")
    return fehler


def pruefe():
    from playwright.sync_api import sync_playwright

    fehler = []
    srv = _serve()
    time.sleep(0.5)
    try:
        with sync_playwright() as pw:
            start = {"executable_path": CHROMIUM} if Path(CHROMIUM).exists() else {}
            b = pw.chromium.launch(args=["--no-sandbox"], **start)
            pg = b.new_page()
            seitenfehler = []
            pg.on("pageerror", lambda e: seitenfehler.append(str(e)[:200]))
            pg.goto(f"http://localhost:{PORT}/viewer_json.html",
                    wait_until="networkidle", timeout=120000)

            geladen = pg.evaluate(
                "() => performance.getEntriesByType('resource')"
                ".map(r => r.name.split('/').pop())")
            print(f"  beim Start geladen: {', '.join(geladen)}")

            # Einen grossen Report oeffnen und einen Block aufklappen.
            pg.evaluate("""async () => {
              const rep = REPORTS.slice().sort((a,b)=>b.nt-a.nt)[0];
              const p = leiParts(rep.entityID);
              location.hash = '#r/'+p.lei+'/'+rep.refPeriod+'/'+p.scope;
            }""")
            pg.wait_for_timeout(2500)
            res = pg.evaluate("""async () => {
              const cont=document.getElementById('tcontainer');
              const lists = cont && cont._lists;
              const ds=[...document.querySelectorAll('details.theme')];
              const beste = ds.map(d=>({d, n:(lists&&lists.get(d.dataset.t)||[]).length}))
                              .sort((a,b)=>b.n-a.n)[0];
              if(!beste || !beste.n) return {fehler:'kein Themenblock mit Templates'};
              const d=beste.d, bd=d.querySelector('.tbody');
              d.open=true;
              let g=0; while(g++<600 && bd.dataset.done!=='1')
                await new Promise(s=>setTimeout(s,10));
              return {block:d.dataset.t, templates:beste.n,
                      tds: bd.querySelectorAll('td').length,
                      werte: bd.querySelectorAll('td.num').length,
                      ctx: bd.querySelectorAll('span.ctxline').length,
                      flags: document.querySelectorAll('td.oddcell').length};
            }""")
            # Skalenbefund (#83): einen markierten Report oeffnen und
            # nachsehen, ob die Marke im DOM ankommt. Sie ist der einzige
            # Hinweis darauf, dass die absoluten Betraege dieses Reports nicht
            # zu gebrauchen sind — bei 50 der 100 markierten Reports meldet die
            # Plausibilitaetspruefung NULL Befunde, dort steht sonst nichts.
            skala = pg.evaluate("""async () => {
              const rep = REPORTS.find(r => r.quality && r.quality.sc);
              if(!rep) return {keine:1};
              const p = leiParts(rep.entityID);
              location.hash = '#r/'+p.lei+'/'+rep.refPeriod+'/'+p.scope;
              for(let g=0; g<400 && !document.querySelector('.ovsc'); g++)
                await new Promise(s=>setTimeout(s,10));
              const n=document.querySelector('.ovsc');
              return {urteil:rep.quality.sc.u, n:REPORTS.filter(r=>r.quality&&r.quality.sc).length,
                      text:n?n.textContent.replace(/\\s+/g,' ').trim():''};
            }""")
            # Groessenbalken (#49): erscheinen sie — und bleiben sie dort WEG,
            # wo sie luegen wuerden? Ein Balken fuer einen um 10^6 zu kleinen
            # Betrag zeigt ein winziges Institut statt eines Meldefehlers.
            balken = pg.evaluate("""async () => {
              location.hash = '#benchmark';
              for(let g=0; g<600 && !document.querySelector('table tbody tr'); g++)
                await new Promise(s=>setTimeout(s,10));
              await new Promise(s=>setTimeout(s,300));
              const zeilen=[...document.querySelectorAll('table tbody tr')];
              let mitMarke=0, markeMitBalken=0;
              for(const tr of zeilen){
                const skaliert = tr.classList.contains('scaled');
                if(!skaliert) continue;
                mitMarke++;
                if(tr.querySelector('.szf')) markeMitBalken++;
              }
              const res = {zeilen:zeilen.length,
                      balken:document.querySelectorAll('.szf').length,
                      legende:!!document.querySelector('.bmlegend'),
                      mitMarke, markeMitBalken, strittig:null};
              // Und dasselbe fuer ein Profil auf der Einheiten-Sperrliste (#9).
              // `esg` laeuft auf 41.00, wo Institute nachweislich in
              // verschiedenen Einheiten melden — dort darf KEIN Balken stehen.
              const sel=document.getElementById('bmProfile');
              const ua=[...sel.options].map(o=>o.value)
                 .find(v=>{ const p=bmAll()[v]; return p && UA.has(p.tpl); });
              if(ua){
                sel.value=ua; sel.dispatchEvent(new Event('change'));
                await new Promise(s=>setTimeout(s,600));
                res.strittig={profil:ua,
                  zeilen:document.querySelectorAll('table tbody tr').length,
                  balken:document.querySelectorAll('.szf').length};
              }
              // Die beiden Sperren als FUNKTION. Kein heutiges Profil verbindet
              // ein strittiges Template mit einer Betragsspalte, also belegt die
              // gerenderte Tabelle dort nichts — ein Test an ihr waere gruen,
              // ohne irgendetwas zu pruefen.
              const sauber={q:null}, skal={q:{sc:{u:'skaliert',t:[]}}};
              const tplSkal={q:{sc:{u:'skaliert',t:['61.00']}}};
              res.regel={
                normal:  barErlaubt({tpl:'61.00'}, sauber),
                skala:   barErlaubt({tpl:'61.00'}, skal),
                tplTrifft: barErlaubt({tpl:'61.00'}, tplSkal),
                tplDaneben: barErlaubt({tpl:'60.00.A'}, tplSkal),
                strittig: ua ? barErlaubt({tpl:bmAll()[ua].tpl}, sauber) : null};
              // CSV-Export (#50): den Text direkt erzeugen, nicht den Download
              // anstossen — geprueft wird der INHALT, und ein Klick lieferte im
              // Headless-Browser nur eine Datei, die niemand liest.
              sel.value='km1'; sel.dispatchEvent(new Event('change'));
              await new Promise(s=>setTimeout(s,600));
              const p2=bmAll()['km1'];
              const zeilen2=benchmarkRows();
              res.csv=benchmarkCSV(zeilen2.slice(0,50), p2);
              res.knopf=!!document.getElementById('bmCsv');
              // Teilbarer Zustand (#50): Sortierung und Auswahl im Hash.
              const erste=REPORTS[0], zweite=REPORTS[1];
              PINS=new Set([repKey(erste), repKey(zweite)]);
              bmSort={col:'cet1', dir:1};
              const par=shareParams();
              res.teilbar={pin:par.get('pin')||'', sort:par.get('sort')||''};
              PINS=new Set();
              return res;
            }""")
            b.close()
    finally:
        srv.shutdown()

    if res.get("fehler"):
        return [res["fehler"]]

    print(f"  Block '{res['block']}': {res['templates']} Templates · "
          f"{res['tds']} Zellen · {res['ctx']} Kontextzeilen · {res['flags']} markiert")
    if skala.get("keine"):
        print("  (kein Report mit Skalenmarke im Index — Prüfung übersprungen)")
    else:
        print(f"  Skalenmarke: {skala['n']} Reports · gerendert: "
              f"{skala['text'][:110] or '— NICHTS —'}")
        if not skala["text"]:
            fehler.append("Report mit Skalenbefund (#83) zeigt keine Marke — "
                          "der Index trägt sie, der Viewer rendert sie nicht")

    print(f"  Benchmark: {balken['zeilen']} Zeilen · {balken['balken']} Größenbalken · "
          f"skaliert markiert {balken['mitMarke']}, davon mit Balken {balken['markeMitBalken']}")
    if balken["zeilen"] and not balken["balken"]:
        fehler.append("kein einziger Größenbalken (#49) in der Benchmark-Tabelle — "
                      "die Spalten tragen Beträge, die Zellen zeigen nur Zahlen")
    if balken["zeilen"] and not balken["legende"]:
        fehler.append("Größenbalken ohne Legende — eine Länge ohne Bezug ist "
                      "eine Behauptung, die niemand prüfen kann")
    if balken["markeMitBalken"]:
        fehler.append(f"{balken['markeMitBalken']} skalierte Reports (#83) tragen einen "
                      "Größenbalken — er zeigt dort ein winziges Institut statt "
                      "eines Meldefehlers")
    # Die Regel selbst, unabhaengig davon, ob ein heutiges Profil sie ausloest.
    regel = balken.get("regel") or {}
    erwartet = {"normal": True, "skala": False, "tplTrifft": False,
                "tplDaneben": True, "strittig": False}
    falsch = [k for k, v in erwartet.items()
              if regel.get(k) is not None and regel[k] is not v]
    print("  Balkenregel: " + "  ".join(
        f"{k}={'ja' if regel.get(k) else 'nein'}" for k in erwartet))
    if falsch:
        fehler.append("barErlaubt() entscheidet falsch bei: " + ", ".join(falsch))

    s = balken.get("strittig")
    if s:
        print(f"  Profil '{s['profil']}' (strittige Einheit, #9): {s['zeilen']} Zeilen · "
              f"{s['balken']} Größenbalken")
        if s["zeilen"] and s["balken"]:
            fehler.append(f"{s['balken']} Größenbalken im Profil '{s['profil']}' — dessen "
                          "Template steht auf der Einheiten-Sperrliste, ein "
                          "Längenvergleich behauptet dort Vergleichbarkeit, die es "
                          "nicht gibt")

    fehler += pruefe_export(balken)

    t = balken.get("teilbar") or {}
    print(f"  Teilbarer Zustand: pin='{t.get('pin','')}' sort='{t.get('sort','')}'")
    if not t.get("pin"):
        fehler.append("die Auswahl (#50) landet nicht im Hash — ein Vergleich "
                      "lässt sich dann nur beschreiben, nicht weitergeben")
    if not t.get("sort"):
        fehler.append("die Sortierung (#50) landet nicht im Hash — der Empfänger "
                      "eines Links sieht eine andere Reihenfolge und damit eine "
                      "andere Spitze")

    if seitenfehler:
        fehler.append(f"JavaScript-Fehler beim Rendern: {seitenfehler[0]}")
    if NICHT_BEIM_START in geladen and geladen.index(NICHT_BEIM_START) < 3:
        fehler.append(f"{NICHT_BEIM_START} wird zu früh geladen — die Startseite "
                      "braucht keine Zelllabels")
    if res["werte"] < 100:
        fehler.append(f"nur {res['werte']} Wertzellen gerendert — die Tabelle ist leer")
    # Die beiden Funktionen, die schon einmal still nichts taten:
    if (DATA / "reports").exists() and res["ctx"] == 0:
        fehler.append("keine einzige Peer-Kontextzeile (#23) im DOM — "
                      "die Shards tragen sie, der Viewer zeigt sie nicht")
    return fehler


if __name__ == "__main__":
    if not (DATA / "index.json").exists():
        print("✗ Zweig-A-Artefakte fehlen — erst build_zweig_a_shards.py laufen lassen")
        sys.exit(1)
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("✗ playwright fehlt: pip install playwright")
        sys.exit(1)
    print("Viewer-Laufzeitprüfung:")
    probleme = pruefe()
    if probleme:
        for p in probleme:
            print(f"  ✗ {p}")
        sys.exit(1)
    print("  ✓ Viewer rendert, Kontextzahlen stehen, Startseite bleibt schlank")
