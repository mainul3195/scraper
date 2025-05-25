import re
from dateutil.parser import parse as dateparse
from datetime import datetime, timedelta
import random
import asyncio
import json

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

class FacebookScraper:
    def __init__(self, context, base_url):
        self.context = context
        self.base_url = base_url

    async def scroll_to_load_all_videos(self, page, selector='a[href*="/videos/"]', max_scrolls=50, wait_time=2):
        last_count = 0
        for _ in range(max_scrolls):
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(wait_time * 1000)
            video_anchors = await page.query_selector_all(selector)
            current_count = len(video_anchors)
            if current_count == last_count:
                break
            last_count = current_count
        return await page.query_selector_all(selector)

    async def extract_facebook_video_upload_date(self, page, video_url=None):
        try:
            # Method 1: Look for time elements with datetime attributes
            time_elements = await page.locator('time').all()
            for time_elem in time_elements:
                datetime_attr = await time_elem.get_attribute('datetime')
                if datetime_attr:
                    try:
                        dt = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                        return dt.strftime('%Y-%m-%d')
                    except:
                        pass
            # Method 2: Look for data-utime attributes (Unix timestamp)
            utime_elements = await page.locator('[data-utime]').all()
            for elem in utime_elements:
                utime = await elem.get_attribute('data-utime')
                if utime and utime.isdigit():
                    try:
                        dt = datetime.fromtimestamp(int(utime))
                        return dt.strftime('%Y-%m-%d')
                    except:
                        pass
            # Method 3: Look for relative time text
            relative_time_patterns = [
                r'(\d+)\s*(minute|minutes|min|mins)\s*ago',
                r'(\d+)\s*(hour|hours|hr|hrs)\s*ago',
                r'(\d+)\s*(day|days)\s*ago',
                r'(\d+)\s*(week|weeks|wk|wks)\s*ago',
                r'(\d+)\s*(month|months|mon|mons)\s*ago',
                r'(\d+)\s*(year|years|yr|yrs)\s*ago',
                r'yesterday',
                r'today'
            ]
            page_text = await page.locator('body').text_content()
            for pattern in relative_time_patterns:
                matches = re.finditer(pattern, page_text, re.IGNORECASE)
                for match in matches:
                    try:
                        upload_date = self.parse_relative_time(match.group())
                        if upload_date:
                            return upload_date.strftime('%Y-%m-%d')
                    except:
                        continue
            # Method 4: Look for specific Facebook date patterns in spans
            span_elements = await page.locator('span').all()
            for span in span_elements:
                text = await span.text_content()
                if text:
                    date_patterns = [
                        r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
                        r'\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b',
                        r'\b\d{4}[/\-]\d{1,2}[/\-]\d{1,2}\b'
                    ]
                    for pattern in date_patterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            try:
                                date_str = match.group()
                                parsed_date = self.parse_date_string(date_str)
                                if parsed_date:
                                    return parsed_date.strftime('%Y-%m-%d')
                            except:
                                continue
            # Method 5: Look in meta tags
            meta_elements = await page.locator('meta').all()
            for meta in meta_elements:
                property_attr = await meta.get_attribute('property')
                content_attr = await meta.get_attribute('content')
                if property_attr and content_attr:
                    if any(date_prop in property_attr.lower() for date_prop in ['published', 'created', 'updated', 'time']):
                        try:
                            dt = datetime.fromisoformat(content_attr.replace('Z', '+00:00'))
                            return dt.strftime('%Y-%m-%d')
                        except:
                            pass
            # Method 6: Look for JSON-LD structured data
            script_elements = await page.locator('script[type="application/ld+json"]').all()
            for script in script_elements:
                script_content = await script.text_content()
                if script_content:
                    try:
                        data = json.loads(script_content)
                        date_fields = ['datePublished', 'dateCreated', 'uploadDate', 'dateModified']
                        for field in date_fields:
                            if field in data:
                                try:
                                    dt = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
                                    return dt.strftime('%Y-%m-%d')
                                except:
                                    pass
                    except:
                        pass
            # Method 7: Obfuscated date extraction from spans (browser rendered)
            try:
                date_text = await page.evaluate("""
                () => {
                    // Find all spans that are likely part of the date
                    let spans = Array.from(document.querySelectorAll('span.xi7du73, span.x1lliihq, span.x1n2onr6, span.x17ihmo5'));
                    // Filter out spans that are not visible or empty
                    spans = spans.filter(s => s.offsetParent !== null && s.innerText.trim().length === 1);
                    // Join the characters
                    return spans.map(s => s.innerText).join('');
                }
                """)
                if date_text and len(date_text) > 5:
                    # Try to parse the date string
                    parsed_date = self.parse_date_string(date_text)
                    if parsed_date:
                        return parsed_date.strftime('%Y-%m-%d')
                    else:
                        try:
                            from dateutil.parser import parse as dateparse
                            return dateparse(date_text).strftime('%Y-%m-%d')
                        except:
                            pass
            except Exception as e:
                print(f"Obfuscated date extraction failed: {e}")
            print(f"Could not extract upload date for video: {video_url or 'unknown'}")
            return None
        except Exception as e:
            print(f"Error extracting upload date: {str(e)}")
            return None

    def parse_relative_time(self, time_str):
        now = datetime.now()
        time_str = time_str.lower().strip()
        if 'today' in time_str:
            return now
        elif 'yesterday' in time_str:
            return now - timedelta(days=1)
        match = re.search(r'(\d+)\s*(minute|hour|day|week|month|year)', time_str)
        if not match:
            return None
        number = int(match.group(1))
        unit = match.group(2)
        if 'minute' in unit:
            return now - timedelta(minutes=number)
        elif 'hour' in unit:
            return now - timedelta(hours=number)
        elif 'day' in unit:
            return now - timedelta(days=number)
        elif 'week' in unit:
            return now - timedelta(weeks=number)
        elif 'month' in unit:
            return now - timedelta(days=number * 30)
        elif 'year' in unit:
            return now - timedelta(days=number * 365)
        return None

    def parse_date_string(self, date_str):
        date_formats = [
            '%B %d, %Y', '%B %d %Y', '%m/%d/%Y', '%m-%d-%Y', '%Y/%m/%d', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'
        ]
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    async def get_facebook_video_upload_date(self, video_url):
        page = await self.context.new_page()
        try:
            print(f"Navigating to video: {video_url}")
            await page.goto(video_url, wait_until='networkidle')
            await page.wait_for_timeout(3000)
            try:
                cookie_button = page.locator('button:has-text("Allow all cookies"), button:has-text("Accept all")')
                if await cookie_button.count() > 0:
                    await cookie_button.first.click()
                    await page.wait_for_timeout(2000)
            except:
                pass
            upload_date = await self.extract_facebook_video_upload_date(page, video_url)
            return upload_date
        except Exception as e:
            print(f"Error getting upload date for {video_url}: {str(e)}")
            return None
        finally:
            await page.close()

    async def scrape_facebook_videos(self):
        print(f"\nScraping Facebook videos from {self.base_url}")
        medias = []
        seen_urls = set()
        page = await self.context.new_page()
        print(f"Navigating to: {self.base_url}")
        await page.goto(self.base_url, wait_until='domcontentloaded', timeout=60000)

        max_scrolls = 300
        no_new_videos_limit = 20
        no_new_videos_count = 0
        last_total = 0

        for _ in range(max_scrolls):
            scroll_amount = random.randint(500, 1200)
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await page.wait_for_timeout(random.randint(1500, 3500))

            video_anchors = await page.query_selector_all('a[href*="/videos/"]')
            for anchor in video_anchors:
                href = await anchor.get_attribute('href')
                title_elem = await anchor.query_selector('.x1lliihq.x6ikm8r.x10wlt62.x1n2onr6')
                title = await title_elem.text_content() if title_elem else None
                if not href or not title:
                    continue
                href = href.strip()
                title = title.strip()
                if href.startswith('/'):
                    full_url = 'https://www.facebook.com' + href
                else:
                    full_url = href
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)
                # Get upload date by visiting the video page
                upload_date = await self.get_facebook_video_upload_date(full_url)
                medias.append({
                    "url": full_url,
                    "title": title,
                    "date": upload_date,
                    "source_type": "video"
                })
                print(f"✓ Added: {title} | {full_url} | {upload_date}")

            if len(medias) == last_total:
                no_new_videos_count += 1
            else:
                no_new_videos_count = 0
            last_total = len(medias)

            if no_new_videos_count >= no_new_videos_limit:
                break

        await page.close()
        print(f"\nTotal Facebook videos found: {len(medias)}")
        return medias 

class CharlestonCivicClerkScraper:
    def __init__(self, context, base_url):
        self.context = context
        self.base_url = base_url

    async def scrape_charleston_civicclerk(self):
        print(f"\nScraping Charleston CivicClerk media from {self.base_url}")
        medias = []
        seen_urls = set()
        page = await self.context.new_page()
        print(f"Navigating to: {self.base_url}")
        await page.goto(self.base_url, wait_until='domcontentloaded', timeout=60000)

        months_without_events = 0
        max_months_without_events = 1
        while months_without_events <= max_months_without_events:
            # Find all event rows on the current month
            event_rows = await page.query_selector_all('li.cpp-MuiListItem-container')
            if not event_rows:
                months_without_events += 1
            else:
                months_without_events = 0
            for row in event_rows:
                # Extract the media link
                link_elem = await row.query_selector('a[href*="/files"]')
                if not link_elem:
                    continue
                href = await link_elem.get_attribute('href')
                if not href:
                    continue
                if href.startswith('/'):
                    full_url = 'https://charlestonwv.portal.civicclerk.com' + href
                else:
                    full_url = href
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)
                # Extract the title
                title_elem = await row.query_selector('[aria-labelledby*="title"], [id*="title"], .cpp-MuiTypography-subtitle1')
                title = await title_elem.text_content() if title_elem else 'PDF Media'
                title = title.strip() if title else 'PDF Media'
                # Extract the date
                date_attr = await link_elem.get_attribute('data-date')
                if not date_attr:
                    # Try to get from parent row
                    date_attr = await row.get_attribute('data-date')
                upload_date = None
                if date_attr:
                    try:
                        upload_date = date_attr[:10]
                    except:
                        upload_date = None
                medias.append({
                    "url": full_url,
                    "title": title,
                    "date": upload_date,
                    "source_type": "pdf"
                })
                print(f"✓ Added: {title} | {full_url} | {upload_date}")
            # Try to go to previous month
            prev_btn = await page.query_selector('button[aria-label*="Previous month"], button[title*="Previous month"]')
            if prev_btn:
                await prev_btn.click()
                await page.wait_for_timeout(2000)
            else:
                break
        await page.close()
        print(f"\nTotal Charleston CivicClerk media found: {len(medias)}")
        return medias 

class YouTubeLiveMeetingsScraper:
    def __init__(self, context, base_url):
        self.context = context
        self.base_url = base_url

    async def parse_relative_time(self, time_str):
        # Example: 'Streamed 1 month ago', 'Streamed 5 hours ago'
        import re
        from datetime import datetime, timedelta
        now = datetime.now()
        time_str = time_str.lower().strip()
        match = re.search(r'streamed\s+(\d+)\s+(minute|hour|day|week|month|year)', time_str)
        if not match:
            return None
        number = int(match.group(1))
        unit = match.group(2)
        if 'minute' in unit:
            return (now - timedelta(minutes=number)).strftime('%Y-%m-%d')
        elif 'hour' in unit:
            return (now - timedelta(hours=number)).strftime('%Y-%m-%d')
        elif 'day' in unit:
            return (now - timedelta(days=number)).strftime('%Y-%m-%d')
        elif 'week' in unit:
            return (now - timedelta(weeks=number)).strftime('%Y-%m-%d')
        elif 'month' in unit:
            return (now - timedelta(days=number * 30)).strftime('%Y-%m-%d')
        elif 'year' in unit:
            return (now - timedelta(days=number * 365)).strftime('%Y-%m-%d')
        return None

    async def scroll_to_load_all_youtube_videos(self, page, max_scrolls=200, wait_time=2, no_new_limit=10):
        last_count = 0
        no_new_count = 0
        for _ in range(max_scrolls):
            await page.evaluate('window.scrollBy(0, 500)')
            await page.wait_for_timeout(wait_time * 1000)
            video_items = await page.query_selector_all('ytd-rich-item-renderer')
            if len(video_items) == last_count:
                no_new_count += 1
            else:
                no_new_count = 0
            last_count = len(video_items)
            if no_new_count >= no_new_limit:
                break
        return await page.query_selector_all('ytd-rich-item-renderer')

    async def scrape_youtube_live_meetings(self):
        print(f"\nScraping YouTube Live Meetings from {self.base_url}")
        medias = []
        seen_urls = set()
        page = await self.context.new_page()
        print(f"Navigating to: {self.base_url}")
        await page.goto(self.base_url, wait_until='domcontentloaded', timeout=60000)

        # Incremental scroll to load all videos
        video_items = await self.scroll_to_load_all_youtube_videos(page)
        print(f"Found {len(video_items)} video items")
        for item in video_items:
            # Get the video link and title
            link_elem = await item.query_selector('a#video-title-link')
            if not link_elem:
                continue
            href = await link_elem.get_attribute('href')
            title = await link_elem.get_attribute('title') or await link_elem.text_content() or 'YouTube Video'
            title = title.strip()
            if not href:
                continue
            if href.startswith('/'):
                full_url = 'https://www.youtube.com' + href
            else:
                full_url = href
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            # Get the upload date (relative time)
            date_elems = await item.query_selector_all('span.inline-metadata-item.style-scope.ytd-video-meta-block')
            upload_date = None
            for elem in date_elems:
                date_text = await elem.text_content()
                if date_text and 'streamed' in date_text.lower():
                    upload_date = await self.parse_relative_time(date_text)
                    break
            medias.append({
                "url": full_url,
                "title": title,
                "date": upload_date,
                "source_type": "video"
            })
            print(f"✓ Added: {title} | {full_url} | {upload_date}")
        await page.close()
        print(f"\nTotal YouTube Live Meetings found: {len(medias)}")
        return medias 