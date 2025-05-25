import asyncio
import subprocess
import sys
from playwright.async_api import async_playwright
import re
import json
from urllib.parse import urljoin

# Default test input
MEETING_URLS = [
    "https://www.lansdale.org/CivicMedia.aspx?VID=Work-Session-1242024-262#player",
    "http://detroit-vod.cablecast.tv/CablecastPublicSite/show/14446?site=1",
    "https://www.youtube.com/watch?v=L2zlvczRd6M"
]

def check_with_ytdlp(url):
    try:
        print(f"Checking with yt-dlp: {url}")
        
        # Try different ways to call yt-dlp
        commands_to_try = [
            ["yt-dlp", "--simulate", url],
            [sys.executable, "-m", "yt_dlp", "--simulate", url],
            ["python", "-m", "yt_dlp", "--simulate", url]
        ]
        
        for cmd in commands_to_try:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    print(f"✓ yt-dlp can download: {url}")
                    return True
                elif "ERROR:" in result.stderr:
                    print(f"✗ yt-dlp cannot download: {url}")
                    if result.stderr.strip():
                        print(result.stderr.strip())
                    return False
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"Error with command {cmd[0]}: {e}")
                continue
        
        print("yt-dlp is not installed or not in PATH. Please install yt-dlp and try again.")
        return False
        
    except Exception as e:
        print(f"Error running yt-dlp: {e}")
        return False

def extract_video_info_with_ytdlp(url):
    """Extract video information using yt-dlp"""
    try:
        commands_to_try = [
            ["yt-dlp", "--dump-json", "--no-download", url],
            [sys.executable, "-m", "yt_dlp", "--dump-json", "--no-download", url],
            ["python", "-m", "yt_dlp", "--dump-json", "--no-download", url]
        ]
        
        for cmd in commands_to_try:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0 and result.stdout.strip():
                    video_info = json.loads(result.stdout)
                    return video_info
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            except Exception:
                continue
        
        return None
    except Exception as e:
        print(f"Error extracting video info: {e}")
        return None

async def extract_video_source_url(page, meeting_url):
    print(f"Visiting: {meeting_url}")
    video_requests = []
    video_pattern = re.compile(r"\\.(m3u8|mp4|webm|mov|flv|f4v|m4v|avi|mpg|mpeg|3gp|ogg|ogv|ts)(\\?|$)", re.IGNORECASE)

    def handle_request(request):
        url = request.url
        resource_type = request.resource_type
        # Capture all XHR/fetch requests
        if resource_type in ("xhr", "fetch"):
            print(f"[XHR/FETCH] {url}")
            video_requests.append(url)
        # Also capture by extension
        if video_pattern.search(url):
            print(f"[Network] Video-like URL found: {url}")
            video_requests.append(url)

    page.on('request', handle_request)

    try:
        await page.goto(meeting_url, wait_until='domcontentloaded', timeout=60000)
        
        # Wait for additional content to load
        await page.wait_for_timeout(5000)
        
        # Print all iframe srcs for debugging
        iframes = await page.query_selector_all('iframe')
        iframe_srcs = []
        for idx, iframe in enumerate(iframes):
            src = await iframe.get_attribute('src')
            print(f'Iframe {idx}: {src}')
            if src and src.startswith('http'):
                iframe_srcs.append(src)
        
        # Try to find a <video> tag or <source> tag
        video_src = None
        video_elem = await page.query_selector('video')
        if video_elem:
            video_src = await video_elem.get_attribute('src')
        
        if not video_src:
            source_elem = await page.query_selector('video source')
            if source_elem:
                video_src = await source_elem.get_attribute('src')
        
        # (Optional) Simulate play button click if no video found
        if not video_src:
            play_button = await page.query_selector('button[aria-label="Play"], .play, .vjs-play-control')
            if play_button:
                print("Simulating play button click...")
                await play_button.click()
                await page.wait_for_timeout(3000)
                # Try again to find video src
                video_elem = await page.query_selector('video')
                if video_elem:
                    video_src = await video_elem.get_attribute('src')
                if not video_src:
                    source_elem = await page.query_selector('video source')
                    if source_elem:
                        video_src = await source_elem.get_attribute('src')
        
        # Check inside iframes
        if not video_src:
            for iframe in iframes:
                try:
                    frame = await iframe.content_frame()
                    if frame:
                        # Wait for iframe content to load
                        await frame.wait_for_timeout(2000)
                        
                        video_elem = await frame.query_selector('video')
                        if video_elem:
                            video_src = await video_elem.get_attribute('src')
                            if video_src:
                                break
                        
                        if not video_src:
                            source_elem = await frame.query_selector('video source')
                            if source_elem:
                                video_src = await source_elem.get_attribute('src')
                                if video_src:
                                    break
                except Exception as e:
                    print(f"Error accessing iframe content: {e}")
                    continue
        
        if video_src and not video_src.startswith('http'):
            video_src = urljoin(meeting_url, video_src)
        
        return video_src, iframe_srcs, list(set(video_requests))
    
    finally:
        # Remove the event listener
        try:
            page.remove_listener('request', handle_request)
        except:
            pass

async def process_iframe_for_video_sources(page, iframe_url):
    """Visit iframe and extract video sources"""
    print(f"\n--- Processing iframe: {iframe_url} ---")
    
    try:
        await page.goto(iframe_url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)
        
        # Look for video elements
        video_sources = []
        
        # Direct video elements
        videos = await page.query_selector_all('video')
        for video in videos:
            src = await video.get_attribute('src')
            if src:
                video_sources.append(src)
                print(f"Found video src: {src}")
        
        # Source elements within video tags
        sources = await page.query_selector_all('video source')
        for source in sources:
            src = await source.get_attribute('src')
            if src:
                video_sources.append(src)
                print(f"Found source src: {src}")
        
        # Look for JavaScript variables that might contain video URLs
        js_content = await page.evaluate("""
            () => {
                const scripts = document.querySelectorAll('script');
                let videoUrls = [];
                
                for (let script of scripts) {
                    const content = script.textContent || script.innerText || '';
                    
                    // Look for common video URL patterns
                    const patterns = [
                        /["']([^"']*\.m3u8[^"']*)/gi,
                        /["']([^"']*\.mp4[^"']*)/gi,
                        /["']([^"']*rtmp[^"']*)/gi,
                        /src["\s]*:["\s]*["']([^"']*\.(m3u8|mp4|webm)[^"']*)/gi
                    ];
                    
                    patterns.forEach(pattern => {
                        let match;
                        while ((match = pattern.exec(content)) !== null) {
                            videoUrls.push(match[1]);
                        }
                    });
                }
                
                return videoUrls;
            }
        """)
        
        if js_content:
            for url in js_content:
                if url and url.startswith('http'):
                    video_sources.append(url)
                    print(f"Found video URL in JS: {url}")
        
        return video_sources
        
    except Exception as e:
        print(f"Error processing iframe {iframe_url}: {e}")
        return []

async def main():
    valid_video_urls = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        for meeting_url in MEETING_URLS:
            print(f"\n{'='*60}")
            print(f"Processing: {meeting_url}")
            print(f"{'='*60}")
            
            # Try yt-dlp directly on the meeting page URL
            if check_with_ytdlp(meeting_url):
                valid_video_urls.append(meeting_url)
                continue
            
            # Extract video sources from the page
            video_url, iframe_srcs, network_video_urls = await extract_video_source_url(page, meeting_url)
            
            # Check direct video URL if found
            if video_url and check_with_ytdlp(video_url):
                valid_video_urls.append(video_url)
                continue
            
            # Process each iframe to find video sources
            for iframe_url in iframe_srcs:
                print(f"\n--- Checking iframe with yt-dlp: {iframe_url} ---")
                if check_with_ytdlp(iframe_url):
                    valid_video_urls.append(iframe_url)
                else:
                    # Visit the iframe and look for video sources
                    iframe_video_sources = await process_iframe_for_video_sources(page, iframe_url)
                    for video_src in iframe_video_sources:
                        if check_with_ytdlp(video_src):
                            valid_video_urls.append(video_src)
            
            # Check network-captured video URLs
            for net_url in network_video_urls:
                if check_with_ytdlp(net_url):
                    valid_video_urls.append(net_url)
        
        await page.close()
        await context.close()
        await browser.close()
    
    # Filter valid_video_urls to only include direct video streams or page URLs yt-dlp can download
    def is_video_url(url):
        video_exts = ('.m3u8', '.mp4', '.webm', '.mov', '.flv', '.f4v', '.m4v', '.avi', '.mpg', '.mpeg', '.3gp', '.ogg', '.ogv', '.ts')
        # Exclude subtitle, analytics, JS, and other non-video URLs
        exclude_patterns = [
            '.vtt', '.js', 'google-analytics', 'doubleclick', '/antiforgery', '/Toggle', '/closed-captions/', '/Assets/Scripts/'
        ]
        if any(pattern in url for pattern in exclude_patterns):
            return False
        if url.lower().endswith(video_exts):
            return True
        # Allow YouTube, Vimeo, and similar page URLs
        if any(domain in url for domain in ['youtube.com', 'youtu.be', 'vimeo.com']):
            return True
        return False

    filtered_video_urls = [url for url in valid_video_urls if is_video_url(url)]

    print(f"\n{'='*60}")
    print("RESULTS:")
    print(f"{'='*60}")
    if filtered_video_urls:
        print("Valid downloadable video URLs:")
        for i, url in enumerate(filtered_video_urls, 1):
            print(f"{i}. {url}")
    else:
        print("No valid downloadable video URLs found.")

if __name__ == "__main__":
    asyncio.run(main())