import asyncio
import csv
import random
import os
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

INPUT_FILE = "products.csv"
OUTPUT_FILE = "prices_updated.csv"
ERROR_FOLDER = "screenshots"
CONCURRENT_PAGES = 5

os.makedirs(ERROR_FOLDER, exist_ok=True)

async def scrape_product(semaphore, context, sku, url):
    async with semaphore:
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(random.uniform(2, 4))  # extra wait for JS content

            # Wait for grid items
            await page.wait_for_selector("div.cat-grid-item-info", timeout=10000)

            # Find correct product by SKU
            grid_items = await page.query_selector_all("div.cat-grid-item-info")
            price_text = None
            for item in grid_items:
                cart_span = await item.query_selector(".specific-cart")
                if cart_span:
                    onclick_attr = await cart_span.get_attribute("onclick")
                    if sku in onclick_attr:
                        price_element = await item.query_selector(".cat-price")
                        if price_element:
                            price_text = await price_element.inner_text()
                        break

            # Clean price
            price_number = ''.join(c for c in price_text if c.isdigit() or c == '.') if price_text else "N/A"

            print(sku, price_number)
            return sku, price_number, datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        except PlaywrightTimeoutError:
            print(f"{sku}: Timeout or element not found")
            return sku, "N/A", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            screenshot_path = os.path.join(ERROR_FOLDER, f"{sku}.png")
            await page.screenshot(path=screenshot_path)
            print(f"{sku}: Error - {e} (screenshot saved)")
            return sku, "ERROR", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        finally:
            await page.close()

async def main():
    semaphore = asyncio.Semaphore(CONCURRENT_PAGES)
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # debug mode
        context = await browser.new_context()

        tasks = []
        with open(INPUT_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tasks.append(scrape_product(semaphore, context, row["sku"], row["url"]))

        for task in asyncio.as_completed(tasks):
            results.append(await task)
            await asyncio.sleep(random.uniform(0.5, 1.5))

        await browser.close()

    # Save to CSV
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sku", "price", "last_updated"])
        writer.writerows(results)

    print(f"Scraping completed. Results saved in {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
