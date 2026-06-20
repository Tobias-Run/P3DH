"""Phase 0 reconnaissance: render the EDAP Power BI embed headless and dump
structure so we can locate the submissions table + 'Report File' download.
Read-only: no clicks that submit anything; only navigation + screenshot + DOM dump.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://edap-public.eba.europa.eu/Report/index/MTE1"
OUT = Path(__file__).resolve().parent.parent / "interim" / "edap_recon"
OUT.mkdir(parents=True, exist_ok=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 1200},
                                   accept_downloads=True)
        page = ctx.new_page()
        page.set_default_timeout(60000)
        print("goto", URL)
        page.goto(URL, wait_until="domcontentloaded")
        print("landed url:", page.url)
        print("title:", page.title())

        # Power BI renders in an iframe to app.powerbi.com; give it time.
        page.wait_for_timeout(12000)

        frames = page.frames
        print(f"\n=== {len(frames)} frames ===")
        for f in frames:
            print(f"  frame: name={f.name!r} url={f.url[:90]}")

        page.screenshot(path=str(OUT / "landing.png"), full_page=True)
        print("screenshot ->", OUT / "landing.png")

        # Dump visible text from main page + each frame (trimmed).
        for i, f in enumerate(frames):
            try:
                txt = f.locator("body").inner_text(timeout=5000)
            except Exception as e:
                txt = f"<no text: {e}>"
            (OUT / f"frame_{i}_text.txt").write_text(txt[:8000], encoding="utf-8")
            print(f"  frame {i} text -> {len(txt)} chars")

    print("done")


if __name__ == "__main__":
    main()
