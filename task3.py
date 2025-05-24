import yt_dlp
import sys

# List of video URLs to download (replace with your own or load from a file)
VIDEO_URLS = [
    # Example URLs
    'https://wms.civplus.tikiliveapi.com/vodhttporigin_civplustest/155443/smil:civplustest/encoded_streams/1/1370/155443.smil/playlist.m3u8?p=vodcdn&chid=93139&ts_chunk_length=6&op_id=1&userId=0&videoId=155443&stime=1748107934&etime=1748194334&token=01d5cdfae3becbb5e7ff0&ip=103.84.158.72&ua=Mozilla%252F5.0%2B%2528Windows%2BNT%2B10.0%253B%2BWin64%253B%2Bx64%2529%2BAppleWebKit%252F537.36%2B%2528KHTML%252C%2Blike%2BGecko%2529%2BChrome%252F120.0.0.0%2BSafari%252F537.36&live=0&avod=1&app_bundle=tikilive.webDevice&domain=civplus.tikiliveapi.com&app_id=0&app_name=TikiLIVE%2BHTML5%2BWeb%2BDevice&cb=1748107570&ccpa=1---&consent=0&device_type=&did=&gdpr=0&h=1080&w=720&livestream=0&min_ad_duration=5&max_ad_duration=30&site_domain=https%3A%2F%2Fcivplus.tikiliveapi.com%2F&site_name=Civic+Plus+-+Tikilive+API+10.0.0&hls_marker=1&debug=true&gender=&age=&content_genre=&content_id=155443&content_title=1267%2B-%2BWork%2BSession%2B12.4.2024&network_name=pa-lansdaleborough&content_owner=1370&viewing_user=guest&oid=1&bid=1370',
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