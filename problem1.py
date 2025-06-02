import asyncio
import json
from playwright.async_api import async_playwright
from scrapers import DetroitScraper, LansdaleScraper, FacebookVideoScraper, CharlestonCivicClerkScraper, YouTubeLiveMeetingsScraper, RegionalWebTVScraper, WinchesterVAScraper

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
            # Use Scraper for Detroit, LansdaleScraper for Lansdale, FacebookVideoScraper for Facebook, CharlestonCivicClerkScraper for Charleston, YouTubeLiveMeetingsScraper for YouTube, RegionalWebTVScraper for Regional Web TV, WinchesterVAScraper for Winchester VA
            if "detroit-vod.cablecast.tv" in base_url:
                scraper = DetroitScraper(context, start_date, end_date, [base_url])
                medias = await scraper.scrape_detroit_vod()
                results.append({
                    "base_url": base_url,
                    "medias": medias
                })
            elif "lansdale.org" in base_url:
                scraper = LansdaleScraper(context, base_url, start_date, end_date)
                medias = await scraper.scrape_lansdale_videos()
                results.append({
                    "base_url": base_url,
                    "medias": medias
                })
            elif "facebook.com/DauphinCountyPA/videos" in base_url:
                scraper = FacebookVideoScraper(context, base_url)
                medias = await scraper.scrape_facebook_videos()
                results.append({
                    "base_url": base_url,
                    "medias": medias
                })
            elif "charlestonwv.portal.civicclerk.com" in base_url:
                scraper = CharlestonCivicClerkScraper(context, base_url, start_date, end_date)
                medias = await scraper.scrape_charleston_civicclerk()
                results.append({
                    "base_url": base_url,
                    "medias": medias
                })
            elif "youtube.com/@SLCLiveMeetings/streams" in base_url:
                scraper = YouTubeLiveMeetingsScraper(context, base_url, start_date, end_date)
                medias = await scraper.scrape_youtube_live_meetings()
                results.append({
                    "base_url": base_url,
                    "medias": medias
                })
            elif "regionalwebtv.com/fredcc" in base_url:
                scraper = RegionalWebTVScraper(context, base_url, start_date, end_date)
                medias = await scraper.scrape_regional_webtv()
                results.append({
                    "base_url": base_url,
                    "medias": medias
                })
            elif "winchesterva.civicweb.net/portal" in base_url:
                # Synchronous scraper, run outside async context
                scraper = WinchesterVAScraper()
                medias = scraper.scrape_meetings_to_json(start_date, end_date)
                results.append({
                    "base_url": base_url,
                    "medias": medias
                })
            else:
                print(f"Unknown base_url: {base_url}, skipping.")
                results.append({
                    "base_url": base_url,
                    "medias": []
                })
        await context.close()
        await browser.close()

    # Write output to output.json
    with open('output.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Results written to output.json")

if __name__ == "__main__":
    asyncio.run(main())