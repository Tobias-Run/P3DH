"""Phase 0 recon step 2: drive the Power BI canvas to the submissions screen,
screenshot each stage, dump interactive elements (aria/role/title)."""
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://edap-public.eba.europa.eu/Report/index/MTE1"
OUT = Path(__file__).resolve().parent.parent / "interim" / "edap_recon"
OUT.mkdir(parents=True, exist_ok=True)


def pbframe(page):
    for f in page.frames:
        if "app.powerbi.com" in f.url:
            return f
    return None


def dump_interactive(frame, tag):
    js = """() => {
      const out = [];
      const sel = '[role], [aria-label], button, a[href], [title], .slicer-restatement, .cell-interactive';
      document.querySelectorAll(sel).forEach(e => {
        const r = e.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) return;
        const lbl = e.getAttribute('aria-label') || e.getAttribute('title') || (e.innerText||'').trim().slice(0,60);
        if (!lbl) return;
        out.push({role: e.getAttribute('role')||e.tagName.toLowerCase(),
                  label: lbl, x: Math.round(r.x), y: Math.round(r.y)});
      });
      return out;
    }"""
    items = frame.evaluate(js)
    lines = [f"{it['role']:14} ({it['x']:4},{it['y']:4})  {it['label']}" for it in items]
    (OUT / f"interactive_{tag}.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"  [{tag}] {len(items)} interactive elements -> interactive_{tag}.txt")
    return items


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 1200},
                                  accept_downloads=True)
        page = ctx.new_page()
        page.set_default_timeout(60000)
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(12000)
        f = pbframe(page)
        print("pb frame:", bool(f))
        dump_interactive(f, "01_landing")

        # "Go to report" is the navigation arrow = link 'Page navigation'.
        clicked = False
        try:
            f.get_by_role("link", name="Page navigation . Click here to follow").first.click(timeout=5000)
            clicked = True; print("clicked Page navigation")
        except Exception as e:
            print("  page-nav miss", str(e)[:80])
            try:
                f.locator("[aria-label*='Page navigation' i]").first.click(timeout=5000)
                clicked = True; print("clicked via aria Page navigation")
            except Exception as e2:
                print("  aria miss", str(e2)[:80])

        page.wait_for_timeout(9000)
        page.screenshot(path=str(OUT / "02_submissions.png"), full_page=True)
        f = pbframe(page)
        dump_interactive(f, "02_submissions")
        print("done; clicked=", clicked)


if __name__ == "__main__":
    main()
