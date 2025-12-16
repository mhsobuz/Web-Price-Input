import asyncio
import os
import random
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import pandas as pd

INPUT_FILE = "products.xlsx"       # Excel input with only 'sku' column
OUTPUT_FILE = "prices_updated.xlsx"
ERROR_FOLDER = "screenshots"
CONCURRENT_PAGES = 6

os.makedirs(ERROR_FOLDER, exist_ok=True)

async def scrape_product(semaphore, context, sku):
    url = f"https://starlightlighting.ca/{sku}"  # Auto-generate URL
    async with semaphore:
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=50000)
            await asyncio.sleep(random.uniform(2, 4))  # wait for JS

            await page.wait_for_selector("div.cat-grid-item-info", timeout=10000)
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

            price_number = ''.join(c for c in price_text if c.isdigit() or c == '.') if price_text else "N/A"
            print(sku, price_number)
            return sku, price_number

        except PlaywrightTimeoutError:
            print(f"{sku}: Timeout or element not found")
            return sku, "N/A"
        except Exception as e:
            screenshot_path = os.path.join(ERROR_FOLDER, f"{sku}.png")
            await page.screenshot(path=screenshot_path)
            print(f"{sku}: Error - {e} (screenshot saved)")
            return sku, "ERROR"
        finally:
            await page.close()

async def main():
    semaphore = asyncio.Semaphore(CONCURRENT_PAGES)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        # Read Excel input with only 'sku'
        df_input = pd.read_excel(INPUT_FILE)
        tasks = [scrape_product(semaphore, context, str(row['sku']))
                 for _, row in df_input.iterrows()]

        results = await asyncio.gather(*tasks)
        await browser.close()

    # Save results to Excel
    df_output = pd.DataFrame(results, columns=["SKU", "Price"])
    df_output.to_excel(OUTPUT_FILE, index=False)
    print(f"Scraping completed. Results saved in {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
