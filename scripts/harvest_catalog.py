"""DEPRECATED — do not use for new harvests.

This DOM-scroll approach only ever surfaces the ~20 rows Power BI renders in its
virtualised grid. Use `harvest_catalog_query.py` instead: it replays the Power BI
`query` endpoint with a raised DataReduction window and drains the COMPLETE catalog
(4,278 submissions / 489 institutions) in one request.

Kept only as reference for the Playwright navigation pattern.

Original: Phase 1 — harvest EDAP submissions catalog via Power BI table scroll."""

from pathlib import Path
from playwright.sync_api import sync_playwright
import csv
import time

URL = "https://edap-public.eba.europa.eu/Report/index/MTE1"
OUT = Path(__file__).resolve().parent.parent / "interim" / "edap_recon"
OUT.mkdir(parents=True, exist_ok=True)


def pbframe(page):
    """Get Power BI embedded iframe."""
    for f in page.frames:
        if "app.powerbi.com" in f.url:
            return f
    return None


def extract_urls_from_table(frame):
    """Extract all visible URLs from Power BI table via DOM inspection."""
    js = """() => {
      const urls = [];
      // Look for download links in the table
      document.querySelectorAll('a[href*="errp.eba.europa.eu"], [title*="errp.eba.europa.eu"]').forEach(el => {
        const href = el.getAttribute('href') || el.textContent;
        if (href && href.includes('errp.eba.europa.eu')) {
          urls.push(href.trim());
        }
      });
      // Also try data attributes / aria-label
      document.querySelectorAll('[aria-label*="http"], [title*="http"]').forEach(el => {
        const text = el.getAttribute('aria-label') || el.getAttribute('title');
        if (text && text.includes('errp.eba.europa.eu')) {
          urls.push(text.trim());
        }
      });
      return [...new Set(urls)];  // deduplicate
    }"""
    return frame.evaluate(js)


def scroll_table_and_harvest(frame, max_scrolls=100):
    """Scroll through virtualized table to load all rows, extract URLs."""
    all_urls = set()
    scroll_count = 0
    prev_count = 0

    print(f"Starting table scroll (max {max_scrolls} iterations)...")

    while scroll_count < max_scrolls:
        # Extract URLs from current view
        urls = extract_urls_from_table(frame)
        all_urls.update(urls)

        # Scroll down in the table
        frame.evaluate("""() => {
          const table = document.querySelector('[role="grid"], [role="table"], .powervisuals-visual');
          if (table) table.scrollTop = table.scrollHeight;
        }""")

        time.sleep(1)  # Wait for virtualization to load new rows
        scroll_count += 1

        # Check if we're getting new URLs
        new_count = len(all_urls)
        if new_count == prev_count and scroll_count > 5:
            print(f"  No new URLs after scroll {scroll_count} — likely reached end")
            break

        if scroll_count % 10 == 0:
            print(f"  Scroll {scroll_count}: {new_count} unique URLs so far")

        prev_count = new_count

    return sorted(list(all_urls))


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 1200},
                                  accept_downloads=True)
        page = ctx.new_page()
        page.set_default_timeout(60000)

        print("Loading EDAP...")
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(12000)

        f = pbframe(page)
        if not f:
            print("ERROR: Power BI frame not found")
            return

        print("Navigating to Submissions table...")
        try:
            f.get_by_role("link", name="Page navigation . Click here to follow").first.click(timeout=5000)
        except Exception as e:
            print(f"  Page nav click failed: {e}")
            try:
                f.locator("[aria-label*='Page navigation' i]").first.click(timeout=5000)
            except:
                print("  Could not navigate — proceeding anyway")

        page.wait_for_timeout(9000)
        f = pbframe(page)

        print("\nHarvesting catalog from virtualized table...")
        urls = scroll_table_and_harvest(f, max_scrolls=150)

        print(f"\nFound {len(urls)} unique URLs")

        # Save to CSV
        manifest_path = OUT / "manifest_urls.csv"
        with open(manifest_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["url", "lei", "consolidation", "country", "module",
                           "refdate", "submission_ts"])

            for url in urls:
                # Parse filename from URL
                if "errp.eba.europa.eu" in url:
                    parts = url.split("/")[-1].replace(".zip", "").split("_")
                    if len(parts) >= 6:
                        # parts[0] = LEI.CON|IND, parts[1] = Country, parts[2] = PILLAR3{module}, parts[3] = CODIS, parts[4] = refdate, parts[5] = timestamp
                        lei_consol = parts[0].split(".")
                        lei = lei_consol[0]
                        consolidation = lei_consol[1] if len(lei_consol) > 1 else ""
                        country = parts[1]
                        module = parts[2].replace("PILLAR3", "")
                        refdate = parts[4]
                        ts = parts[5]
                        writer.writerow([url, lei, consolidation, country, module, refdate, ts])

        print(f"✓ Manifest saved: {manifest_path}")

        browser.close()


if __name__ == "__main__":
    main()
