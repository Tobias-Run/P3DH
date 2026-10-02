"""Create a review ledger; judgments are manual, numerical evidence is retained."""
import collections,csv,json,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
findings=json.loads((ROOT/'findings.json').read_text())
mixed={
 ('5493008QRHH0XCLJ4238','61.00'):'Kapital und TREA sind plausibel; Liquiditäts-/Funding-Zeilen liegen etwa Faktor 1.000 unter Dezember. Warnung auf betroffene Zeilen begrenzen.',
 ('D1HEB8VEU6D9M8ZUXG17','71.00'):'Spalte 0010 ist plausibel; Dezember-Spalte 0020 enthält Millionenwerte. Beispiel r0560: 116.540 statt des Juni-Werts 116.540.317.600 EUR. Kein einheitlicher Template-Faktor.',
 ('DG3RU1DBUFHT4ZF9WN62','61.00'):'Kapital/TREA/Leverage sind in EUR plausibel. Liquiditäts-/Funding-Zeilen 0280–0340 enthalten Größen wie 103.493 HQLA und 469.754 ASF; Millionenhypothese. Der geschätzte Faktor 10^3 ist unpassend.',
 ('FR9695005MSX1OYEMGDF','27.02.A'):'Dezember enthält normale EUR-Werte und Millionenwerte nebeneinander: r0130 c0010 Gesamt-Exposure 634.778,85, während c0020 RWA 133.910.346.543,27 EUR. Keine uniforme Skalierung.',
 ('K8MS7FD7N5Z2WQ51AZ71','74.00.A'):'Ein Teil der Perioden/Datenpunkte enthält Beträge rund Faktor 1.000 kleiner; andere sind plausibel. Dieselbe sichtbare Koordinate enthält mehrere Datapoints mit unterschiedlicher Frequenz. Juni-Wert 61 Mio erscheint im Dezember als historischer Wert erneut. Zeit-/Periodenachsen müssen getrennt werden.',
 ('O2RNE8IBXP4R0TD8PU41','27.01'):'Vergleichszellen zeigen ein Gemisch normaler EUR-Werte und etwa Faktor 1.000 kleinerer Beträge. Warnung berechtigt für Teile, nicht als pauschaler Faktor.',
 ('O2RNE8IBXP4R0TD8PU41','27.02.A'):'Vergleichszellen zeigen normale EUR-Werte und ungefähr Faktor 1.000 kleinere Beträge. Zeilen/Spalten getrennt prüfen.',
 ('O2RNE8IBXP4R0TD8PU41','27.02.B'):'Vergleich enthält Cluster bei Faktoren 10^6 und 10^9. Der geschätzte Faktor 10^9 ist keine Korrekturvorgabe für das gesamte Template.',
 ('R0MUWSFPU8MPRO8K5P83','04.00.A'):'Unterschiedliche Teile liegen etwa Faktor 10^6 auseinander; zahlreiche andere Zellen bewegen sich normal. Kein einheitlicher Template-Faktor.',
}
special={
 ('K8MS7FD7N5Z2WQ51AZ71','83.01.C'):('nicht_gestuetzt','Kein Skalensprung in 15 direkt vergleichbaren Datenpunkten: Median 0,048 log10, alle innerhalb Faktor 2 um unveränderte Skala. Der Populationsversatz springt wegen veränderter Zellzusammensetzung; Juni ist nicht als skaliert belegt.'),
 ('KFUXYFTU2LHQFQZDQG45','41.00'):('falsche_richtung','Dezember-Exposure r0010 c0010 ist 3,273 Mrd EUR; Juni enthält 3,117 Billiarden EUR, bei Juni-TREA 7,592 Mrd EUR. Juni ist etwa 10^6 zu groß; Dezember nicht pauschal hochskalieren. Template ist zusätzlich unit_ambiguous.'),
 ('N1FBEDJ5J41VKZLO2475','68.00'):('falsche_richtung','Juni meldet EVE-Verlust Parallel-up von -121,994 Mrd EUR, Dezember -113,082 Mio EUR und als Vorperiode -121,994 Mio EUR. Gleicher historischer Wert zeigt Juni-Faktor 1.000 zu groß. Dezember ist plausibel; Warnung gehört zu Juni.'),
 ('KR6LSKV3BTSJRD41IF75','29.02.A'):('offen','Acht direkt vergleichbare positive Werte sind feste Risikogewichte (z.B. 0,5), im Datensatz als monetary geführt und mit CZK/EUR umgerechnet. Die monetären Exposures wechseln Datapoints/Zellbelegung. Ein Skalenproblem ist möglich, aber der pauschale Faktor 10^3 ist damit nicht belegt. Datentyp und Perioden-/Versionszuordnung zuerst klären.'),
}
rows=[]
for f in findings:
 if f['ebene']=='report':
  if f['urteil']=='skaliert':
   status='warnung_plausibel';reason='Sehr kleine absolute Beträge/TREA und passende weitere Indizien; kein Gegenbeleg gegen die Warnung gefunden. Reportwarnung bedeutet überwiegend problematische absolute Beträge, nicht jede Zelle und kein sicherer einheitlicher Korrekturfaktor.'
   if not f['trea_eur']:reason='Kein TREA gemeldet; extrem kleiner monetärer Report-Rumpf. Warnung plausibel, aber kein formaler Einheiten-/Faktorbeweis allein aus Populationsversatz.'
  elif f['lei'] in {'5299000F1CGJQ8NAXQ58','815600B43BECA3919584'}:
   status='kleine_bank_kein_nachweis';reason='Kapital im zweistelligen Millionenbereich und TREA rund 18 Mio EUR sind für ein kleines Institut plausibel. Populationsversatz allein belegt keinen Skalendefekt; keine automatische Hochskalierung um 1.000.'
  else:
   status='verdacht_bleibt';reason='Tausender-Hypothese bleibt plausibel, ist aber ohne belastbaren Referenzbetrag nicht bestätigt. Konstante Skalierung über alle eigenen Stichtage widerlegt sie nicht. Warnung als Verdacht erhalten, nicht als sicheren Fehler ausgeben.'
   if f['lei']=='5493000UPYR7EEHN2R94':reason+=' Gorenjska enthält auch Milliardenzellen: möglicher Teilfehler, kein uniformer Reportfaktor.'
 else:
  key=f['lei'],f['template_id']
  if key in special:status,reason=special[key]
  elif key in mixed:status='teilfehler';reason=mixed[key]
  else:
   status='gut_gestuetzt';reason='Direkter Vergleich gleicher Datapoints stützt den starken Einheitenbruch. Faktor bleibt Hypothese; fachlich zugehörige Referenzbeträge und Teilzellen beachten.'
   if key==('213800DBQIB6VBNU5C64','23.00'):reason='Original EBA-CSV unverändert übernommen: 15/15 positiven Vergleichszellen nahe Faktor 10^6, Juni-KM1-TREA 30,604 Mrd EUR plausibel. Sehr starke Evidenz für in Millionen gemeinte Juni-CR3-Beträge.'
   if key==('969500CJCTMI93QJKK89','61.00'):reason='KM1-CET1 540,72 und TREA 2.998,88 EUR, sonstiger monetärer Report-Rumpf in normaler EUR-Größenordnung. Isolierte KM1-Warnung plausibel; kein zweiter eigener KM1-Stichtag.'
   if key==('213800A1O379I6DMCU10','25.00'):reason='Risikogewichts-/Portfolio-Aufteilung verändert sich stark; einzelne Zellen sind schlechte Zeitreihenanker. Gesamtsumme 4.755.060 gegenüber KM1-Leverage 4.755.060.268,29 EUR stützt Tausenderhypothese. Faktor nicht auf jede Zelle blind anwenden.'
   if f['bank_name']=='Banca Transilvania':reason+=' September ist der bessere Referenzstichtag; Dezember enthält möglicherweise weitere Teilfehler.'
 comparisons=f['comparisons'] if f['ebene']=='template' else []
 ev='; '.join(f"{x['date']}: n={x['matched_cells']}, log10(ref/current)={x['log_ratio']:.3f}, q10={x['q10']:.3f}, q90={x['q90']:.3f}" for x in comparisons)
 rows.append({'ebene':f['ebene'],'lei':f['lei'],'scope':f['scope'],'bank_name':f['bank_name'],'refPeriod':f['refPeriod'],'template_id':f['template_id'],'original_urteil':f['urteil'],'review_status':status,'reason':reason,'trea_eur':f['trea_eur'],'original_faktor_geschaetzt':f['faktor_geschaetzt'],'original_versatz_log10':f['versatz_log10'],'direct_comparisons':ev,'source_urls':' | '.join(f['source_urls'])})
with (ROOT/'review_119_findings.csv').open('w',newline='',encoding='utf-8-sig') as fh:
 w=csv.DictWriter(fh,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
counts=collections.Counter(r['review_status'] for r in rows)
(ROOT/'review_summary.json').write_text(json.dumps({'rows':len(rows),'statuses':dict(counts)},indent=2,ensure_ascii=False)+'\n')
print(counts)
