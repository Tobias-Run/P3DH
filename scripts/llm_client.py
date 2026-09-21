"""Ein dünner Client gegen OpenAI-kompatible Endpunkte (#38b).

Das Lesen der DISDOCS-Berichte ist eine Aufgabe über 21 Sprachen, die kein
Skript leistet. Dieses Modul stellt die Werkzeuge bereit, **damit ein Modell
sie übernehmen kann, ohne dass das Projekt seine Zusagen aufgibt**:
Reproduzierbarkeit, „Fehlt ≠ Null", und nichts behaupten, was nicht belegt ist.

> ⚠️ **Dieser Client ist nie an einem echten Modell gelaufen.** Er ist
> vollständig gegen eine Attrappe geprüft — Schema, Cache, Herkunft,
> Zitatprüfung, Abbruchverhalten —, aber in der Umgebung, in der er entstand,
> gab es keinen Endpunkt. Was ein echtes Modell tut, steht damit noch aus:
> Antwortqualität, Halluzinationsrate, Laufzeit. Der erste Lauf gegen LM
> Studio ist deshalb kein Routinelauf, sondern eine Messung (38d).

## Warum das Zitat mechanisch geprüft wird — der Kern des Ganzen

Ein LLM erfindet Belege, und zwar überzeugend. Deshalb muss jede Aussage ein
**wörtliches Zitat** samt Seitenzahl tragen, und `zitat_geprueft()` schlägt
es im extrahierten Text nach. Kommt es dort nicht vor, ist die Zeile
verworfen — ohne Urteil, ohne Ermessen, mit einem Stringvergleich.

Dadurch bekommt jedes Modell eine **messbare Halluzinationsrate**, und ein
Modellwechsel wird vergleichbar statt Geschmackssache. Ohne diesen Schritt
wäre der ganze Aufbau eine Meinungsmaschine mit Nachkommastellen.

## Reproduzierbarkeit, obwohl das Modell nicht deterministisch ist

Nicht der *Aufruf* ist reproduzierbar, sondern das *Ergebnis* — weil es mit
seiner Herkunft gespeichert wird: Modell, Prompt-Fassung und -Hash,
Eingabe-Hash, Temperatur, Seed, Zeitpunkt. Der Cache ist damit ein Artefakt
wie jedes andere: wer ihn hat, bekommt unsere Ergebnisse, ohne ein Modell zu
besitzen. Wer ein anderes Modell einsetzt, erzeugt eine zweite Spalte in der
Herkunft — kein Überschreiben.

**CI ruft kein Modell auf.** Nichtdeterministisch, langsam, und dort steht
keines. CI prüft den Cache: Schema eingehalten, jedes Zitat verifizierbar,
Herkunftsfelder vollständig. Das ist deterministisch und fängt die Fehler,
die zählen.

## Was der Client NICHT tut

- **Keine Sprachbestimmung.** Die ist deterministisch gelöst (#38a) und muss
  es bleiben, sonst verschiebt ein Modellwechsel sie.
- **Keine Zahlen aus dem Fliesstext.** Die Zahlen haben wir geprüft, normiert
  und mit Stichtag. Eine aus Text gelesene Quote wäre eine zweite, schlechtere
  Wahrheit neben Zweig B.
- **Keine Absichtszuschreibung.** „Text und Zahl passen nicht zusammen" ist
  ein Befund; „die Bank beschönigt" eine Unterstellung.

## Umgebung

    P3DH_LLM_BASE_URL   default http://localhost:1234/v1   (LM Studio)
    P3DH_LLM_MODEL      z. B. qwen2.5-14b-instruct
    P3DH_LLM_API_KEY    von LM Studio ignoriert, für gehostete Endpunkte nötig

Aufruf:
    python3 scripts/llm_client.py --pruefen          # Erreichbarkeit
    python3 scripts/llm_client.py --dry-run ...      # Prompts, ohne zu senden
"""

from pathlib import Path
import hashlib
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent

BASIS = os.environ.get("P3DH_LLM_BASE_URL", "http://localhost:1234/v1")
MODELL = os.environ.get("P3DH_LLM_MODEL", "")
SCHLUESSEL = os.environ.get("P3DH_LLM_API_KEY", "")

CACHE = ROOT / "interim" / "llm_cache.jsonl"

# Die Fassung des Prompts. Ändert sich der Text, MUSS diese Zahl steigen —
# sonst liefert der Cache Antworten auf eine Frage, die so nicht mehr
# gestellt wird, und niemand merkt es.
PROMPT_FASSUNG = 1

# Temperatur 0 und fester Seed: sie machen das Modell nicht deterministisch
# (das tut auf GPU niemand), aber sie nehmen die Streuung heraus, die man
# selbst verursacht hätte.
TEMPERATUR = 0.0
SEED = 20260921

# Herkunftsfelder, die JEDE Cache-Zeile tragen muss. Eine Antwort ohne
# Herkunft ist nicht nachvollziehbar und damit für dieses Projekt wertlos.
HERKUNFT = ("model", "endpoint_kind", "prompt_version", "prompt_sha",
            "input_sha", "temperature", "seed", "created_utc")


def hash_von(text):
    """Stabiler Kurz-Hash. Kürzer als sha256, lang genug gegen Kollisionen."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def endpunkt_art(basis=None):
    """`lokal` oder `gehostet` — gehört in die Herkunft.

    Ob der Korpus das Haus verlassen hat, ist keine Fussnote: es ist der
    Unterschied, den der Septemberkommentar zu #38 ausdrücklich benennt.
    """
    b = (basis or BASIS or "").lower()
    return "lokal" if ("localhost" in b or "127.0.0.1" in b or "::1" in b) \
        else "gehostet"


def normalisiere(text):
    """Für den Zitatvergleich: Unicode, Bindestriche, Leerraum vereinheitlicht.

    Ein Modell gibt ein Zitat selten zeichengenau zurück — es normalisiert
    typografische Anführungszeichen, ersetzt einen weichen Trennstrich, zieht
    einen Zeilenumbruch zu einem Leerzeichen zusammen. Das sind **keine**
    Erfindungen, und sie deshalb als Halluzination zu zählen machte die
    Halluzinationsrate zu einem Mass für Typografie.

    Was hier NICHT vereinheitlicht wird: Buchstaben und Ziffern. Wer „2,4 %"
    schreibt, wo „4,2 %" steht, hat nicht anders formatiert.
    """
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = t.replace("­", "")                       # weicher Trennstrich
    t = re.sub(r"[‐-―−]", "-", t)      # Bindestrich-Familie
    t = re.sub(r"[‘’‚′']", "'", t)
    t = re.sub(r"[“”„″\"]", '"', t)
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


def zitat_geprueft(zitat, quelltext, min_zeichen=20):
    """Steht das Zitat WÖRTLICH im Quelltext?

    Der mechanische Kern des ganzen Aufbaus. Kein Ermessen, kein Modell, ein
    Stringvergleich — und damit eine Grösse, die ein Modellvergleich braucht.

    Ein sehr kurzes Zitat ist dabei kein Beleg: „Kreditqualität" kommt in
    jedem Bericht vor und belegt nichts. Unterhalb von `min_zeichen` gilt es
    als ungeprüft, nicht als bestätigt.
    """
    if not zitat or not quelltext:
        return False
    z = normalisiere(zitat)
    if len(z) < min_zeichen:
        return False
    return z in normalisiere(quelltext)


def antwort_gueltig(obj, felder=("aussage", "zitat", "seite")):
    """Trägt die Antwort die Form, die abgesprochen war?

    Ein Modell, das statt des Schemas einen Fliesstext liefert, ist kein
    Sonderfall, sondern der Normalfall bei kleinen Modellen. Ein `except:
    pass` hier hiesse: solche Antworten verschwinden, und die Ausbeute sieht
    aus wie „nichts gefunden" statt wie „Modell hält sich nicht ans Format".
    """
    if not isinstance(obj, dict):
        return False
    return all(f in obj and obj[f] not in (None, "") for f in felder)


def cache_schluessel(modell, prompt, eingabe, fassung=PROMPT_FASSUNG):
    """Was eine Antwort eindeutig macht.

    Das Modell gehört hinein: dieselbe Frage an ein anderes Modell ist eine
    andere Antwort und darf die erste nicht verdrängen. Die Prompt-Fassung
    auch — sonst beantwortet der Cache eine Frage, die so nicht mehr gestellt
    wird.
    """
    return f"{modell}|{fassung}|{hash_von(prompt)}|{hash_von(eingabe)}"


def lade_cache(pfad=None):
    """JSONL -> {Schlüssel: Zeile}. Kaputte Zeilen werden übersprungen, aber
    gezählt — ein stillschweigend halber Cache wäre eine stille Wiederholung
    teurer Aufrufe."""
    pfad = Path(pfad) if pfad else CACHE
    eintraege, kaputt = {}, 0
    if not pfad.exists():
        return eintraege, kaputt
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        if not zeile.strip():
            continue
        try:
            d = json.loads(zeile)
        except json.JSONDecodeError:
            kaputt += 1
            continue
        if d.get("key"):
            eintraege[d["key"]] = d
        else:
            kaputt += 1
    return eintraege, kaputt


def schreibe_cache(zeile, pfad=None):
    """Anhängen, nicht neu schreiben.

    Ein Lauf über 1.073 Dokumente darf bei Abbruch nicht alles verlieren —
    dieselbe Lehre wie beim GLEIF-Abruf. Anhängen ist hier richtig, wo
    `os.replace` es bei einer Tabelle wäre: es gibt keinen Zustand, der halb
    geschrieben unbrauchbar wäre.
    """
    pfad = Path(pfad) if pfad else CACHE
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with pfad.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(zeile, ensure_ascii=False) + "\n")


def herkunft(modell, prompt, eingabe, basis=None, fassung=PROMPT_FASSUNG):
    """Die Felder, ohne die eine Antwort nicht nachvollziehbar ist."""
    return {
        "model": modell,
        "endpoint_kind": endpunkt_art(basis),
        "prompt_version": fassung,
        "prompt_sha": hash_von(prompt),
        "input_sha": hash_von(eingabe),
        "temperature": TEMPERATUR,
        "seed": SEED,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# --- alles ab hier redet mit dem Endpunkt ------------------------------------

def _post(pfad, nutzlast, basis=None, schluessel=None, timeout=300):
    basis = basis or BASIS
    kopf = {"Content-Type": "application/json"}
    s = schluessel if schluessel is not None else SCHLUESSEL
    if s:
        kopf["Authorization"] = f"Bearer {s}"
    req = urllib.request.Request(
        basis.rstrip("/") + pfad,
        data=json.dumps(nutzlast).encode("utf-8"),
        headers=kopf, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return json.load(fh)


def erreichbar(basis=None, schluessel=None, timeout=10):
    """(bool, Meldung) — VOR dem Lauf, nicht nach 300 Dokumenten.

    Die Lehre aus dem GLEIF-Abruf: ein Lauf, der nach vierzig Minuten am
    Verbindungsfehler stirbt, hat vierzig Minuten gekostet und nichts
    geliefert.
    """
    basis = basis or BASIS
    kopf = {}
    s = schluessel if schluessel is not None else SCHLUESSEL
    if s:
        kopf["Authorization"] = f"Bearer {s}"
    try:
        req = urllib.request.Request(basis.rstrip("/") + "/models", headers=kopf)
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            d = json.load(fh)
        namen = [m.get("id") for m in d.get("data", []) if m.get("id")]
        return True, f"{len(namen)} Modell(e): {', '.join(namen[:5])}"
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        return False, f"{basis} nicht erreichbar: {str(e)[:80]}"


def frage(prompt, eingabe, modell=None, basis=None, cache_pfad=None,
          trocken=False):
    """Eine Frage an das Modell — oder aus dem Cache, oder nur gezeigt.

    `trocken=True` sendet nichts und gibt zurück, was gesendet WÜRDE. Damit
    lässt sich die Hochrechnung über 48 Mio Tokens prüfen, bevor Rechenzeit
    fliesst.
    """
    modell = modell or MODELL
    schluessel = cache_schluessel(modell, prompt, eingabe)
    eintraege, _ = lade_cache(cache_pfad)
    if schluessel in eintraege:
        return {**eintraege[schluessel], "aus_cache": True}

    nutzlast = {
        "model": modell,
        "messages": [{"role": "system", "content": prompt},
                     {"role": "user", "content": eingabe}],
        "temperature": TEMPERATUR,
        "seed": SEED,
    }
    if trocken:
        return {"trocken": True, "key": schluessel, "nutzlast": nutzlast,
                "zeichen": len(prompt) + len(eingabe),
                # Grobe Faustregel aus dem Septemberkommentar: Zeichen/3,5.
                # Eine Schätzung, ausdrücklich als solche benannt — der
                # Tokenizer des Modells kennt sie nicht.
                "tokens_geschaetzt": round((len(prompt) + len(eingabe)) / 3.5),
                **herkunft(modell, prompt, eingabe, basis)}

    roh = _post("/chat/completions", nutzlast, basis=basis)
    text = (roh.get("choices") or [{}])[0].get("message", {}).get("content", "")
    zeile = {"key": schluessel, "antwort": text,
             **herkunft(modell, prompt, eingabe, basis)}
    schreibe_cache(zeile, cache_pfad)
    return {**zeile, "aus_cache": False}


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pruefen", action="store_true",
                   help="nur die Erreichbarkeit des Endpunkts prüfen")
    p.add_argument("--cache", default=None)
    args = p.parse_args()

    print(f"Endpunkt : {BASIS}  ({endpunkt_art()})")
    print(f"Modell   : {MODELL or '— nicht gesetzt (P3DH_LLM_MODEL)'}")
    eintraege, kaputt = lade_cache(args.cache)
    print(f"Cache    : {len(eintraege)} Antwort(en)"
          + (f", {kaputt} unlesbare Zeile(n)" if kaputt else ""))
    if args.pruefen:
        ok, meldung = erreichbar()
        print(f"{'✓' if ok else '✗'} {meldung}")
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
