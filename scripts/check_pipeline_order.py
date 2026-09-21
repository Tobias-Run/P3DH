"""Die Reihenfolge der Pipeline gegen die Abhängigkeiten der Skripte (#8).

Ausgabe: nur Konsole. Rückgabe 0, wenn die Kette eine gültige Topologie ist.

## Warum es das gibt

#8 will den wöchentlichen Cron scharf schalten. Die Vorbedingung lautet „ein
manueller Lauf komplett grün" — aber grün heisst nur, dass kein Schritt mit
Exit-Code != 0 endete. Genau das ist bei einer Reihenfolgenverletzung **nicht**
der Fall:

    build_footprint.py       ohne scale_flags.csv  -> markiert nichts, Exit 0
    build_omission_profile.py ohne disclosure_frequency.csv
                             -> schreibt eine Datei mit Kopfzeile und ohne
                                Inhalt, Exit 0

Beide Fehler sind im September 2026 tatsächlich passiert (#83 und #43 Punkt 4),
beide wären einem grünen Lauf nicht aufgefallen, und beide wurden bisher mit je
einem eigenen Test abgefangen. Ein Cron, der unbeaufsichtigt läuft, braucht die
allgemeine Form davon: **wer eine Datei liest, die ein anderer Schritt derselben
Kette schreibt, muss nach ihm laufen.**

## Die Deklaration wird gegen den Quelltext geprüft

`ABHAENGIG` steht hier und nicht im Workflow, weil sie eine Eigenschaft der
Skripte ist. Eine Deklaration, die niemand nachhält, ist allerdings schlimmer
als keine — deshalb prüft `pruefe_deklaration()`, dass jeder deklarierte Pfad im
Quelltext des Skripts auch wirklich vorkommt. Wer eine Abhängigkeit hinzufügt
und die Tabelle vergisst, bekommt keinen Fehler; wer die Tabelle erfindet, schon.

Das ist die ehrliche Grenze dieses Guards: er findet FALSCHE Reihenfolgen, nicht
VERGESSENE Abhängigkeiten. Für letztere gibt es keine Prüfung, die ohne einen
echten Lauf auskommt.

Aufruf: python3 scripts/check_pipeline_order.py
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "pipeline.yml"
SCRIPTS = ROOT / "scripts"

# {Skript: (liest, schreibt)} — nur Artefakte, die INNERHALB der Kette
# entstehen. Externe Quellen (DPM-Zip, EZB-API, GLEIF) stehen nicht drin: sie
# haben keine Reihenfolge innerhalb der Pipeline.
#
# Gepflegt wird, was für die REIHENFOLGE zählt. Ein Skript, das nur das Parquet
# liest, hängt an build_zweig_b und sonst an nichts.
ABHAENGIG = {
    "harvest_catalog_query.py": ([], ["interim/edap_recon/manifest_full.csv"]),
    "build_parse_manifest.py": (["interim/edap_recon/manifest_full.csv"],
                                ["interim/edap_recon/manifest_parse.csv"]),
    "build_entity_meta.py": ([], ["processed/entity_meta.csv"]),
    "fetch_fx_rates.py": ([], ["processed/fx_rates.csv"]),
    # Die Kante, vor der #7 ausdrücklich warnt: „Ohne aktualisierte EZB-Kurse
    # hat ein neuer Stichtag keinen fx_rate ⇒ fact_value_eur bleibt für alle
    # Nicht-EUR-Fakten STILL leer." Genau diese Reihenfolge ist damit geprüft
    # und nicht mehr Gedächtnissache.
    "build_zweig_b.py": (["processed/entity_meta.csv", "processed/fx_rates.csv"],
                         ["processed/long/p3dh_long.parquet"]),
    "build_disclosure_lag.py": (["interim/edap_recon/manifest_full.csv",
                                 "processed/entity_meta.csv"],
                                ["processed/disclosure_lag.csv"]),
    "build_dataset_manifest.py": (["interim/edap_recon/manifest_full.csv",
                                   "processed/long/p3dh_long.parquet"],
                                  ["processed/long/manifest.json"]),
    "build_framework_bridge.py": (["processed/long/p3dh_long.parquet"],
                                  ["codebook/framework_bridge.csv"]),
    "build_report_scale.py": (["processed/long/p3dh_long.parquet"],
                              ["processed/scale_flags.csv"]),
    "check_plausibility.py": (["processed/long/p3dh_long.parquet",
                               "processed/scale_flags.csv",
                               "codebook/framework_bridge.csv",
                               "processed/disclosure_frequency.csv"],
                              ["processed/quality_profile.csv",
                               "interim/plausibility_findings.csv"]),
    "build_footprint.py": (["processed/long/p3dh_long.parquet",
                            "processed/scale_flags.csv"],
                           ["processed/footprint.csv"]),
    "build_rwa_density.py": (["processed/long/p3dh_long.parquet"],
                             ["processed/rwa_density.csv"]),
    "build_irb_risk_weights.py": (["processed/long/p3dh_long.parquet"],
                                  ["processed/irb_risk_weights.csv"]),
    "build_disclosure_frequency.py": (["processed/filing_indicators.csv"],
                                      ["processed/disclosure_frequency.csv"]),
    "build_omission_profile.py": (["processed/filing_indicators.csv",
                                   "processed/long/p3dh_long.parquet",
                                   "processed/disclosure_frequency.csv"],
                                  ["processed/omission_profile.csv",
                                   "processed/omission_persistence.csv"]),
    "build_irrbb_sensitivity.py": (["processed/long/p3dh_long.parquet",
                                    "processed/scale_flags.csv"],
                                   ["processed/irrbb_sensitivity.csv"]),
    "check_group_graphs.py": (["processed/lei_relations.csv",
                               "processed/coverage_gap.csv"],
                              ["processed/group_graph_check.csv"]),
    "check_consolidation.py": (["processed/footprint.csv",
                                "processed/lei_relations.csv",
                                "processed/long/p3dh_long.parquet"],
                               ["processed/consolidation_check.csv"]),
    "build_peer_similarity.py": (["processed/long/p3dh_long.parquet",
                                  "processed/lei_relations.csv",
                                  "processed/coverage_gap.csv"],
                                 ["processed/peer_similarity.csv"]),
    "build_exposure_graph.py": (["processed/long/p3dh_long.parquet",
                                 "processed/entity_groups.csv",
                                 "processed/country_swap.csv"],
                                ["processed/country_dependence.csv",
                                 "processed/contagion_edges.csv"]),
    "build_submission_profile.py": (["interim/edap_recon/manifest_full.csv",
                                     "processed/quality_profile.csv",
                                     "processed/entity_meta.csv"],
                                    ["processed/submission_profile.csv",
                                     "processed/persistent_findings.csv"]),
    "build_credit_chain.py": (["processed/long/p3dh_long.parquet",
                               "processed/entity_meta.csv"],
                              ["processed/credit_chain.csv"]),
    "check_country_swap.py": (["processed/long/p3dh_long.parquet"],
                              ["processed/country_swap.csv"]),
    "check_proportionality.py": (["processed/omission_profile.csv",
                                  "processed/long/p3dh_long.parquet"],
                                 ["processed/proportionality.csv"]),
    # Verbindet beide Konzerngraphen (#32/#42) zu einer Zuordnung je Report.
    "build_entity_groups.py": (["processed/lei_relations.csv",
                                "processed/coverage_gap.csv",
                                "processed/entity_meta.csv",
                                "processed/long/p3dh_long.parquet"],
                               ["processed/entity_groups.csv"]),
    # Liest peer_similarity.csv NICHT als Datei, sondern importiert dessen
    # `lade`/`ueberlappung` — die Kante ist trotzdem echt: laeuft das Clustering
    # vor dem Aehnlichkeitsschritt, stuenden im Bericht Gruppen, die zum
    # veroeffentlichten Nachbarschaftsartefakt nicht passen.
    "build_peer_clusters.py": (["processed/lei_relations.csv",
                                "processed/peer_similarity.csv"],
                               ["processed/peer_clusters.csv"]),
    # Die deskriptive Schwester von check_country_effect.py: dieselben beiden
    # Quellen, aber als Normierung statt als Regression (#14).
    "build_country_exposure.py": (["processed/long/p3dh_long.parquet",
                                   "processed/footprint.csv",
                                   "processed/lei_relations.csv",
                                   "processed/fx_rates.csv",
                                   "codebook/country_gdp.csv"],
                                  ["processed/country_exposure.csv",
                                   "processed/country_concentration.csv"]),
    "check_country_effect.py": (["processed/footprint.csv",
                                 "codebook/country_gdp.csv"],
                                ["processed/country_effect.csv"]),
    # Haelt den Katalog gegen BEIDES: das Parquet und die Coverage-Matrix. Nur
    # aus dem Unterschied ist der #28-Fall (geparst, in der Matrix, ohne
    # platzierbaren Fakt) von einer echten Luecke zu unterscheiden.
    "check_catalogue_coverage.py": (["interim/edap_recon/manifest_full.csv",
                                     "interim/edap_recon/manifest_parse.csv",
                                     "processed/filing_indicators.csv",
                                     "processed/long/p3dh_long.parquet"],
                                    ["processed/catalogue_coverage.csv"]),
    # Der einzige Schritt mit einer FREMDEN Netzquelle. Seine Ausgabe liegt im
    # Repo, deshalb steht sie hier als Erzeugnis und nicht als Vorbedingung.
    "fetch_wikidata_entities.py": (["processed/long/p3dh_long.parquet"],
                                   ["codebook/wikidata_entities.csv"]),
    "build_equity_link.py": (["codebook/wikidata_entities.csv"],
                             ["processed/equity_link.csv"]),
    "check_event_study_feasibility.py": (
        ["interim/edap_recon/manifest_full.csv",
         "codebook/wikidata_entities.csv",
         "interim/plausibility_findings.csv"],
        ["processed/event_study_feasibility.csv"]),
    # Liest die Plausibilitaetsbefunde: ein Report mit `rem_per_head`-Befund
    # (#17) liefert die eine Haelfte des Quotienten. Laeuft dieser Schritt
    # zuerst, ist der Filter leer — und ein bekannter Ausreisser geht als
    # Governance-Aussage durch.
    "build_risk_taker_share.py": (["processed/long/p3dh_long.parquet",
                                   "codebook/wikidata_entities.csv",
                                   "interim/plausibility_findings.csv"],
                                  ["processed/risk_taker_share.csv"]),
    "build_zweig_a_shards.py": (["processed/long/p3dh_long.parquet",
                                 "processed/quality_profile.csv",
                                 "interim/plausibility_findings.csv",
                                 "processed/scale_flags.csv",
                                 "processed/peer_similarity.csv"],
                                ["processed/zweig_a/data/index.json"]),
}


def schritte(text=None):
    """Die Skripte in der Reihenfolge, in der der Workflow sie aufruft.

    Mehrfachaufrufe (xbrl_csv_parser läuft in drei Zweigen) behalten ihre
    erste Position: für die Reihenfolge zählt, wann ein Artefakt frühestens
    entsteht.
    """
    text = text if text is not None else WORKFLOW.read_text(encoding="utf-8")
    gesehen, aus = set(), []
    for treffer in re.finditer(r"python scripts/([a-z_0-9]+\.py)", text):
        name = treffer.group(1)
        if name not in gesehen:
            gesehen.add(name)
            aus.append(name)
    return aus


def verletzungen(reihenfolge, abhaengig=None):
    """Welcher Schritt liest ein Artefakt, das erst später entsteht?

    Liefert Tupel (Leser, Datei, Erzeuger). Leer heisst: die Kette ist eine
    gültige Topologie.

    Ein Skript, das gar nicht im Workflow steht, kann nichts verletzen — es
    wird übersprungen statt gemeldet. Sonst schlüge der Guard bei jedem
    Artefakt an, das ausserhalb der Pipeline gepflegt wird.
    """
    abhaengig = ABHAENGIG if abhaengig is None else abhaengig
    pos = {s: i for i, s in enumerate(reihenfolge)}
    erzeuger = {}
    for skript, (_, schreibt) in abhaengig.items():
        if skript in pos:
            for datei in schreibt:
                # Der FRÜHESTE Erzeuger zählt; zwei Schritte, die dieselbe
                # Datei schreiben, gibt es in dieser Kette nicht.
                if datei not in erzeuger or pos[skript] < pos[erzeuger[datei]]:
                    erzeuger[datei] = skript

    aus = []
    for skript, (liest, _) in sorted(abhaengig.items()):
        if skript not in pos:
            continue
        for datei in liest:
            quelle = erzeuger.get(datei)
            if quelle and quelle != skript and pos[quelle] > pos[skript]:
                aus.append((skript, datei, quelle))
    return aus


def pruefe_deklaration(abhaengig=None, scripts=None):
    """Steht jeder deklarierte Pfad auch wirklich im Quelltext?

    Die Gegenprobe zur Tabelle. Sie fängt nicht jede vergessene Abhängigkeit —
    das könnte sie nur mit einem echten Lauf —, aber sie verhindert, dass die
    Deklaration und der Code auseinanderlaufen, ohne dass es jemand merkt.
    Genau diese Klasse (eine Regel, zwei Orte, einer veraltet) hat das Projekt
    schon mehrfach getroffen (#88).
    """
    abhaengig = ABHAENGIG if abhaengig is None else abhaengig
    scripts = Path(scripts or SCRIPTS)
    aus = []
    for skript, (liest, schreibt) in sorted(abhaengig.items()):
        pfad = scripts / skript
        if not pfad.exists():
            aus.append((skript, "", "Skript fehlt"))
            continue
        quelltext = pfad.read_text(encoding="utf-8")
        for datei in list(liest) + list(schreibt):
            # Verglichen wird über den Dateinamen, nicht den ganzen Pfad: die
            # Skripte bauen ihn aus ROOT / "processed" / "x.csv" zusammen.
            if Path(datei).name not in quelltext:
                aus.append((skript, datei, "im Quelltext nicht gefunden"))
    return aus


def main():
    if not WORKFLOW.exists():
        print(f"ERROR: {WORKFLOW} fehlt")
        return 2
    reihenfolge = schritte()
    print(f"Pipeline-Schritte: {len(reihenfolge)} · davon mit deklarierter "
          f"Abhängigkeit: {sum(1 for s in reihenfolge if s in ABHAENGIG)}")

    falsch = pruefe_deklaration()
    for skript, datei, grund in falsch:
        print(f"  ✗ {skript}: {datei} — {grund}")

    v = verletzungen(reihenfolge)
    for leser, datei, quelle in v:
        print(f"  ✗ {leser} liest {datei}, erzeugt von {quelle} — das läuft SPÄTER")

    if not falsch and not v:
        print("  ✓ Die Kette ist eine gültige Topologie: jedes gelesene "
              "Artefakt entsteht vorher.")
        # Ohne diese Zeile wäre „keine Verletzung" nicht von „nichts geprüft"
        # zu unterscheiden.
        kanten = sum(1 for s, (liest, _) in ABHAENGIG.items()
                     if s in reihenfolge for d in liest
                     if any(d in w for _, w in ABHAENGIG.values()))
        print(f"    geprüfte Abhängigkeiten: {kanten}")
    return 1 if (falsch or v) else 0


if __name__ == "__main__":
    sys.exit(main())
