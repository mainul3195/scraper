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
        """Aggressive scrolling to load all 100 videos"""
        print(f"Starting to scroll and load video content (target: {target_count} videos)...")
        last_count = 0
        consecutive_no_change = 0
        max_no_change = 15  # Increased patience
        
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
                    
                    # Final desperate attempt - try different scroll positions
                    print("Attempting final scroll techniques...")
                    for i in range(5):
                        await page.evaluate(f'window.scrollTo(0, document.body.scrollHeight * {0.7 + i * 0.1})')
                        await page.wait_for_timeout(3000)
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        await page.wait_for_timeout(3000)
                        
                        new_cards = await page.query_selector_all('div.x9f619.x1r8uery.x1iyjqo2.x6ikm8r.x10wlt62.x1n2onr6')
                        if len(new_cards) > current_count:
                            print(f"Final technique worked! Found {len(new_cards)} cards")
                            current_count = len(new_cards)
                            consecutive_no_change = 0
                            break
                    
                    if consecutive_no_change >= max_no_change * patience_multiplier:
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
        
        # Wait for cards to have actual content
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
            if loaded_count >= current_count * 0.7:  # 70% of cards have content
                break
        
        final_cards = await page.query_selector_all('div.x9f619.x1r8uery.x1iyjqo2.x6ikm8r.x10wlt62.x1n2onr6')
        final_count = len(final_cards)
        
        print(f"Final count: {final_count} video cards loaded")
        
        if final_count < target_count:
            print(f"⚠️  Only found {final_count} cards out of expected {target_count}")
            print("This could be due to:")
            print("- Facebook's rate limiting")
            print("- Authentication requirements") 
            print("- Changed page structure")
            print("- Network issues")
        
        return final_cards

    async def extract_video_info_from_card(self, card, card_index):
        """Enhanced video info extraction with better error handling"""
        try:
            video_info = {
                "url": None,
                "title": None,
                "date": None,
                "source_type": "video"
            }
            
            # Wait a moment for the card to be fully rendered
            await card.wait_for_timeout(500)
            
            # Get card HTML for debugging
            try:
                card_html = await card.inner_html()
                if len(card_html.strip()) < 100:  # Very minimal content
                    print(f"DEBUG - Card {card_index}: Minimal content ({len(card_html)} chars)")
            except:
                card_html = "Unable to get HTML"
            
            # Enhanced URL extraction strategies
            found_href = None
            
            # Strategy 1: Look for direct video links first
            try:
                video_links = await card.query_selector_all('a[href*="/videos/"]')
                if video_links:
                    href = await video_links[0].get_attribute('href')
                    if href:
                        found_href = href
                        print(f"DEBUG - Card {card_index}: Found direct video link")
            except:
                pass
            
            # Strategy 2: Look for any Facebook links that might be videos
            if not found_href:
                try:
                    all_links = await card.query_selector_all('a[href]')
                    for link in all_links:
                        href = await link.get_attribute('href')
                        if href and any(pattern in href for pattern in ['/videos/', '/watch/', '/reel/']):
                            found_href = href
                            print(f"DEBUG - Card {card_index}: Found video-related link")
                            break
                except:
                    pass
            
            # Strategy 3: Look for any meaningful links
            if not found_href:
                try:
                    all_links = await card.query_selector_all('a[href]')
                    for link in all_links:
                        href = await link.get_attribute('href')
                        if href and href not in ['#', 'javascript:void(0)'] and len(href) > 10:
                            # Check if it's a Facebook post/content link
                            if 'facebook.com' in href or href.startswith('/'):
                                found_href = href
                                break
                except:
                    pass
            
            # Format URL
            if found_href:
                if found_href.startswith('/'):
                    video_info["url"] = f"https://www.facebook.com{found_href}"
                elif found_href.startswith('http'):
                    video_info["url"] = found_href
                else:
                    video_info["url"] = f"https://www.facebook.com/{found_href}"
            
            # Enhanced title extraction
            title = None
            
            # Strategy 1: Look for aria-labels with meaningful content
            try:
                elements_with_aria = await card.query_selector_all('[aria-label]')
                for element in elements_with_aria:
                    aria_label = await element.get_attribute('aria-label')
                    if aria_label and len(aria_label.strip()) > 15:
                        # Skip common UI elements
                        skip_words = ['like', 'share', 'comment', 'play', 'pause', 'video player']
                        if not any(word in aria_label.lower() for word in skip_words):
                            title = aria_label.strip()
                            break
            except:
                pass
            
            # Strategy 2: Look for spans with substantial text content
            if not title:
                try:
                    text_spans = await card.query_selector_all('span')
                    longest_text = ""
                    for span in text_spans:
                        text = await span.text_content()
                        if text and len(text.strip()) > len(longest_text) and len(text.strip()) > 15:
                            # Skip if it's just numbers or common UI text
                            if not text.strip().isdigit() and 'ago' not in text.lower():
                                longest_text = text.strip()
                    if longest_text:
                        title = longest_text
                except:
                    pass
            
            # Strategy 3: Extract from any text content
            if not title:
                try:
                    all_text = await card.text_content()
                    if all_text:
                        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                        for line in lines:
                            if len(line) > 20 and not line.isdigit():
                                # Look for lines that seem like titles
                                if any(word in line.lower() for word in ['meeting', 'county', 'commission', 'workshop', 'townhall']):
                                    title = line
                                    break
                        # Fallback to longest line if no keyword match
                        if not title and lines:
                            title = max(lines, key=len)
                except:
                    pass
            
            # Fallback title
            if not title:
                title = "Facebook Video"
            
            video_info["title"] = title
            
            # Debug output for problematic cards
            if not video_info["url"]:
                print(f"DEBUG - Card {card_index}: No URL found")
                print(f"  └─ HTML preview: {card_html[:300]}...")
            
            return video_info
            
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
            
            print(f"Navigating to: {self.base_url}")
            await page.goto(self.base_url, wait_until='networkidle', timeout=90000)
            
            # Wait for initial page load
            await page.wait_for_timeout(8000)
            
            # Check for and handle common Facebook overlays
            try:
                # Handle cookie consent
                cookie_buttons = await page.query_selector_all('[data-testid="cookie-policy-manage-dialog"] button, [data-cookiebanner="accept_button"]')
                if cookie_buttons:
                    await cookie_buttons[0].click()
                    await page.wait_for_timeout(2000)
                    print("Handled cookie consent")
            except:
                pass
            
            # Verify main content is loaded
            try:
                await page.wait_for_selector('[role="main"], div[data-pagelet="ProfileTimeline"]', timeout=15000)
                print("Page main content detected")
            except:
                print("Warning: Main content selector not found, proceeding anyway...")
            
            # Enhanced scroll and load - targeting 100 videos
            video_cards = await self.scroll_to_load_all_videos(page, target_count=100)
            
            if not video_cards:
                print("No video cards found.")
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