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
            b.close()
    finally:
        srv.shutdown()

    if res.get("fehler"):
        return [res["fehler"]]

    print(f"  Block '{res['block']}': {res['templates']} Templates · "
          f"{res['tds']} Zellen · {res['ctx']} Kontextzeilen · {res['flags']} markiert")

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
