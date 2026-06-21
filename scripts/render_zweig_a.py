"""Zweig A: render the long-form tidy data back into human-readable EBA template grids.

Reads:
    processed/long_form_raw.csv   (entity x refPeriod x template x cell -> value)
    codebook/dpm_codebook.csv     (template,row,col -> title, row_label, col_label)

Writes one self-contained HTML file per report into processed/zweig_a/ plus an index.
"""

from pathlib import Path
from collections import defaultdict
from html import escape
import csv
import re

ROOT = Path(__file__).resolve().parent.parent
LONGFORM = ROOT / "processed" / "long_form_raw.csv"
CODEBOOK = ROOT / "codebook" / "dpm_codebook.csv"
OUTDIR = ROOT / "processed" / "zweig_a"


def load_codebook():
    """(template, row, col) -> dict; template uses DPM form 'K_61.00'."""
    cb = {}
    titles = {}
    with open(CODEBOOK, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["row"]:
                continue
            cb[(r["template"], r["row"], r["col"])] = (r["row_label"], r["col_label"])
            if r["template_title"]:
                titles[r["template"]] = r["template_title"]
    return cb, titles


def dpm_template_code(template_id: str) -> str:
    """long-form '60.00.A' -> DPM codebook key 'K_60.00.a'."""
    parts = template_id.split(".")
    if parts and re.fullmatch(r"[A-Z]", parts[-1]):
        parts[-1] = parts[-1].lower()
    return "K_" + ".".join(parts)


def fmt(value: str) -> str:
    try:
        n = float(value)
    except (ValueError, TypeError):
        return escape(str(value))
    if n == int(n):
        return f"{int(n):,}".replace(",", " ")
    return f"{n:,.2f}".replace(",", " ")


def render_template(tmpl_id, cells, cb, titles):
    """cells: list of (row, col, value). Returns HTML for one template grid."""
    tcode = dpm_template_code(tmpl_id)
    title = titles.get(tcode, "")
    rows = sorted({c[0] for c in cells})
    cols = sorted({c[1] for c in cells})
    val = {(r, c): v for r, c, v in cells}

    row_lbl = {r: cb.get((tcode, r, cols[0]), ("", ""))[0] for r in rows}
    # column label: take from any cell present in that column
    col_lbl = {}
    for c in cols:
        for r in rows:
            if (tcode, r, c) in cb:
                col_lbl[c] = cb[(tcode, r, c)][1]
                break
        col_lbl.setdefault(c, "")

    h = [f'<section><h2>{escape(tmpl_id)} &mdash; {escape(title) or "?"}</h2>',
         '<table><thead><tr><th class="rh">Row</th><th class="rl"></th>']
    for c in cols:
        h.append(f'<th>{escape(c)}<br><span class="cl">{escape(col_lbl[c])}</span></th>')
    h.append("</tr></thead><tbody>")
    for r in rows:
        h.append(f'<tr><th class="rh">{escape(r)}</th><td class="rl">{escape(row_lbl[r])}</td>')
        for c in cols:
            v = val.get((r, c))
            h.append(f'<td class="num">{fmt(v)}</td>' if v is not None else '<td class="empty"></td>')
        h.append("</tr>")
    h.append("</tbody></table></section>")
    return "\n".join(h)


CSS = """
body{font:13px/1.4 -apple-system,Segoe UI,Roboto,sans-serif;margin:2rem;color:#1a1a1a;background:#fafafa}
h1{font-size:1.4rem}h2{font-size:1rem;margin:1.5rem 0 .4rem;color:#0b3d91}
.meta{color:#555;margin-bottom:1rem}
table{border-collapse:collapse;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.08);margin-bottom:1rem}
th,td{border:1px solid #e2e2e2;padding:3px 7px;vertical-align:top}
thead th{background:#0b3d91;color:#fff;font-weight:600;text-align:left;font-size:11px}
.rh{background:#f0f3fa;color:#0b3d91;font-weight:600;text-align:center;width:48px}
.rl{max-width:320px;font-size:12px}
.cl{font-weight:400;opacity:.85;font-size:10px}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.empty{background:#f7f7f7}
a{color:#0b3d91}
"""


def main():
    cb, titles = load_codebook()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    # group: report -> template -> [(row,col,value)]
    reports = defaultdict(lambda: defaultdict(list))
    meta = {}
    with open(LONGFORM, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["cell_row"]:
                continue
            key = (r["entityID"], r["refPeriod"])
            reports[key][r["template_id"]].append((r["cell_row"], r["cell_col"], r["fact_value"]))
            meta[key] = (r["baseCurrency"], r["framework_version"])

    index = ['<!doctype html><meta charset="utf-8"><title>Zweig A &mdash; P3DH</title>',
             f"<style>{CSS}</style>", "<h1>Zweig A &mdash; Pillar 3 Template Reconstruction</h1>",
             f'<p class="meta">{len(reports)} reports</p><ul>']

    for i, (key, tmpls) in enumerate(sorted(reports.items()), 1):
        entity, refp = key
        cur, fw = meta[key]
        eid = re.sub(r"[^A-Za-z0-9]", "_", entity)[:30]
        fname = f"{i:02d}_{eid}_{refp}.html"
        body = [f'<!doctype html><meta charset="utf-8"><title>{escape(entity)} {refp}</title>',
                f"<style>{CSS}</style>",
                f'<h1>{escape(entity)}</h1>',
                f'<p class="meta">Reference date <b>{refp}</b> &middot; Currency <b>{escape(cur)}</b>'
                f' &middot; Framework <b>{escape(fw)}</b> &middot; values in units of base currency</p>',
                '<p class="meta"><a href="index.html">&larr; all reports</a></p>']
        for tmpl_id in sorted(tmpls):
            body.append(render_template(tmpl_id, tmpls[tmpl_id], cb, titles))
        (OUTDIR / fname).write_text("\n".join(body), encoding="utf-8")
        index.append(f'<li><a href="{fname}">{escape(entity)}</a> &middot; {refp} '
                     f'&middot; {escape(cur)} &middot; {len(tmpls)} templates</li>')

    index.append("</ul>")
    (OUTDIR / "index.html").write_text("\n".join(index), encoding="utf-8")
    print(f"✓ Zweig A: {OUTDIR}/index.html  ({len(reports)} reports)")


if __name__ == "__main__":
    main()
