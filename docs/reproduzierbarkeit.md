# Warum die Pipeline dreimal nicht reproduzierbar war

Dieselbe Fehlerklasse hat innerhalb weniger Tage dreimal zugeschlagen. Jedes Mal
wurde sie **nachträglich und beiläufig** entdeckt, jedes Mal repariert, indem
eine Spalte mehr an den `ORDER BY` gehängt wurde, bis der Churn verschwand.
Das ist Symptombehandlung: sie sagt nicht, wann man fertig ist.

Dieses Dokument hält fest, was die Ursache war, warum die vorhandenen
Schutzmechanismen sie nicht fangen konnten, und was jetzt an ihrer Stelle steht.

## Das Fehlerbild

Eine Ausgabe ändert sich zwischen zwei Läufen auf **unveränderten Eingaben** —
ohne dass irgendetwas fehlschlägt. Kein Stacktrace, kein roter Test, keine
Warnung. Nur andere Bytes.

Belegt (DuckDB 1.5.5, 4 Threads):

```
Sortierung nach unvollständigem Schlüssel : 4 Läufe -> 4 verschiedene Reihenfolgen
Sortierung nach vollständigem  Schlüssel  : 4 Läufe -> 1 Reihenfolge
```

DuckDB sortiert parallel. Zeilen, die sich auf allen Sortierspalten gleichen,
kommen in beliebiger Reihenfolge zurück, und diese Reihenfolge wechselt.

## Die vier Ursachen

### U1 — Die Invariante war nirgends formuliert

Es gab keine Regel, gegen die man hätte prüfen können. Die naheliegende
Formulierung — *„der Sortierschlüssel muss eindeutig sein"* — ist zu stark und
zugleich nutzlos teuer: im Shard-Build gibt es 3.695 Tie-Gruppen, die man nie
alle auflösen kann.

Die richtige Regel ist präziser:

> **Jedes Feld, das in die Ausgabe fließt, muss im Sortierschlüssel stehen.**

Dann sind zwei Zeilen einer Tie-Gruppe *in der Ausgabe ununterscheidbar* und
ihre Vertauschung ist folgenlos. Ties sind erlaubt — der Schlüssel muss nur
alles abdecken, was sichtbar wird. Das ist prüfbar und hat einen definierten
Endzustand.

### U2 — Der Nichtdeterminismus war unbeobachtbar

Er hat kein Fehlerbild. Im Shard-Build sah er aus wie *„830 von 882 Shards
geschrieben"* — nach einem Delta-Load das völlig erwartete Ergebnis. Der einzige
Detektor war der `written/skipped`-Zähler, und der wurde beiläufig gelesen.

`check_plausibility.py` hat gar keinen solchen Zähler. Dort lief der Fehler
**seit Issue #17 unbemerkt**: `interim/plausibility_findings.csv` war zwischen
zwei Läufen inhaltlich identisch, aber anders sortiert — 97 % der Zeilen teilen
sich ihren Sortierwert (754 verschiedene `deviation_orders` auf 5.969 Zeilen,
größte Gruppe 150).

### U3 — Die Tests waren strukturell blind

Alle 107 Tests prüften **reine Funktionen** (`collapse_cells`,
`resolve_coverage`, `base_tid`, `latest_wins`). Die sind deterministisch per
Konstruktion. Der Nichtdeterminismus lebt exakt an der Naht **SQL → Python**,
die kein Test berührte.

Das ist die unbequemste Erkenntnis: *mehr Tests derselben Art hätten nicht
geholfen.* Es brauchte eine andere **Art** von Test — einen, der eine
Eigenschaft des Laufs prüft statt eines Rückgabewerts.

### U4 — Die Kosten fielen woanders an

Eine frühere Fassung des Code-Kommentars begründete den Fix damit, der Churn
blähe den `data`-Branch auf. **Das stimmt nicht** — der wird als frisches
Orphan-Commit ohne Historie force-gepusht, dort ist Churn folgenlos. Der echte
Schaden ist:

1. **Diagnostik.** Bei 830 von 882 geschriebenen Shards erkennt niemand mehr,
   ob wirklich neue Daten da sind. Das Signal ist zerstört.
2. **Historie.** `processed/quality_profile.csv` und die beiden
   `interim/plausibility_*.csv` werden von der Pipeline nach `main` committet.
   Dort landet der Churn dauerhaft in der Historie.
3. **Der Anspruch selbst.** Arbeitsprinzip 1 heißt „Reproduzierbarkeit". Eine
   Pipeline, die auf gleichen Eingaben verschiedene Bytes liefert, kann man
   gegen nichts prüfen — es gibt keine Referenz.

## Was jetzt an ihrer Stelle steht

### 1. Ein Guard im Ausführungspfad (`scripts/determinism.py`)

`ordered_query(con, sql, what)` führt eine Query nur aus, wenn ihre
Zeilenreihenfolge zugesichert ist. Wer eine Spalte in die Projektion aufnimmt
und die Sortierung nicht nachzieht, bekommt einen **harten Abbruch** statt einer
stillen Lücke.

Er prüft mehr als die reine Spaltenliste:

| geprüft | warum |
|---|---|
| Projektionsspalte fehlt im `ORDER BY` | die Kernregel |
| `GROUP BY`-Schlüssel nicht sortiert | dieselbe Regel eine Ebene höher |
| `any_value()`, `first()`, `arbitrary()` | greifen ein *beliebiges* Element |
| `list()`, `string_agg()` ohne eigenes `ORDER BY` | erben die Zufallsordnung |
| `UNION`/`INTERSECT`, unerkannte Formen | **abgelehnt**, nicht durchgewunken |

Der letzte Punkt ist Absicht: der Guard ist ein Textcheck, kein SQL-Parser. Was
er nicht sicher beurteilen kann, lehnt er ab — ein Guard, der im Zweifel „ok"
sagt, ist schlimmer als keiner.

### 2. Ein Doppellauf mit variiertem `PYTHONHASHSEED`

Der Guard sieht nur SQL. Die Python-Seite — Iteration über `set()` und `dict` —
deckt `tests/test_determinism.py` ab: derselbe Build zweimal auf Mini-Daten,
mit **verschiedenem Hash-Seed**, Bytes verglichen. Die Seed-Variation macht die
Klasse *zuverlässig* sichtbar, statt darauf zu hoffen, dass zwei zufällige
Läufe zufällig auseinanderlaufen.

### 3. Die Fixture enthält die Fallen — nachgewiesen

Beim Bau dieses Tests bin ich in genau die Falle getappt, vor der er warnt: die
erste Fassung der Fixture hatte **ein** Template und keine Filing-Indicators,
also gab es gar keine Set-Iteration zu variieren — und der Test blieb grün,
obwohl der Fehler zurück war.

Deshalb wurde jede Gegenmaßnahme **durch Mutation geprüft**: den Fix rückgängig
machen und nachsehen, ob der Test rot wird.

| Mutation | erwartet | Ergebnis |
|---|---|---|
| `sort_keys=True` entfernt | Test rot | ✓ rot (erst nach Fixture-Korrektur) |
| `ORDER BY` verkürzt | Test rot | ✓ rot |
| `any_value()` zurück | Lauf bricht ab | ✓ Abbruch |

Ein Test, der nur grün ist, weil er den Fall nicht enthält, ist schlimmer als
keiner — er erzeugt Vertrauen ohne Deckung.

## Was der Fix zusätzlich freigelegt hat

Determinismus herzustellen zwingt dazu, jede willkürliche Auswahl zu benennen.
Drei davon sind **inhaltliche** Probleme, die vorher unter der Zufallsordnung
verborgen lagen:

- **12 Reports tragen zwei Währungen.** `baseCurrency` im Index wird aus der
  ersten Zeile gezogen. Jetzt deterministisch — aber immer noch willkürlich.
- **10 Zellkoordinaten tragen mehrere Labels.** Bei OV1 (`60.00.A`) r0120/c0020
  liegen „9. Of which other CCR" und „10. CVA risk" auf derselben Koordinate,
  und zwar in *beiden* Framework-Versionen. Das ist kein 4.1/4.2-Bruch, sondern
  eine mehrdeutige Platzierung — und OV1 ist ein Benchmark-Template.
- **Mehrfach belegte Zellkoordinaten** — das war bereits #52.

Alle drei sind dieselbe Klasse: *unsere Darstellung ist enger als die Daten.*
Determinismus macht daraus aus einem unsichtbaren ein sichtbares Problem, löst
es aber nicht.

## Regel für künftige Änderungen

Jede Änderung an einer Query, deren Ergebnis in eine Datei fließt, ist erst
fertig, wenn sie durch `ordered_query()` läuft. Jede Änderung an der Struktur
einer Ausgabe braucht den Doppellauf als Teil der Verifikation — nicht als
nachgelagerte Kontrolle.
