import yt_dlp
import sys

# List of video URLs to download (replace with your own or load from a file)
VIDEO_URLS = [
    # Example URLs
    'https://www.youtube.com/watch?v=L2zlvczRd6M'
    'https://reflect-detroit-vod.cablecast.tv/store-8/14446-Detroit-City-Council-Rules-Committee-05-23-2025-v1/vod.m3u8',
    # Add more URLs as needed
]

def download_with_aria2c(url):
    ydl_opts = {
        'external_downloader': 'aria2c',
        'external_downloader_args': [
            '--max-connection-per-server=16',
            '--split=16',
            '--min-split-size=1M',
            '--max-tries=10',
            '--retry-wait=5',
            '--timeout=60',
            '--summary-interval=0',
            '--console-log-level=warn',
        ],
        'outtmpl': '%(title)s.%(ext)s',
        'noplaylist': True,
        'quiet': False,
        'progress_with_newline': True,
        'retries': 5,
        'continuedl': True,
    }
    print(f"\n=== Downloading: {url} ===")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        print(f"Error downloading {url}: {e}")

def main():
    for url in VIDEO_URLS:
        download_with_aria2c(url)

if __name__ == "__main__":
    main() 