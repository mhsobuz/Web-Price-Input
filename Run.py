import asyncio
import csv
import random
import os
from datetime import datetime
from playwright.async_api import async_playwright

# CSS selector for price
PRICE_SELECTOR = "div.cat-price"

# Folder for error screenshots
ERROR_FOLDER = "screenshots"
os.makedirs(ERROR_FOLDER, exist_ok=True)

async def scrape_product(semaphore, context, sku, url):
    async with semaphore:
        page = await context.new_page()
        try:
            # Load page fully
            await page.goto(url, wait_until="networkidle", timeout=60000)
            # Wait for the price element
            await page.wait_for_selector(PRICE_SELECTOR, timeout=30000)
            # Extract the price
            price_text = await page.locator(PRICE_SELECTOR).first.inner_text()
            price_number = price_text.replace("$", "").strip()
            print(sku, price_number)
            return sku, price_number, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            # On error, take screenshot
            screenshot_path = os.path.join(ERROR_FOLDER, f"{sku}.png")
            await page.screenshot(path=screenshot_path)
            print(f"Failed {sku}: {e} (screenshot saved)")
            return sku, "ERROR", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        finally:
            await page.close()

async def main():
    semaphore = asyncio.Semaphore(8)  # number of concurrent pages
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False for debugging
        context = await browser.new_context()

        # Load CSV with SKUs and URLs
        tasks = []
        with open("products.csv") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tasks.append(scrape_product(semaphore, context, row["sku"], row["url"]))

        # Run tasks asynchronously
        for task in asyncio.as_completed(tasks):
            results.append(await task)
            await asyncio.sleep(random.uniform(0.5, 1.5))  # random delay to avoid blocking

        await browser.close()

    # Save results to CSV
    with open("prices_updated.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sku", "price", "last_updated"])
        writer.writerows(results)

    print("Scraping completed. Results saved in prices_updated.csv")

# Run the scraper
if __name__ == "__main__":
    asyncio.run(main())
