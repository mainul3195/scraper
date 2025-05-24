import asyncio
import json
from playwright.async_api import async_playwright
from scrappers import Scraper, LansdaleScraper

async def main():
    # Read input from input.json
    with open('input.json', 'r') as f:
        INPUT = json.load(f)
    start_date = INPUT.get("start_date")
    end_date = INPUT.get("end_date")
    base_urls = INPUT["base_urls"]
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        for base_url in base_urls:
            # Use Scraper for Detroit, LansdaleScraper for Lansdale
            if "detroit-vod.cablecast.tv" in base_url:
                scraper = Scraper(context, start_date, end_date, [base_url])
                medias = await scraper.scrape_detroit_vod()
            elif "lansdale.org" in base_url:
                scraper = LansdaleScraper(context, base_url)
                medias = await scraper.scrape_lansdale_videos()
            else:
                print(f"Unknown base_url: {base_url}, skipping.")
                medias = []
            results.append({
                "base_url": base_url,
                "medias": medias
            })
        await context.close()
        await browser.close()

    # Write output to output.json
    with open('output.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Results written to output.json")

if __name__ == "__main__":
    asyncio.run(main())