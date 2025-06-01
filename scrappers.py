import re
from dateutil.parser import parse as dateparse
from datetime import datetime, timedelta
import random
import asyncio
import json
import os

class DetroitScraper:
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
    def __init__(self, context, base_url, start_date=None, end_date=None):
        if start_date is not None and isinstance(start_date, str):
            start_date = dateparse(start_date)
        if end_date is not None and isinstance(end_date, str):
            end_date = dateparse(end_date)
        self.context = context
        self.base_url = base_url
        self.start_date = start_date
        self.end_date = end_date

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
        if self.start_date and self.end_date:
            print(f"Filtering videos between {self.start_date.strftime('%Y-%m-%d')} and {self.end_date.strftime('%Y-%m-%d')}")
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
            add_media = True
            dt = None
            if self.start_date and self.end_date and upload_date and upload_date != 'nan':
                try:
                    dt = dateparse(upload_date)
                    add_media = self.start_date <= dt <= self.end_date
                except Exception:
                    add_media = False
            if add_media:
                medias.append({
                    "url": info['url'],
                    "title": info['title'],
                    "date": upload_date,
                    "source_type": "video"
                })
                print(f"✓ Finalized: {info['title']} | {info['url']} | {upload_date}")
            else:
                print(f"× Skipped (out of range): {info['title']} | {upload_date}")
        return medias 

class FacebookVideoScraper:
    def __init__(self, context, base_url, start_date=None, end_date=None):
        if start_date is not None and isinstance(start_date, str):
            start_date = dateparse(start_date)
        if end_date is not None and isinstance(end_date, str):
            end_date = dateparse(end_date)
        self.context = context
        self.base_url = base_url
        self.start_date = start_date
        self.end_date = end_date

    async def wait_for_cards_to_load(self, page, timeout=30000):
        """Wait for video cards to fully load with content"""
        try:
            # Wait for cards to have actual content, not just empty divs
            await page.wait_for_function("""
                () => {
                    const cards = document.querySelectorAll('div.x9f619.x1r8uery.x1iyjqo2.x6ikm8r.x10wlt62.x1n2onr6');
                    if (cards.length === 0) return false;
                    
                    // Check if at least some cards have meaningful content
                    let cardsWithContent = 0;
                    for (let card of cards) {
                        const links = card.querySelectorAll('a[href*="/videos/"]');
                        const text = card.textContent.trim();
                        if (links.length > 0 || text.length > 50) {
                            cardsWithContent++;
                        }
                    }
                    
                    return cardsWithContent >= Math.min(5, cards.length * 0.3);
                }
            """, timeout=timeout)
            return True
        except:
            print("Warning: Cards may not have fully loaded, proceeding anyway...")
            return False

    async def scroll_to_load_all_videos(self, page, target_count=100, max_scrolls=200, base_wait_time=4):
        """Aggressive scrolling to load all 100 videos, with YouTube-style fallback if needed"""
        print(f"Starting to scroll and load video content (target: {target_count} videos)...")
        last_count = 0
        consecutive_no_change = 0
        max_no_change = 15  # Increased patience
        used_fallback = False
        
        for scroll_num in range(max_scrolls):
            # Get current page height before scrolling
            current_height = await page.evaluate('document.body.scrollHeight')
            
            # Aggressive multi-step scrolling strategy
            await page.evaluate('''
                () => {
                    // Method 1: Scroll to absolute bottom
                    window.scrollTo(0, document.body.scrollHeight);
                    
                    // Method 2: Try scrolling main content areas
                    const scrollableElements = [
                        document.querySelector('[role="main"]'),
                        document.querySelector('[data-pagelet="ProfileTimeline"]'),
                        document.querySelector('div[style*="overflow"]'),
                        document.documentElement
                    ];
                    
                    scrollableElements.forEach(el => {
                        if (el && el.scrollHeight > el.clientHeight) {
                            el.scrollTop = el.scrollHeight;
                        }
                    });
                    
                    // Method 3: Trigger multiple scroll events
                    ['scroll', 'wheel', 'touchmove'].forEach(eventType => {
                        window.dispatchEvent(new Event(eventType, { bubbles: true }));
                    });
                }
            ''')
            
            # Dynamic wait time - longer waits as we get more content
            wait_time = base_wait_time + (scroll_num // 20)  # Increase wait every 20 scrolls
            await page.wait_for_timeout(wait_time * 1000)
            
            # Every few scrolls, use additional techniques
            if scroll_num % 4 == 0:
                # Technique 1: Scroll up then down to trigger lazy loading
                await page.evaluate('window.scrollBy(0, -500)')
                await page.wait_for_timeout(1000)
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(2000)
                
                # Technique 2: Simulate user interaction
                await page.evaluate('''
                    () => {
                        // Simulate mouse movement to trigger hover states
                        const event = new MouseEvent('mousemove', {
                            view: window,
                            bubbles: true,
                            cancelable: true,
                            clientX: window.innerWidth / 2,
                            clientY: window.innerHeight / 2
                        });
                        document.dispatchEvent(event);
                    }
                ''')
                
            # Every 8 scrolls, wait for network activity to settle
            if scroll_num % 8 == 0:
                try:
                    await page.wait_for_load_state('networkidle', timeout=8000)
                except:
                    pass  # Continue if network doesn't settle
            
            # Count video cards
            video_cards = await page.query_selector_all('div.x9f619.x1r8uery.x1iyjqo2.x6ikm8r.x10wlt62.x1n2onr6')
            current_count = len(video_cards)
            
            # Check if page height increased (indicates new content loaded)
            new_height = await page.evaluate('document.body.scrollHeight')
            height_increased = new_height > current_height
            
            print(f"Scroll {scroll_num + 1}: Found {current_count} video cards (height: {current_height} → {new_height})")
            
            # More sophisticated progress detection
            if current_count == last_count and not height_increased:
                consecutive_no_change += 1
                
                # If we're close to target, be more patient
                if current_count >= target_count * 0.8:  # Within 80% of target
                    patience_multiplier = 2
                else:
                    patience_multiplier = 1
                    
                if consecutive_no_change >= max_no_change * patience_multiplier:
                    print(f"No new content after {consecutive_no_change} scrolls. Current: {current_count}, Target: {target_count}")
                    print("Trying YouTube-style fallback scroll...")
                    used_fallback = True
                    # --- YOUTUBE-STYLE FALLBACK ---
                    fallback_no_new = 0
                    fallback_last_count = current_count
                    for fallback_scroll in range(50):
                        await page.evaluate('window.scrollBy(0, 500)')
                        await page.wait_for_timeout(1200)
                        video_cards_fb = await page.query_selector_all('div.x9f619.x1r8uery.x1iyjqo2.x6ikm8r.x10wlt62.x1n2onr6')
                        fb_count = len(video_cards_fb)
                        print(f"[Fallback] Scroll {fallback_scroll+1}: {fb_count} cards loaded.")
                        if fb_count == fallback_last_count:
                            fallback_no_new += 1
                        else:
                            fallback_no_new = 0
                        fallback_last_count = fb_count
                        if fallback_no_new >= 10:
                            print("[Fallback] No new cards after several scrolls. Stopping fallback.")
                            break
                        if fb_count >= target_count:
                            print(f"[Fallback] Target reached! Found {fb_count} cards.")
                            break
                    # After fallback, break out of main scroll loop
                    break
            else:
                consecutive_no_change = 0
                last_count = current_count
                
            # Check if we've reached our target
            if current_count >= target_count:
                print(f"🎉 Target reached! Found {current_count} cards (target was {target_count})")
                break
                
            # Safety check - if we're way past target, something might be wrong
            if current_count > target_count * 1.5:
                print(f"⚠️  Found more cards than expected ({current_count} > {target_count * 1.5}). Stopping to avoid infinite scroll.")
                break
        
        # Final comprehensive wait for all content to load
        print("Final loading phase - waiting for all cards to populate...")
        for attempt in range(10):
            await page.wait_for_timeout(2000)
            loaded_count = await page.evaluate('''
                () => {
                    const cards = document.querySelectorAll('div.x9f619.x1r8uery.x1iyjqo2.x6ikm8r.x10wlt62.x1n2onr6');
                    let loaded = 0;
                    for (let card of cards) {
                        const hasLink = card.querySelector('a[href]');
                        const hasText = card.textContent.trim().length > 20;
                        if (hasLink || hasText) loaded++;
                    }
                    return loaded;
                }
            ''')
            print(f"Loading attempt {attempt + 1}: {loaded_count} cards have content")
            # If most cards have content, we're good
            current_count = len(await page.query_selector_all('div.x9f619.x1r8uery.x1iyjqo2.x6ikm8r.x10wlt62.x1n2onr6'))
            if loaded_count >= current_count * 0.7:  # 70% of cards have content
                break
        final_cards = await page.query_selector_all('div.x9f619.x1r8uery.x1iyjqo2.x6ikm8r.x10wlt62.x1n2onr6')
        final_count = len(final_cards)
        print(f"Final count: {final_count} video cards loaded" + (" (YouTube-style fallback used)" if used_fallback else ""))
        if final_count < target_count:
            print(f"⚠️  Only found {final_count} cards out of expected {target_count}")
            print("This could be due to:")
            print("- Facebook's rate limiting")
            print("- Authentication requirements") 
            print("- Changed page structure")
            print("- Network issues")
        return final_cards

    async def extract_video_info_from_card(self, card, card_index):
        try:
            video_info = {
                "url": None,
                "title": None,
                "date": None,
                "source_type": "video"
            }

            await asyncio.sleep(0.5)

            # 1. Find the <a> with the video link
            link_elem = await card.query_selector('a[href*="/videos/"]')
            if link_elem:
                href = await link_elem.get_attribute('href')
                if href:
                    video_info["url"] = href

                # 2. Find the <span> with the title/date inside the <a>
                title_elem = await link_elem.query_selector('span.x1lliihq.x6ikm8r.x10wlt62.x1n2onr6')
                if title_elem:
                    title_text = (await title_elem.text_content() or '').strip()
                    video_info["title"] = title_text
                    # Try to extract date from the title using regex
                    import re
                    date_match = re.search(r'(\d{2}/\d{2}/\d{2,4})', title_text)
                    if date_match:
                        video_info["date"] = date_match.group(1)
            # Fallback: try to find the <span> elsewhere in the card
            if not video_info["title"]:
                title_elem = await card.query_selector('span.x1lliihq.x6ikm8r.x10wlt62.x1n2onr6')
                if title_elem:
                    title_text = (await title_elem.text_content() or '').strip()
                    video_info["title"] = title_text
                    import re
                    date_match = re.search(r'(\d{2}/\d{2}/\d{2,4})', title_text)
                    if date_match:
                        video_info["date"] = date_match.group(1)

            # Only return if we have a valid URL
            if video_info["url"]:
                return video_info
            else:
                print(f"DEBUG - Card {card_index}: No URL found")
                return None

        except Exception as e:
            print(f"Error extracting video info from card {card_index}: {e}")
            return None

    async def scrape_facebook_videos(self):
        """Main scraping method with enhanced error handling"""
        print(f"\nScraping Facebook videos from {self.base_url}")
        
        medias = []
        seen_urls = set()
        
        try:
            page = await self.context.new_page()
            
            # Enhanced headers to appear more like a real browser
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
            })
            
            # Set viewport to ensure proper rendering
            await page.set_viewport_size({"width": 1366, "height": 768})

            # --- Load Facebook cookies if available ---
            cookie_path = 'facebook_cookies.json'
            if os.path.exists(cookie_path):
                with open(cookie_path, 'r') as f:
                    cookies = json.load(f)
                # print("COOKIES TO BE ADDED:")
                # print(json.dumps(cookies, indent=2))
                try:
                    await self.context.add_cookies(cookies)
                    print("Loaded Facebook cookies for authentication.")
                except Exception as e:
                    print(f"Error adding cookies: {e}")
                    print("Cookies passed:")
                    print(json.dumps(cookies, indent=2))
                    await page.close()
                    return medias
            else:
                print("facebook_cookies.json not found. Proceeding without cookies.")

            print(f"Navigating to: {self.base_url}")
            nav_success = False
            for attempt in range(3):
                try:
                    await page.goto(self.base_url, wait_until='domcontentloaded', timeout=90000)
                    nav_success = True
                    break
                except Exception as e:
                    print(f"[Retry {attempt+1}] Page.goto failed: {e}")
                    await page.wait_for_timeout(4000)
                    try:
                        await page.reload(wait_until='domcontentloaded', timeout=90000)
                        nav_success = True
                        break
                    except Exception as e2:
                        print(f"[Retry {attempt+1}] Page.reload failed: {e2}")
                        await page.wait_for_timeout(4000)
            if not nav_success:
                print("Failed to load Facebook page after retries. Skipping.")
                await page.close()
                return medias
            # Wait extra for dynamic content
            await page.wait_for_timeout(8000)
            # Handle cookie consent
            try:
                cookie_buttons = await page.query_selector_all('[data-testid="cookie-policy-manage-dialog"] button, [data-cookiebanner="accept_button"]')
                if cookie_buttons:
                    await cookie_buttons[0].click()
                    await page.wait_for_timeout(2000)
                    print("Handled cookie consent")
            except Exception as e:
                print(f"Cookie consent handling error: {e}")
            # Check for login wall
            try:
                login_elements = await page.query_selector_all('#login_form, [data-testid="royal_login_form"]')
                if login_elements:
                    print("⚠️  Login form detected - Facebook may require authentication. Skipping this page.")
                    await page.close()
                    return medias
            except Exception as e:
                print(f"Login wall check error: {e}")
            # Verify main content is loaded
            try:
                await page.wait_for_selector('[role="main"], div[data-pagelet="ProfileTimeline"]', timeout=15000)
                print("Page main content detected")
            except:
                print("Warning: Main content selector not found, proceeding anyway...")
            # Wait extra for dynamic content
            await page.wait_for_timeout(5000)
            # Enhanced scroll and load - targeting 100 videos
            video_cards = await self.scroll_to_load_all_videos(page, target_count=100)
            if not video_cards:
                print("No video cards found after scrolling. Debugging page...")
                await self.debug_facebook_page(page)
                await page.close()
                return medias
            print(f"\nProcessing {len(video_cards)} video cards...")
            # Process cards with better error handling
            for i, card in enumerate(video_cards):
                try:
                    video_info = await self.extract_video_info_from_card(card, i+1)
                    if video_info and video_info["url"]:
                        if video_info["url"] not in seen_urls:
                            seen_urls.add(video_info["url"])
                            medias.append(video_info)
                            print(f"✓ Added: {video_info['title'][:60]}...")
                            print(f"  └─ URL: {video_info['url']}")
                        else:
                            print(f"× Skipped (duplicate): Card {i+1}")
                    else:
                        print(f"× Skipped card {i+1}: No valid URL found")
                except Exception as e:
                    print(f"Error processing card {i+1}: {e}")
                    continue
            await page.close()
        except Exception as e:
            print(f"Error in scrape_facebook_videos: {e}")
            if 'page' in locals():
                await page.close()
        print(f"\nTotal Facebook videos found: {len(medias)}")
        return medias

    async def debug_facebook_page(self, page):
        """Enhanced debug method"""
        try:
            print("\n=== FACEBOOK PAGE DEBUG ===")
            
            title = await page.title()
            url = page.url
            print(f"Page Title: {title}")
            print(f"Current URL: {url}")
            
            # Check for login requirement
            login_elements = await page.query_selector_all('#login_form, [data-testid="royal_login_form"]')
            if login_elements:
                print("⚠️  Login form detected - Facebook may require authentication")
            
            # Check various video-related selectors
            selectors_to_check = [
                ('Target video cards', 'div.x9f619.x1r8uery.x1iyjqo2.x6ikm8r.x10wlt62.x1n2onr6'),
                ('Video links', 'a[href*="/videos/"]'),
                ('Any videos', 'video'),
                ('Role img elements', '[role="img"]'),
                ('Main content', '[role="main"]'),
                ('Profile timeline', '[data-pagelet="ProfileTimeline"]')
            ]
            
            for name, selector in selectors_to_check:
                try:
                    elements = await page.query_selector_all(selector)
                    print(f"{name}: {len(elements)} found")
                except:
                    print(f"{name}: Error checking selector")
            
            # Sample some card content
            try:
                cards = await page.query_selector_all('div.x9f619.x1r8uery.x1iyjqo2.x6ikm8r.x10wlt62.x1n2onr6')
                print(f"\nSampling first 3 cards:")
                for i, card in enumerate(cards[:3]):
                    try:
                        text = await card.text_content()
                        html = await card.inner_html()
                        print(f"Card {i+1}:")
                        print(f"  Text length: {len(text) if text else 0}")
                        print(f"  HTML length: {len(html) if html else 0}")
                        if text and len(text.strip()) > 0:
                            print(f"  Sample text: {text[:100]}...")
                    except Exception as e:
                        print(f"  Error sampling card {i+1}: {e}")
            except:
                print("Could not sample card content")
                
        except Exception as e:
            print(f"Error in debug_facebook_page: {e}")

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
    def __init__(self, context, base_url, start_date=None, end_date=None):
        from dateutil.parser import parse as dateparse
        self.context = context
        self.base_url = base_url
        if start_date is not None and isinstance(start_date, str):
            start_date = dateparse(start_date)
        if end_date is not None and isinstance(end_date, str):
            end_date = dateparse(end_date)
        self.start_date = start_date
        self.end_date = end_date

    async def scroll_to_load_all_youtube_videos(self, page, max_scrolls=200, wait_time=1, no_new_limit=10):
        print("[Scroll] Starting to scroll to load YouTube videos...")
        last_count = 0
        no_new_count = 0
        for scroll_num in range(max_scrolls):
            await page.evaluate('window.scrollBy(0, 500)')
            await page.wait_for_timeout(wait_time * 1000)
            video_items = await page.query_selector_all('ytd-rich-item-renderer')
            print(f"[Scroll] Scroll {scroll_num+1}: {len(video_items)} videos loaded so far.")
            if len(video_items) == last_count:
                no_new_count += 1
            else:
                no_new_count = 0
            last_count = len(video_items)
            if no_new_count >= no_new_limit:
                print("[Scroll] No new videos loaded after several scrolls. Stopping scroll.")
                break
        print(f"[Scroll] Finished scrolling. Total videos loaded: {last_count}")
        return await page.query_selector_all('ytd-rich-item-renderer')

    async def extract_upload_date_from_video(self, video_url):
        print(f"[DateExtract] Visiting video page: {video_url}")
        page = await self.context.new_page()
        try:
            await page.goto(video_url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(2000)
            # Try to find and click the 'more' button robustly
            try:
                more_btn = None
                try:
                    more_btn = await page.wait_for_selector('tp-yt-paper-button#expand', state='visible', timeout=5000)
                except Exception:
                    pass
                if not more_btn:
                    # Try fallback selector
                    btns = await page.query_selector_all('tp-yt-paper-button')
                    for btn in btns:
                        btn_text = (await btn.text_content() or '').strip().lower()
                        if btn_text == 'more':
                            more_btn = btn
                            break
                if more_btn:
                    is_enabled = True
                    try:
                        is_enabled = await more_btn.is_enabled()
                    except Exception:
                        pass
                    if is_enabled:
                        print("[DateExtract] Clicking 'more' button to expand description...")
                        await more_btn.click()
                        await page.wait_for_timeout(1000)
                    else:
                        print("[DateExtract] 'more' button found but not enabled.")
                else:
                    print("[DateExtract] 'more' button not found. Listing all tp-yt-paper-button texts:")
                    btns = await page.query_selector_all('tp-yt-paper-button')
                    for i, btn in enumerate(btns):
                        btn_text = (await btn.text_content() or '').strip()
                        print(f"  [Button {i+1}] {btn_text}")
            except Exception as e:
                print(f"[DateExtract] Could not click 'more' button: {e}")
            # Wait for the expanded date string to appear (up to 10s)
            found_date = False
            for attempt in range(10):
                candidates = await page.query_selector_all('span.yt-formatted-string')
                for span in candidates:
                    text = (await span.text_content() or '').strip()
                    if any(phrase in text for phrase in ['Streamed live on', 'Premiered on', 'Published on']):
                        found_date = True
                        date_text = text
                        print(f"[DateExtract] Found date string: {date_text}")
                        import re
                        from dateutil.parser import parse as dateparse
                        match = re.search(r'(Streamed live on|Premiered on|Published on) (.+)', date_text)
                        if match:
                            date_part = match.group(2)
                            try:
                                dt = dateparse(date_part)
                                result = dt.strftime('%Y-%m-%d')
                                print(f"[DateExtract] Parsed upload date: {result}")
                                await page.close()
                                return result
                            except Exception as e:
                                print(f"[DateExtract] Failed to parse date: {e}")
                if found_date:
                    break
                await page.wait_for_timeout(1000)
            if not found_date:
                print("[DateExtract] No upload date string found on video page after clicking 'more'. Printing all candidate texts:")
                for i, span in enumerate(candidates):
                    text = (await span.text_content() or '').strip()
                    print(f"  [Candidate {i+1}] {text}")
            await page.close()
            return None
        except Exception as e:
            print(f"[DateExtract] Error visiting video page: {e}")
            await page.close()
            # Wait for any span.yt-formatted-string to appear
            try:
                await page.wait_for_selector('span.yt-formatted-string', timeout=10000)
            except Exception as e:
                print(f"[DateExtract] Timed out waiting for span.yt-formatted-string: {e}")
            # Find the date string
            date_text = None
            date_span = None
            candidates = await page.query_selector_all('span.yt-formatted-string')
            for span in candidates:
                text = (await span.text_content() or '').strip()
                if any(phrase in text for phrase in ['Streamed live on', 'Premiered on', 'Published on']):
                    date_text = text
                    date_span = span
                    break
            if date_text:
                print(f"[DateExtract] Found date string: {date_text}")
                # Extract the date part
                import re
                from dateutil.parser import parse as dateparse
                match = re.search(r'(Streamed live on|Premiered on|Published on) (.+)', date_text)
                if match:
                    date_part = match.group(2)
                    try:
                        dt = dateparse(date_part)
                        result = dt.strftime('%Y-%m-%d')
                        print(f"[DateExtract] Parsed upload date: {result}")
                        await page.close()
                        return result
                    except Exception as e:
                        print(f"[DateExtract] Failed to parse date: {e}")
            else:
                print("[DateExtract] No upload date string found on video page. Printing all candidate texts:")
                for i, span in enumerate(candidates):
                    text = (await span.text_content() or '').strip()
                    print(f"  [Candidate {i+1}] {text}")
            await page.close()
            return None
        except Exception as e:
            print(f"[DateExtract] Error visiting video page: {e}")
            await page.close()
            return None

    async def scrape_youtube_live_meetings(self):
        print(f"\nScraping YouTube Live Meetings from {self.base_url}")
        medias = []
        seen_urls = set()
        page = await self.context.new_page()
        print(f"Navigating to: {self.base_url}")
        await page.goto(self.base_url, wait_until='domcontentloaded', timeout=60000)

        # Incremental scroll to load all videos
        video_items = await self.scroll_to_load_all_youtube_videos(page)
        print(f"[Main] Found {len(video_items)} video items. Beginning extraction...")
        for idx, item in enumerate(video_items):
            print(f"[Main] Processing video {idx+1}/{len(video_items)}...")
            # Get the video link and title
            link_elem = await item.query_selector('a#video-title-link')
            if not link_elem:
                print(f"[Main] Skipping video {idx+1}: No link element found.")
                continue
            href = await link_elem.get_attribute('href')
            title = await link_elem.get_attribute('title') or await link_elem.text_content() or 'YouTube Video'
            title = title.strip()
            if not href:
                print(f"[Main] Skipping video {idx+1}: No href found.")
                continue
            if href.startswith('/'):
                full_url = 'https://www.youtube.com' + href
            else:
                full_url = href
            if full_url in seen_urls:
                print(f"[Main] Skipping video {idx+1}: Duplicate URL.")
                continue
            seen_urls.add(full_url)
            # Visit the video page and extract the upload date
            upload_date = await self.extract_upload_date_from_video(full_url)
            dt = None
            if upload_date:
                try:
                    dt = dateparse(upload_date)
                except Exception:
                    print(f"[Main] Could not parse upload date: {upload_date}")
            # Filter by date range
            add_media = True
            if self.start_date and self.end_date and dt:
                if dt < self.start_date:
                    print(f"[Main] Stopping: found date {dt.strftime('%Y-%m-%d')} before start date {self.start_date.strftime('%Y-%m-%d')}")
                    break
                if not (self.start_date <= dt <= self.end_date):
                    print(f"[Main] Skipping (out of range): {title} | {upload_date}")
                    add_media = False
            if add_media:
                medias.append({
                    "url": full_url,
                    "title": title,
                    "date": upload_date,
                    "source_type": "video"
                })
                print(f"[Main] ✓ Added: {title} | {full_url} | {upload_date}")
        await page.close()
        print(f"\n[Main] Total YouTube Live Meetings found: {len(medias)}")
        return medias 


class RegionalWebTVScraper:
    def __init__(self, context, base_url, start_date=None, end_date=None):
        if start_date is not None and isinstance(start_date, str):
            start_date = dateparse(start_date)
        if end_date is not None and isinstance(end_date, str):
            end_date = dateparse(end_date)
        self.context = context
        self.base_url = base_url
        self.start_date = start_date
        self.end_date = end_date

    async def extract_date_from_title(self, title):
        # Match dates like 2/8/2022, 2-8-2022, 2 8 2022, 02/08/2022, etc.
        date_patterns = [
            r'(\d{1,2})[\/\-\s](\d{1,2})[\/\-\s](\d{2,4})'
        ]
        for pattern in date_patterns:
            match = re.search(pattern, title)
            if match:
                month, day, year = match.groups()
                if len(year) == 2:
                    year = '20' + year  # handle 2-digit years
                try:
                    dt = datetime(int(year), int(month), int(day))
                    return dt.strftime('%Y-%m-%d')
                except Exception:
                    continue
        return None

    async def scroll_to_load_all(self, page, max_scrolls=30, wait_time=2):
        last_count = 0
        for _ in range(max_scrolls):
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(wait_time * 1000)
            # Try the original selector from your screenshot
            cards = await page.query_selector_all('a.w-video-card')
            if len(cards) == last_count:
                break
            last_count = len(cards)
        return await page.query_selector_all('a.w-video-card')

    async def scrape_regional_webtv(self):
        print(f"\nScraping Regional Web TV from {self.base_url}")
        if self.start_date and self.end_date:
            print(f"Filtering videos between {self.start_date.strftime('%Y-%m-%d')} and {self.end_date.strftime('%Y-%m-%d')}")
        medias = []
        seen_urls = set()
        
        try:
            page = await self.context.new_page()
            print(f"Navigating to: {self.base_url}")
            await page.goto(self.base_url, wait_until='domcontentloaded', timeout=60000)
            
            # Wait a bit for dynamic content to load
            await page.wait_for_timeout(3000)
            
            # Look for iframes that contain video content
            iframes = await page.query_selector_all('iframe')
            print(f"Found {len(iframes)} iframes on the page")
            
            video_iframes = []
            for iframe in iframes:
                src = await iframe.get_attribute('src')
                if src and 'filesusr.com/html' in src:
                    video_iframes.append(src)
                    print(f"Found video iframe: {src}")
            
            if not video_iframes:
                print("No video iframes found. Debugging page structure...")
                await self.debug_page_structure(page)
                await page.close()
                return medias
            
            # Process each video iframe
            for iframe_url in video_iframes:
                print(f"\nProcessing iframe: {iframe_url}")
                
                # Create new page for iframe content
                iframe_page = await self.context.new_page()
                try:
                    await iframe_page.goto(iframe_url, wait_until='domcontentloaded', timeout=60000)
                    await iframe_page.wait_for_timeout(2000)  # Wait for content to load
                    
                    # Now look for video cards in the iframe
                    card_elems = await self.scroll_to_load_all(iframe_page)
                    print(f"Found {len(card_elems)} video items in iframe")
                    
                    for card in card_elems:
                        try:
                            href = await card.get_attribute('href')
                            if not href or href in seen_urls:
                                continue
                            
                            # Make href absolute if it's relative
                            if href.startswith('/'):
                                href = f"https://www.regionalwebtv.com{href}"
                            elif not href.startswith('http'):
                                # If relative to iframe domain
                                if href.startswith('../') or not href.startswith('./'):
                                    href = f"https://www-regionalwebtv-com.filesusr.com{href}"
                            
                            seen_urls.add(href)
                            
                            # Try multiple ways to get the title
                            title = None
                            h3 = await card.query_selector('h3')
                            if h3:
                                title = await h3.get_attribute('title') or await h3.text_content()
                            
                            # If no h3, try other elements
                            if not title:
                                title_elem = await card.query_selector('[title]')
                                if title_elem:
                                    title = await title_elem.get_attribute('title')
                            
                            if not title:
                                # Last resort - get any text content
                                title = await card.text_content()
                            
                            if not title:
                                print(f"⚠️  No title found for: {href}")
                                continue
                            
                            title = title.strip()
                            upload_date = await self.extract_date_from_title(title)
                            
                            # Only add if upload_date is within range (if both dates are set and upload_date is valid)
                            add_media = True
                            if self.start_date and self.end_date and upload_date:
                                try:
                                    dt = dateparse(upload_date)
                                    add_media = self.start_date <= dt <= self.end_date
                                except Exception:
                                    add_media = False
                            if add_media:
                                medias.append({
                                    "url": href,
                                    "title": title,
                                    "date": upload_date,
                                    "source_type": "video"
                                })
                                print(f"✓ Added: {title} | {href} | {upload_date}")
                            else:
                                print(f"× Skipped (out of range): {title} | {upload_date}")
                            
                        except Exception as e:
                            print(f"Error processing card: {e}")
                            continue
                    
                except Exception as e:
                    print(f"Error processing iframe {iframe_url}: {e}")
                finally:
                    await iframe_page.close()
            
            await page.close()
            
        except Exception as e:
            print(f"Error in scrape_regional_webtv: {e}")
            if 'page' in locals():
                await page.close()
        
        print(f"\nTotal Regional Web TV videos found: {len(medias)}")
        return medias
    
    async def debug_page_structure(self, page):
        """Debug method to understand the page structure"""
        try:
            print("\n=== PAGE STRUCTURE DEBUG ===")
            
            # Wait for any potential dynamic content
            print("Waiting for dynamic content...")
            await page.wait_for_timeout(5000)  # Wait 5 seconds
            
            # Get page title and URL to confirm we're on the right page
            title = await page.title()
            url = page.url
            print(f"Page Title: {title}")
            print(f"Current URL: {url}")
            
            # Get all links on the page with their attributes
            all_links = await page.query_selector_all('a')
            print(f"\nTotal links found: {len(all_links)}")
            
            print("\nFirst 10 links with their classes and hrefs:")
            for i, link in enumerate(all_links[:10]):
                href = await link.get_attribute('href')
                class_name = await link.get_attribute('class')
                text = await link.text_content()
                print(f"  {i+1}. href='{href}' class='{class_name}' text='{text[:50]}...' if text else 'No text'")
            
            # Look for any elements with common video-related terms
            search_terms = ['video', 'card', 'media', 'content', 'item', 'thumb', 'preview']
            for term in search_terms:
                elements = await page.query_selector_all(f'*[class*="{term}"]')
                if elements:
                    print(f"\nElements with '{term}' in class: {len(elements)}")
                    for i, elem in enumerate(elements[:3]):
                        class_name = await elem.get_attribute('class')
                        tag_name = await elem.evaluate('el => el.tagName')
                        print(f"  {i+1}. <{tag_name.lower()}> class='{class_name}'")
            
            # Get page HTML structure (first 3000 chars)
            html_content = await page.content()
            print(f"\nFirst 3000 characters of page HTML:")
            print("=" * 50)
            print(html_content[:3000])
            print("=" * 50)
            
            # Look for iframes (content might be in iframe)
            iframes = await page.query_selector_all('iframe')
            print(f"\nIframes found: {len(iframes)}")
            for i, iframe in enumerate(iframes):
                src = await iframe.get_attribute('src')
                print(f"  {i+1}. iframe src: {src}")
            
            # Check if page has JavaScript errors or is still loading
            print(f"\nPage ready state: {await page.evaluate('document.readyState')}")
            
            # Try to find any divs that might contain video content
            divs = await page.query_selector_all('div')
            print(f"\nTotal divs found: {len(divs)}")
            
            # Look for divs with specific attributes that might indicate video content
            video_related_divs = []
            for div in divs[:20]:  # Check first 20 divs
                class_name = await div.get_attribute('class') or ''
                id_name = await div.get_attribute('id') or ''
                if any(term in class_name.lower() or term in id_name.lower() 
                       for term in ['video', 'media', 'content', 'grid', 'list', 'item']):
                    video_related_divs.append((div, class_name, id_name))
            
            print(f"\nPotentially relevant divs: {len(video_related_divs)}")
            for i, (div, class_name, id_name) in enumerate(video_related_divs[:5]):
                print(f"  {i+1}. class='{class_name}' id='{id_name}'")
                
        except Exception as e:
            print(f"Error in debug_page_structure: {e}")