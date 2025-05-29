import yt_dlp
import sys
import os
from pathlib import Path
import subprocess

# Test URLs
TEST_URLS = [
    'https://uhsakamai-a.akamaihd.net/sjc/omega/vod/us1-32bc453c-41ae-43b7-bfb7-ba5bf80ef384/19598040000/10582010208000/plain/rfc/8/chunk_2_1870599898.m4a'
    # 'https://video.ibm.com/recorded/134312408'
]

def check_aria2c():
    """Check if aria2c is available"""
    try:
        result = subprocess.run(['aria2c', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"✓ aria2c found: {version}")
            return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    print("✗ aria2c not found")
    print("Install with: brew install aria2 (macOS) or apt install aria2 (Ubuntu)")
    return False

def list_available_formats(url):
    """List available formats for a URL"""
    print(f"\nChecking available formats for: {url}")
    
    opts = {
        'quiet': False,
        'no_warnings': False,
        'listformats': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        print(f"Error listing formats: {e}")
        return None

def test_url_accessibility(url):
    """Test if URL is accessible and get basic info"""
    print(f"Testing URL accessibility: {url}")
    
    test_opts = {
        'quiet': True,
        'no_warnings': True,
        'simulate': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(test_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)
            print(f"✓ URL accessible: {title}")
            if duration:
                # Handle float duration values
                duration = int(duration) if duration else 0
                if duration > 0:
                    print(f"  Duration: {duration//60}:{duration%60:02d}")
            return True, title, info
    except Exception as e:
        print(f"✗ URL not accessible: {e}")
        return False, str(e), None

def download_video_with_aria2c(url, use_aria2c=True):
    """Download video with optimized settings"""
    
    # More flexible format selection
    base_opts = {
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'noplaylist': True,
        # Try multiple format options in order of preference
        'format': 'best[height<=1080]/best[height<=720]/best',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        },
        'verbose': True,  # Enable verbose output to see what's happening
    }
    
    if use_aria2c:
        base_opts.update({
            'external_downloader': 'aria2c',
            'external_downloader_args': [
                '--max-connection-per-server=16',  # Increased connections
                '--split=16',                      # More splits for faster download
                '--min-split-size=1M',
                '--max-tries=10',                  # More retries
                '--retry-wait=2',
                '--timeout=60',                    # Longer timeout
                '--connect-timeout=30',
                '--console-log-level=warn',
                '--summary-interval=10',           # Progress updates
                '--download-result=hide',
                '--disable-ipv6=true',             # Sometimes helps with connectivity
            ],
        })
        print("🚀 Using aria2c for accelerated downloads")
    else:
        print("📥 Using standard yt-dlp downloader")
    
    try:
        with yt_dlp.YoutubeDL(base_opts) as ydl:
            print(f"Starting download...")
            ydl.download([url])
        return True
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False

def download_with_fallback_formats(url, use_aria2c=True):
    """Try downloading with different format options"""
    
    # List of format options to try, from best to most compatible
    format_options = [
        'best[height<=1080][ext=mp4]/best[height<=1080]',
        'best[height<=720][ext=mp4]/best[height<=720]', 
        'best[ext=mp4]/best',
        'worst[ext=mp4]/worst',
        'best/worst'  # Last resort - any available format
    ]
    
    for i, fmt in enumerate(format_options, 1):
        print(f"\n🔄 Attempt {i}/{len(format_options)} with format: {fmt}")
        
        opts = {
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'noplaylist': True,
            'format': fmt,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            },
        }
        
        if use_aria2c:
            opts.update({
                'external_downloader': 'aria2c',
                'external_downloader_args': [
                    '--max-connection-per-server=16',
                    '--split=16',
                    '--min-split-size=1M',
                    '--max-tries=10',
                    '--retry-wait=2',
                    '--timeout=60',
                    '--connect-timeout=30',
                    '--console-log-level=warn',
                    '--disable-ipv6=true',
                ],
            })
        
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            print(f"✅ Download successful with format: {fmt}")
            return True
        except Exception as e:
            print(f"❌ Failed with format '{fmt}': {str(e)[:100]}...")
            continue
    
    return False

def main():
    print("🎥 === Advanced Video Downloader with aria2c ===\n")
    
    # Create downloads directory
    downloads_dir = Path('downloads')
    downloads_dir.mkdir(exist_ok=True)
    print(f"📁 Downloads will be saved to: {downloads_dir.absolute()}")
    
    # Check aria2c availability
    has_aria2c = check_aria2c()
    print()
    
    for i, url in enumerate(TEST_URLS, 1):
        print(f"\n{'='*60}")
        print(f"📺 Processing Video {i}/{len(TEST_URLS)}")
        print(f"🔗 URL: {url}")
        print(f"{'='*60}")
        
        # Test accessibility first
        accessible, info, metadata = test_url_accessibility(url)
        
        if not accessible:
            print(f"⚠️  Skipping inaccessible URL: {info}")
            continue
        
        # Skip format listing to avoid potential issues
        # print(f"\n📋 Checking available formats...")
        # list_available_formats(url)
        
        # Try download with fallback formats
        print(f"\n🚀 Starting download process...")
        success = download_with_fallback_formats(url, use_aria2c=has_aria2c)
        
        if success:
            print(f"\n🎉 Download completed successfully!")
        else:
            print(f"\n💔 All download attempts failed")
            
            # Final fallback without aria2c if it was being used
            if has_aria2c:
                print(f"\n🔄 Final attempt without aria2c...")
                success = download_with_fallback_formats(url, use_aria2c=False)
                if success:
                    print(f"✅ Download completed with fallback method!")
                else:
                    print(f"❌ All methods exhausted")
    
    print(f"\n🏁 Process completed!")
    
    # Show downloaded files
    download_files = list(downloads_dir.glob('*'))
    if download_files:
        print(f"\n📂 Downloaded files:")
        for file in download_files:
            size_mb = file.stat().st_size / (1024 * 1024)
            print(f"  📄 {file.name} ({size_mb:.1f} MB)")
    else:
        print(f"\n📭 No files downloaded")

if __name__ == "__main__":
    main()