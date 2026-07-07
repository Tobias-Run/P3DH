"""Phase 1 (robust): harvest the COMPLETE EDAP Pillar 3 catalog via the Power BI
`query` endpoint instead of scrolling the virtualised grid.

How: render the embed once (Playwright) to capture the live submissions-table query
(endpoint + auth headers + SemanticQuery body, whose DataReduction window is Count=500),
then replay that POST in the same session with DSR RestartToken pagination until the
whole table is drained. Each page's `errp…zip` URLs are regex-extracted (slashes are
\\u002f-escaped in the DSR JSON) and the filename yields the manifest metadata.

Output: interim/edap_recon/manifest_full.csv  (same schema as harvest_catalog.py).
"""

from pathlib import Path
import re
import json
import csv
from playwright.sync_api import sync_playwright

URL = "https://edap-public.eba.europa.eu/Report/index/MTE1"
OUT = Path(__file__).resolve().parent.parent / "interim" / "edap_recon"
ZIP_RE = re.compile(r"https://errp\.eba\.europa\.eu/[^\s\"'\\]+?\.zip")
MAX_PAGES = 200


def pbframe(page):
    for f in page.frames:
        if "app.powerbi.com" in f.url:
            return f
    return None


def find_window(body_obj):
    """Locate the submissions-table command's DataReduction window dict (mutable)."""
    for q in body_obj.get("queries", []):
        for c in q.get("Query", {}).get("Commands", []):
            sq = c.get("SemanticQueryDataShapeCommand")
            if not sq:
                continue
            sel = sq["Query"].get("Select", [])
            if any(s.get("Column", {}).get("Property") == "Report File Link" for s in sel):
                return sq["Binding"]["DataReduction"]["Primary"].setdefault("Window", {"Count": 500})
    return None


def restart_token(resp_json):
    """Pull the DSR restart token from a query response, or None when drained."""
    try:
        ds = resp_json["results"][0]["result"]["data"]["dsr"]["DS"][0]
    except (KeyError, IndexError):
        return None
    return ds.get("RT")


def main():
    capture = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1700, "height": 1300})
        page = ctx.new_page()
        page.set_default_timeout(60000)

        def on_request(req):
            if "/public/query" in req.url and req.method == "POST" and not capture:
                body = req.post_data or ""
                if '"Property":"Report File Link"' in body:
                    capture["url"] = req.url
                    capture["headers"] = dict(req.headers)
                    capture["body"] = body

        page.on("request", on_request)
        print("Rendering embed to capture the live query...")
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(12000)
        f = pbframe(page)
        try:
            f.get_by_role("link", name="Page navigation . Click here to follow").first.click(timeout=5000)
        except Exception:
            pass
        page.wait_for_timeout(10000)
        if not capture:
            print("ERROR: table query not captured")
            return

        # Replay with RestartToken pagination, reusing the live session (context.request).
        headers = {k: v for k, v in capture["headers"].items()
                   if k.lower() not in ("content-length", "host", "accept-encoding")}
        body_obj = json.loads(capture["body"])
        window = find_window(body_obj)
        if window is not None:
            window["Count"] = 30000  # raise the page window; drain in one shot if allowed
        urls = set()
        print("Draining catalog via query (window=30000)...")
        for pageno in range(1, MAX_PAGES + 1):
            resp = ctx.request.post(capture["url"], headers=headers, data=json.dumps(body_obj))
            if not resp.ok:
                print(f"  page {pageno}: HTTP {resp.status} — stop")
                break
            text = resp.text()
            found = ZIP_RE.findall(text.replace("\\u002f", "/").replace("\\/", "/"))
            before = len(urls)
            urls.update(found)
            rj = json.loads(text)
            rt = restart_token(rj)
            print(f"  page {pageno}: +{len(urls)-before} urls (total {len(urls)})  restart={'yes' if rt else 'no'}")
            if pageno == 1 and rt:
                print("  RT format:", json.dumps(rt)[:200])
            if not rt or len(urls) == before or window is None:
                break
            window["Count"] = 500
            window["RestartTokens"] = [rt]
        browser.close()

    # Build manifest from filenames
    rows = []
    leis = set()
    for u in sorted(urls):
        fn = u.split("/")[-1].replace(".zip", "")
        parts = fn.split("_")
        if len(parts) < 6:
            continue
        lei_con = parts[0].split(".")
        lei = lei_con[0]
        leis.add(lei)
        rows.append({
            "url": u, "lei": lei,
            "consolidation": lei_con[1] if len(lei_con) > 1 else "",
            "country": parts[1], "module": parts[2].replace("PILLAR3", ""),
            "refdate": parts[4], "submission_ts": parts[5],
        })

    out = OUT / "manifest_full.csv"

    # Delta against the previous harvest: what is new, what disappeared.
    prev_urls = set()
    if out.exists():
        with open(out, encoding="utf-8") as fh:
            prev_urls = {r["url"] for r in csv.DictReader(fh)}
    new_urls = {r["url"] for r in rows} - prev_urls
    gone_urls = prev_urls - {r["url"] for r in rows}

    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["url", "lei", "consolidation", "country", "module", "refdate", "submission_ts"])
        w.writeheader()
        w.writerows(rows)

    # Append-only harvest log + delta file for downstream incremental steps.
    from datetime import datetime, timezone
    ts_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log = OUT / "harvest_log.csv"
    new_file = not log.exists()
    with open(log, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["harvested_at", "total", "institutions", "new", "gone"])
        if new_file:
            w.writeheader()
        w.writerow({"harvested_at": ts_now, "total": len(rows), "institutions": len(leis),
                    "new": len(new_urls), "gone": len(gone_urls)})
    delta = OUT / "manifest_delta.csv"
    with open(delta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["change", "url"])
        w.writeheader()
        for u in sorted(new_urls):
            w.writerow({"change": "new", "url": u})
        for u in sorted(gone_urls):
            w.writerow({"change": "gone", "url": u})

    print(f"\n✓ {out}")
    print(f"  Submissions: {len(rows)}  ·  Institutionen (LEI): {len(leis)}")
    print(f"  Delta seit letztem Harvest: +{len(new_urls)} neu, -{len(gone_urls)} verschwunden")
    print(f"  Log: {log.name} · Delta: {delta.name}")


if __name__ == "__main__":
    main()
