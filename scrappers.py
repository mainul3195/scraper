import re
from dateutil.parser import parse as dateparse
from datetime import datetime

class Scraper:
    def __init__(self, context, start_date, end_date, base_urls):
        if isinstance(start_date, str):
            start_date = dateparse(start_date)
        if isinstance(end_date, str):
            end_date = dateparse(end_date)
        self.context = context
        self.start_date = start_date
        self.end_date = end_date
        self.base_urls = base_urls

    async def scrape_detroit_vod(self):
        print(f"\nSearching for videos between {self.start_date.strftime('%Y-%m-%d')} and {self.end_date.strftime('%Y-%m-%d')}")
        medias = []
        base_url = self.base_urls[0] + "/gallery/3"
        current_page = 1
        page = await self.context.new_page()

        while True:
            print(f"\nProcessing page {current_page}...")
            url = f"{base_url}?page={current_page}&site=1"
            print(f"Navigating to: {url}")
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)

            stubs = await page.query_selector_all('.show-stub')
            if not stubs:
                print(f"No video stubs found on page {current_page}")
                break

            print(f"Found {len(stubs)} videos on page {current_page}")
            for stub in stubs:
                link = await stub.query_selector('a')
                h3 = await stub.query_selector('h3')
                if not link or not h3:
                    continue
                href = await link.get_attribute('href')
                title = await h3.text_content()
                if not href or not title:
                    continue
                title = title.strip()
                if not href.startswith('http'):
                    href = self.base_urls[0].rstrip('/') + href

                # Extract date from title
                date_match = re.findall(r'(\d{2}-\d{2}-\d{4})', title)
                if not date_match:
                    print(f"No date found in title: {title}")
                    continue
                date_str = date_match[-1]
                try:
                    month, day, year = map(int, date_str.split('-'))
                    meeting_date = datetime(year, month, day)
                except Exception as e:
                    print(f"Failed to parse date from: {title}")
                    continue

                print(f"Title: {title}")
                print(f"URL: {href}")
                print(f"Date: {meeting_date.strftime('%Y-%m-%d')}")

                if meeting_date < self.start_date:
                    print(f"Stopping: found date {meeting_date.strftime('%Y-%m-%d')} before start date {self.start_date.strftime('%Y-%m-%d')}")
                    await page.close()
                    return medias
                if self.start_date <= meeting_date <= self.end_date:
                    medias.append({
                        "url": href,
                        "title": title,
                        "date": meeting_date.strftime('%Y-%m-%d'),
                        "source_type": "video"
                    })
                    print("✓ Added to results")
                else:
                    print("× Date outside range")
            current_page += 1

        await page.close()
        print(f"\nTotal videos found: {len(medias)}")
        return medias

class LansdaleScraper:
    def __init__(self, context, base_url):
        self.context = context
        self.base_url = base_url

    async def get_upload_date(self, video_url):
        page = await self.context.new_page()
        try:
            await page.goto(video_url, wait_until='domcontentloaded', timeout=60000)
            # Try to close any modal/pop-up
            try:
                close_btn = await page.query_selector('button[aria-label="Close"], .close, .modal-close')
                if close_btn:
                    await close_btn.click()
            except Exception:
                pass
            # Wait for dd.first to appear
            await page.wait_for_selector('dd.first', timeout=30000)
            dd_first = await page.query_selector('dd.first')
            if dd_first:
                date_text = (await dd_first.text_content() or '').strip()
                try:
                    parsed_date = dateparse(date_text).strftime('%Y-%m-%d')
                    return parsed_date
                except Exception:
                    return date_text  # fallback: return raw text
            return 'nan'
        except Exception as e:
            print(f"Error fetching upload date for {video_url}: {e}")
            return 'nan'
        finally:
            await page.close()

    async def scrape_lansdale_videos(self):
        print(f"\nScraping Lansdale videos from {self.base_url}")
        medias = []
        seen_urls = set()
        page = await self.context.new_page()
        print(f"Navigating to: {self.base_url}")
        await page.goto(self.base_url, wait_until='domcontentloaded', timeout=60000)
        current_page = 1
        video_infos = []
        while True:
            print(f"Processing page {current_page}")
            video_cards = await page.query_selector_all('.video')
            if not video_cards:
                print(f"No video cards found on page {current_page}")
                break
            print(f"Found {len(video_cards)} videos on page {current_page}")
            for card in video_cards:
                link_elem = await card.query_selector('a')
                h3_elem = await card.query_selector('h3')
                if not link_elem or not h3_elem:
                    continue
                href = await link_elem.get_attribute('href')
                title = await h3_elem.text_content()
                if not href or not title:
                    continue
                print(f"Found href: {href}")  # Debug: print all hrefs
                title = title.strip()
                # Accept links that start with /CivicMedia.aspx?VID=
                if not href.startswith('/CivicMedia.aspx?VID='):
                    continue
                full_url = 'https://www.lansdale.org' + href
                if full_url in seen_urls:
                    print(f"Skipping duplicate: {full_url}")
                    continue
                seen_urls.add(full_url)
                video_infos.append({
                    "url": full_url,
                    "title": title
                })
            # Find the next page number link (not the current one)
            pagination_links = await page.query_selector_all('span[id*="dpgVideos"] a')
            # Get the first video href before clicking
            first_video = await page.query_selector('.video a')
            first_video_href = await first_video.get_attribute('href') if first_video else None
            for link in pagination_links:
                text = (await link.text_content() or '').strip()
                if text == str(current_page + 1):
                    print(f"Clicking to page {text}")
                    await link.scroll_into_view_if_needed()
                    await link.click()
                    # Wait for the first video href to change (i.e., new page loaded)
                    for _ in range(30):  # up to 30 seconds
                        await page.wait_for_timeout(1000)
                        new_first_video = await page.query_selector('.video a')
                        new_first_video_href = await new_first_video.get_attribute('href') if new_first_video else None
                        if new_first_video_href and new_first_video_href != first_video_href:
                            break
                    current_page += 1
                    # After clicking, break out of the for loop and let the while loop re-query everything
                    break
            else:
                print("No more pages found.")
                break
        await page.close()
        print(f"\nTotal Lansdale videos found: {len(video_infos)}")
        # Now, visit each video URL to get the upload date
        for info in video_infos:
            upload_date = await self.get_upload_date(info['url'])
            medias.append({
                "url": info['url'],
                "title": info['title'],
                "date": upload_date,
                "source_type": "video"
            })
            print(f"✓ Finalized: {info['title']} | {info['url']} | {upload_date}")
        return medias 