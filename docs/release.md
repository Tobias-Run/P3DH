# Ein Release herausgeben

Was released wird, ist **zweierlei mit unterschiedlichem Status**:

| | Was | DOI |
|---|---|---|
| **Software** | Die Pipeline, der Viewer, die Doku — unstrittig unsere Leistung | ✅ Zenodo |
| **Datensatz** | `p3dh_long.parquet` — inhaltlich EBA-Material, von uns umgeformt | ❌ bewusst nicht |

Der Datensatz bekommt **keinen DOI**. `DISCLAIMER.md` verspricht Rechteinhabern
eine zügige Entfernung auf Zuruf; ein Zenodo-DOI ist bewusst nicht rücknehmbar
(ein zurückgezogener Record hinterlässt einen Tombstone, der DOI bleibt). Ein
Versprechen zu geben, das man technisch nicht halten kann, ist schlechter als
keines. Er geht deshalb als **Release-Asset** heraus: dauerhaft adressierbar,
aber entfernbar.

Sollte später ein Paper einen fixierten Stand zitieren müssen, wird *jener*
Schnappschuss mit dem Paper geminzt — mit Anlass und geprüfter Fehlerlage.

## Einmalig: Zenodo einrichten

Diese vier Schritte kann nur der Repository-Eigentümer gehen; sie brauchen eine
Anmeldung.

1. Auf **https://zenodo.org** mit dem GitHub-Konto anmelden.
2. **Settings → GitHub** öffnen und die Repository-Liste synchronisieren.
3. Den Schalter für **`Tobias-Run/P3DH`** auf **On** stellen.
4. Fertig. Ab jetzt greift Zenodo **jedes künftige GitHub-Release** ab und vergibt
   einen DOI. Für Releases, die vor dem Einschalten entstanden sind, tut es das
   nicht — der Schalter muss also **vor** dem ersten Release stehen.

`.zenodo.json` im Repo-Root steuert dabei Titel, Beschreibung, Lizenz und
Schlagworte; ohne die Datei würde Zenodo aus dem Repo raten.

Zenodo vergibt zwei DOIs: einen **Concept-DOI**, der immer auf die neueste Version
zeigt, und je Release einen **Versions-DOI**. In Texten über das Projekt gehört der
Concept-DOI, in einer Zitation eines konkreten Standes der Versions-DOI.

Nach dem ersten Release: den Concept-DOI in `CITATION.cff` als `doi:` nachtragen
und als Badge in den README — dann zeigt GitHubs „Cite this repository" den
vollständigen Eintrag.

## Je Release

### 1. Stand herstellen

Ein grüner Pipeline-Lauf muss das Release tragen — nicht ein Bestand von vorletzter
Woche. `manifest.json` hält fest, welcher Commit ihn erzeugt hat.

```
Actions → P3DH pipeline → Run workflow
```

Wenn `codebook/dpm_codebook.csv` seit dem letzten Lauf geändert wurde, entscheidet
die Pipeline den vollen Reparse selbst (Fingerabdruck, #57) — der Schalter
`full_reparse` ist dann nur noch die Abkürzung.

### 2. Zahlen aus dem Manifest ziehen

Nicht aus dem README abschreiben, nicht schätzen:

```bash
curl -s https://cdn.jsdelivr.net/gh/Tobias-Run/P3DH@data/state/manifest.json \
  | python3 -m json.tool
```

`coverage` und `breakdown` sind die Release-Beschreibung. `generator.commit` sagt,
worauf der Tag zeigen muss.

### 3. Asset sichern

Der `data`-Branch wird beim nächsten Lauf force-überschrieben. Was ins Release
soll, muss **vorher** heruntergeladen und angehängt werden:

```bash
BASE=https://cdn.jsdelivr.net/gh/Tobias-Run/P3DH@data/state
curl -sO $BASE/p3dh_long.parquet
curl -sO $BASE/manifest.json
```

### 4. Taggen und veröffentlichen

Version nach [SemVer](https://semver.org/lang/de/), `v0.x` solange sich das Schema
noch ändern darf. Ein Schema-Bruch (Spalte entfernt oder umbenannt) ist ein
Major-Sprung — nachgelagerte Auswertungen hängen daran.

```bash
git tag -a v0.1.0 -m "Erstes dokumentiertes Release"
git push origin v0.1.0
```

Dann auf GitHub das Release aus dem Tag erzeugen, `p3dh_long.parquet` und
`manifest.json` anhängen, und in den Text mindestens aufnehmen:

- die Kennzahlen aus `manifest.json`
- den Hinweis, dass die Offenlegungsdaten von der EBA stammen und **gesondert zu
  zitieren** sind
- einen Verweis auf `docs/datensatz.md` für Schema und Einschränkungen

### 5. Nachtragen

Nach dem ersten Release den DOI in `CITATION.cff` und README eintragen.

> **Erledigt seit v0.1.1.** Concept-DOI: `10.5281/zenodo.22666716`. Er steht in
> `CITATION.cff` (Feld `doi`) und als Badge im README und muss nicht erneut
> geändert werden — er löst von sich aus auf die jeweils neueste Fassung auf.
> Zu pflegen bleiben je Release nur `version` und `date-released` in
> `CITATION.cff`.

> **Zur Schreibweise der Tags:** veröffentlicht sind `v.0.1.0` und `v.0.1.1` —
> mit Punkt nach dem `v`. Das weicht von der oben genannten Form ab. Die Tags
> bleiben, wie sie sind: Zenodo hat gegen sie DOIs vergeben, und ein Umbenennen
> änderte daran nichts, sondern machte die Archiveinträge nur unauffindbar.

## Was ein Release blockiert

| Prüfung | Warum |
|---|---|
| Pipeline-Lauf grün | Parität, Placement- und Referenzdaten-Guard tragen die Zusagen des Datensatzes |
| `manifest.json` vorhanden | ohne Herkunftsnachweis ist der Bestand nicht identifizierbar |
| `LICENSE`, `DISCLAIMER.md`, `CITATION.cff` aktuell | die Abgrenzung Code ↔ Daten muss stimmen |
| `docs/datensatz.md` deckt das Schema | ein Test prüft, dass jede Parquet-Spalte dokumentiert ist |

Ausdrücklich **kein** Blocker: der wöchentliche Cron (#8). Ihn vor der
Versionierung scharf zu schalten hieße, dass sich „das Release" unter den Nutzern
verändert. Erst Releases, dann Automatik.
