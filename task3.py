import yt_dlp
import sys
import os
from pathlib import Path

# Test with a simple working URL first
TEST_URLS = [
    # Test with a simple YouTube video first to verify setup
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ',  # Short test video
    
    # Then try your extracted URLs
    'https://multnomah.granicus.com/MediaPlayer.php?view_id=3&clip_id=3097',
    'https://cityofalhambraorg-my.sharepoint.com/:v:/g/personal/lmyles_alhambraca_gov/ETs6K1euPsBClaWtczJXl-gB47R9yoz9o9FJYZuEY0KOjA?e=7B41Fy',
]

def test_url_accessibility(url):
    """Test if URL is accessible before downloading"""
    print(f"Testing URL accessibility: {url}")
    
    test_opts = {
        'quiet': True,
        'no_warnings': True,
        'simulate': True,  # Don't actually download
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(test_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown')
            print(f"✓ URL accessible: {title}")
            return True, title
    except Exception as e:
        print(f"✗ URL not accessible: {e}")
        return False, str(e)

def check_aria2c():
    """Check if aria2c is available"""
    import subprocess
    try:
        result = subprocess.run(['aria2c', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"✓ aria2c found: {version}")
            return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    print("✗ aria2c not found")
    print("Install with: brew install aria2")
    return False

def download_single_video(url, use_aria2c=True):
    """Download a single video with or without aria2c"""
    
    base_opts = {
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'noplaylist': True,
        'format': 'best[ext=mp4]/best',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        },
    }
    
    if use_aria2c:
        base_opts.update({
            'external_downloader': 'aria2c',
            'external_downloader_args': [
                '--max-connection-per-server=8',
                '--split=8', 
                '--min-split-size=1M',
                '--max-tries=5',
                '--retry-wait=3',
                '--timeout=30',
                '--console-log-level=warn',
            ],
        })
        print("Using aria2c for faster downloads")
    else:
        print("Using standard yt-dlp downloader")
    
    try:
        with yt_dlp.YoutubeDL(base_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        return False

def main():
    print("=== Video Downloader Test ===\n")
    
    # Create downloads directory
    Path('downloads').mkdir(exist_ok=True)
    
    # Check aria2c availability
    has_aria2c = check_aria2c()
    print()
    
    for i, url in enumerate(TEST_URLS, 1):
        print(f"\n--- Testing URL {i}/{len(TEST_URLS)} ---")
        print(f"URL: {url}")
        
        # Test accessibility first
        accessible, info = test_url_accessibility(url)
        
        if not accessible:
            print(f"Skipping inaccessible URL: {info}")
            continue
        
        # Try to download
        print(f"Attempting download...")
        success = download_single_video(url, use_aria2c=has_aria2c)
        
        if success:
            print("✓ Download completed successfully!")
        else:
            print("✗ Download failed")
            
            # If aria2c failed, try without it
            if has_aria2c:
                print("Retrying without aria2c...")
                success = download_single_video(url, use_aria2c=False)
                if success:
                    print("✓ Download completed with fallback!")

if __name__ == "__main__":
    main()