import asyncio
import subprocess
import sys
import json
import re
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright

# Test URLs from the problem
TEST_URLS = [
    "https://video.ibm.com/recorded/134312408"
]

def test_with_ytdlp(url):
    """Test if URL is downloadable with yt-dlp"""
    try:
        for cmd in [["yt-dlp", "--simulate", url], [sys.executable, "-m", "yt_dlp", "--simulate", url]]:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    print(f"✓ Valid: {url}")
                    return True
                elif "ERROR:" in result.stderr:
                    print(f"✗ Invalid: {url} - {result.stderr.strip()}")
                    return False
            except FileNotFoundError:
                continue
        print("yt-dlp not found")
        return False
    except Exception as e:
        print(f"Error testing {url}: {e}")
        return False

def get_ytdlp_info(url):
    """Get video info from yt-dlp if available"""
    try:
        for cmd in [["yt-dlp", "--dump-json", "--no-download", url], [sys.executable, "-m", "yt_dlp", "--dump-json", "--no-download", url]]:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0 and result.stdout.strip():
                    return json.loads(result.stdout)
            except (FileNotFoundError, json.JSONDecodeError):
                continue
        return None
    except Exception:
        return None

async def extract_video_urls(page, url):
    """Extract video URLs from a webpage using multiple strategies"""
    print(f"\n{'='*50}")
    print(f"Processing: {url}")
    print(f"{'='*50}")
    
    # Strategy 1: Try yt-dlp directly on the page URL first
    if test_with_ytdlp(url):
        print(f"✓ Main URL is directly supported by yt-dlp: {url}")
        return [url]  # Return the main URL if it works
    
    video_urls = set()
    
    # Set up network monitoring for video requests
    video_patterns = [
        r'\.m3u8(\?|$)',
        r'\.mp4(\?|$)', 
        r'\.webm(\?|$)',
        r'\.mov(\?|$)',
        r'\.flv(\?|$)',
        r'\.ts(\?|$)',
        r'/playlist\.m3u8',
        r'/master\.m3u8',
        r'stream\.m3u8',
        r'\.mpd(\?|$)',  # DASH
        r'rtmp://',
        r'rtmps://'
    ]
    
    def handle_request(request):
        req_url = request.url
        # Check for video-like URLs in network requests
        for pattern in video_patterns:
            if re.search(pattern, req_url, re.IGNORECASE):
                print(f"[Network] Found video URL: {req_url}")
                video_urls.add(req_url)
    
    page.on('request', handle_request)
    
    try:
        # Load the page with better error handling
        await page.goto(url, wait_until='domcontentloaded', timeout=45000)
        await page.wait_for_timeout(3000)
        
        # Strategy 2: Look for video elements and their sources
        videos = await page.query_selector_all('video')
        for video in videos:
            src = await video.get_attribute('src')
            if src:
                full_url = urljoin(url, src) if not src.startswith('http') else src
                print(f"[Video Element] Found: {full_url}")
                video_urls.add(full_url)
        
        # Look for source elements
        sources = await page.query_selector_all('video source, source')
        for source in sources:
            src = await source.get_attribute('src')
            if src:
                full_url = urljoin(url, src) if not src.startswith('http') else src
                print(f"[Source Element] Found: {full_url}")
                video_urls.add(full_url)
        
        # Strategy 3: Check iframes for embeds
        iframes = await page.query_selector_all('iframe')
        iframe_urls = []
        for iframe in iframes:
            src = await iframe.get_attribute('src')
            if src and src.startswith('http'):
                iframe_urls.append(src)
                print(f"[Iframe] Found: {src}")
        
        # Test iframe URLs with yt-dlp
        for iframe_url in iframe_urls:
            if test_with_ytdlp(iframe_url):
                print(f"✓ Iframe URL is valid: {iframe_url}")
                video_urls.add(iframe_url)
        
        # Strategy 4: Extract video URLs from JavaScript
        js_video_urls = await page.evaluate(r"""
            () => {
                const videoUrls = new Set();
                const scripts = document.querySelectorAll('script');
                
                // Common video URL patterns in JS
                const patterns = [
                    /["']([^"']*\.m3u8[^"']*)/gi,
                    /["']([^"']*\.mp4[^"']*)/gi,
                    /["']([^"']*\.webm[^"']*)/gi,
                    /["']([^"']*stream[^"']*)/gi,
                    /src[\\s]*:[\\s]*["']([^"']*\.(m3u8|mp4|webm)[^"']*)/gi,
                    /url[\\s]*:[\\s]*["']([^"']*\.(m3u8|mp4|webm)[^"']*)/gi,
                    /file[\\s]*:[\\s]*["']([^"']*\.(m3u8|mp4|webm)[^"']*)/gi
                ];
                
                scripts.forEach(script => {
                    const content = script.textContent || script.innerText || '';
                    
                    patterns.forEach(pattern => {
                        let match;
                        while ((match = pattern.exec(content)) !== null) {
                            let url = match[1] || match[0];
                            url = url.replace(/\\\//g, '/');
                            if (url && (url.startsWith('http') || url.startsWith('//'))) {
                                videoUrls.add(url.startsWith('//') ? 'https:' + url : url);
                            }
                        }
                    });
                });
                
                return Array.from(videoUrls);
            }
        """)
        
        for js_url in js_video_urls:
            print(f"[JavaScript] Found: {js_url}")
            video_urls.add(js_url)
        
        # Strategy 5: Look for download links
        download_links = await page.query_selector_all('a[href*="download"], a[href*="stream"], a[href*="video"]')
        for link in download_links:
            href = await link.get_attribute('href')
            if href and any(ext in href.lower() for ext in ['.mp4', '.m3u8', '.webm', 'download', 'stream']):
                full_url = urljoin(url, href) if not href.startswith('http') else href
                print(f"[Download Link] Found: {full_url}")
                video_urls.add(full_url)
        
        # Strategy 6: Try clicking play buttons to trigger video loading
        play_buttons = await page.query_selector_all(
            'button[aria-label*="play" i], button[aria-label*="Play" i], '
            '.play-button, .vjs-play-control, [class*="play"]:not([class*="playlist"]), [id*="play"]'
        )
        
        if play_buttons:
            print(f"Found {len(play_buttons)} potential play buttons, trying to click...")
            for i, button in enumerate(play_buttons[:2]):
                try:
                    is_visible = await button.is_visible()
                    is_enabled = await button.is_enabled()
                    
                    if is_visible and is_enabled:
                        await button.click(timeout=5000)
                        await page.wait_for_timeout(3000)
                        print(f"Clicked play button {i+1}")
                        break
                except Exception as e:
                    print(f"Could not click play button {i+1}: {str(e)[:100]}...")
                    continue
        
        # Wait for any additional content to load
        await page.wait_for_timeout(2000)
        
    except Exception as e:
        print(f"Error processing {url}: {e}")
    
    finally:
        try:
            page.remove_listener('request', handle_request)
        except:
            pass
    
    return list(video_urls)

def filter_and_test_urls(urls):
    """Filter URLs and test them with yt-dlp"""
    valid_urls = []
    exclude_patterns = [
        '.vtt', '.js', '.css', '.png', '.jpg', '.gif', '.svg', '.ico',
        'analytics', 'tracking', 'antiforgery', 'csrf', 'facebook.com',
        'assets/scripts', 'jquery', 'bootstrap', 'trustarc.com'
    ]
    
    for url in urls:
        # Skip obviously non-video URLs
        if any(pattern in url.lower() for pattern in exclude_patterns):
            continue
        
        # Test with yt-dlp
        if test_with_ytdlp(url):
            valid_urls.append(url)
    
    return valid_urls

async def main():
    """Main function to process all URLs"""
    all_valid_urls = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        for url in TEST_URLS:
            try:
                # Get all potential video URLs
                found_urls = await extract_video_urls(page, url)
                
                # Filter and test each URL
                valid_urls = filter_and_test_urls(found_urls)
                all_valid_urls.extend(valid_urls)
                        
            except Exception as e:
                print(f"Error processing {url}: {e}")
        
        await browser.close()
    
    # Print results
    print(f"\n{'='*60}")
    print("FINAL RESULTS:")
    print(f"{'='*60}")
    
    if all_valid_urls:
        # Remove duplicates while preserving order
        unique_urls = []
        seen = set()
        for url in all_valid_urls:
            if url not in seen:
                unique_urls.append(url)
                seen.add(url)
        
        print("Valid downloadable video URLs:")
        for i, url in enumerate(unique_urls, 1):
            print(f"{i}. {url}")
        
        print(f"\nJSON Output:")
        print(json.dumps(unique_urls, indent=2))
        
        return unique_urls
    else:
        print("No valid downloadable video URLs found.")
        return []

if __name__ == "__main__":
    result = asyncio.run(main())