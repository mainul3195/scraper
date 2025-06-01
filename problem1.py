import asyncio
import json
from playwright.async_api import async_playwright
from scrappers import DetroitScraper, LansdaleScraper, FacebookVideoScraper, CharlestonCivicClerkScraper, YouTubeLiveMeetingsScraper, RegionalWebTVScraper

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
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9'
            }
        )
        for base_url in base_urls:
            # Use Scraper for Detroit, LansdaleScraper for Lansdale, FacebookVideoScraper for Facebook, CharlestonCivicClerkScraper for Charleston, YouTubeLiveMeetingsScraper for YouTube, RegionalWebTVScraper for Regional Web TV
            if "detroit-vod.cablecast.tv" in base_url:
                scraper = DetroitScraper(context, start_date, end_date, [base_url])
                medias = await scraper.scrape_detroit_vod()
            elif "lansdale.org" in base_url:
                scraper = LansdaleScraper(context, base_url, start_date, end_date)
                medias = await scraper.scrape_lansdale_videos()
            elif "facebook.com/DauphinCountyPA/videos" in base_url:
                scraper = FacebookVideoScraper(context, base_url)
                medias = await scraper.scrape_facebook_videos()
            elif "charlestonwv.portal.civicclerk.com" in base_url:
                scraper = CharlestonCivicClerkScraper(context, base_url)
                medias = await scraper.scrape_charleston_civicclerk()
            elif "youtube.com/@SLCLiveMeetings/streams" in base_url:
                scraper = YouTubeLiveMeetingsScraper(context, base_url, start_date, end_date)
                medias = await scraper.scrape_youtube_live_meetings()
            elif "regionalwebtv.com/fredcc" in base_url:
                scraper = RegionalWebTVScraper(context, base_url, start_date, end_date)
                medias = await scraper.scrape_regional_webtv()
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