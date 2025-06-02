# 🧠 Meeting Video Scraper

This repository provides a robust, modular system for scraping and downloading public meeting videos from a variety of platforms. It is designed to be scalable, efficient, and easy to use for both metadata collection and high-speed video downloads.

---

## 📦 Features
- **Problem 1:** Scrape meeting metadata (title, date, link, etc.) from public video directories over a date range.
- **Problem 2:** Extract direct, downloadable video URLs from meeting pages, verifying with `yt-dlp`.
- **Bonus:** Download videos at high speed using `yt-dlp` with `aria2c` as an external downloader.
- **Tricky Tasks Included:**
  - Audio/video stream merging (e.g., IBM Video)
  - Downloading m3u8 streams with custom headers/cookies (high-security sites)
- Modular, reusable code ready for scale.
- Outputs clean, structured JSON for easy database ingestion.

---

## 🛠️ Requirements
- Python 3.8+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [aria2c](https://aria2.github.io/)
- [playwright](https://playwright.dev/python/) (`pip install playwright`)
- [requests](https://pypi.org/project/requests/) (if used in Problem 1)
- [selenium](https://pypi.org/project/selenium/) and [webdriver-manager](https://pypi.org/project/webdriver-manager/) (for Winchester CivicWeb)
- Run `playwright install` after installing the package.

Install dependencies:
```bash
pip install yt-dlp playwright requests selenium webdriver-manager beautifulsoup4
playwright install
```

---

## 🚀 Usage

### 1️⃣ Problem 1: Scraping Meeting Metadata
- **Script:** `problem1.py`
- **Input:** JSON with `start_date`, `end_date`, and `base_urls` (see `input.json`).
- **Output:** Structured JSON with all matching meeting metadata (see `output.json`).

**Supported scrapers:**
- [Detroit Cablecast PublicSite](http://detroit-vod.cablecast.tv/CablecastPublicSite) (**fully implemented**)
- [Lansdale CivicMedia](https://www.lansdale.org/CivicMedia?CID=2024-Council-Meetings-26) (**fully implemented**)
- [YouTube Live Meetings](https://www.youtube.com/@SLCLiveMeetings/streams) (**fully implemented**)
- [Regional Web TV](https://www.regionalwebtv.com/fredcc) (**fully implemented**)
- [Facebook Videos](https://www.facebook.com/DauphinCountyPA/videos) (**video scraping implemented, date filtering not supported**)
- [Charleston CivicClerk](https://charlestonwv.portal.civicclerk.com/) (**PDFs, fully implemented**)
- [Winchester CivicWeb](https://winchesterva.civicweb.net/portal/) (**fully implemented: videos & documents**)

**Winchester CivicWeb Scraper:**
> The Winchester CivicWeb scraper is now fully implemented. It can scrape both video and document (agenda/minutes) links successfully, with proper date range filtering. For simplicity, Selenium is used instead of Playwright for this site. See the `WinchesterVAScraper` class in `scrapers.py`.

**Facebook Scraper:**
> The Facebook video scraper is implemented and can collect all video links and titles from the given public Facebook video page. **However, it cannot extract upload dates, so filtering by start and end date is not supported.**

**PDF Scrapers:**
> The Charleston CivicClerk and Winchester CivicWeb scrapers both scrape PDFs (such as agendas, packets, and minutes) from their respective websites.

**Input Example:**
```json
{
    "start_date": "2025-05-28",
    "end_date": "2025-06-02",
    "base_urls": [
        "https://charlestonwv.portal.civicclerk.com/",
        "https://winchesterva.civicweb.net/portal/"
    ]
}
```

**Output Example:**
```json
[
  {
    "base_url": "https://charlestonwv.portal.civicclerk.com/",
    "medias": [
      {
        "url": "https://charlestonwv.api.civicclerk.com/v1/Meetings/GetMeetingFileStream(fileId=7420,plainText=false)",
        "title": "Firemen's Pension Board 5-29-2025 agenda",
        "date": "2025-05-29",
        "source_type": "pdf"
      }
    ]
  },
  {
    "base_url": "https://winchesterva.civicweb.net/portal/",
    "medias": [
      {
        "url": "https://winchesterva.civicweb.net/document/337470",
        "title": "City Council - Strategic Planning Committee - 3:00 PM - Jun 02 2025",
        "date": "2025-06-02",
        "source_type": "document"
      },
      {
        "url": "https://winchesterva.civicweb.net/document/337337",
        "title": "City Council - Planning and Economic Development Committee - 1:00 PM - May 29 2025",
        "date": "2025-05-29",
        "source_type": "document"
      },
      {
        "url": "https://winchesterva.new.swagit.com/videos/344309?ts=0",
        "title": "City Council - Planning and Economic Development Committee - 1:00 PM - May 29 2025",
        "date": "2025-05-29",
        "source_type": "video"
      },
      {
        "url": "https://winchesterva.civicweb.net/document/337115",
        "title": "Community Policy & Management Team - 3:00 PM - May 28 2025",
        "date": "2025-05-28",
        "source_type": "document"
      }
    ]
  }
]
```

**Run:**
```bash
python problem1.py
```

---

### 2️⃣ Problem 2: Video Download URL Resolution
- **Script:** `problem2.py`
- **Input:** List of meeting URLs (from Problem 1 output).
- **Output:** List of direct video URLs that are downloadable with `yt-dlp`.

**How it works:**
- Visits each meeting page using Playwright.
- Extracts direct video sources (from HTML, iframes, and network requests).
- Verifies each candidate URL with `yt-dlp --simulate`.
- Outputs only valid, downloadable video URLs.
- Handles special cases for highly protected or embedded streams.

**Run:**
```bash
python problem2.py
```
- Edit the list of URLs in the script as needed.

---

### 💡 Bonus: Faster Downloads with aria2c
- **Script:** `bonus.py`
- **Input:** List of direct video URLs (from Problem 2 output).
- **Output:** Downloads videos at high speed using `yt-dlp` + `aria2c`.

**How it works:**
- Uses the `yt-dlp` Python API with `aria2c` as the external downloader.
- Configures `aria2c` for multi-threaded, split, and robust retry downloads.
- Falls back to standard yt-dlp if aria2c is not available.

**Run:**
```bash
python bonus.py
```
- Edit the list of URLs in the script as needed.

---

### 🧩 Special/Tricky Tasks

#### tricky_task_1.py
- **Problem:** Some sites (e.g., IBM Video) provide audio and video streams separately.
- **Solution:**
  - Use `yt-dlp --list-formats` to find the best video-only and audio-only formats.
  - Download them separately:
    ```bash
    yt-dlp -f <video_format_id> -o video_only.mp4 <url>
    yt-dlp -f <audio_format_id> -o audio_only.mp4 <url>
    ```
  - Merge them using ffmpeg:
    ```bash
    ffmpeg -i video_only.mp4 -i audio_only.mp4 -c copy -map 0:v:0 -map 1:a:0 final_output.mp4
    ```
- See the script for an automated example.

#### tricky_task_2.py
- **Problem:** Some sites require custom headers and cookies to download m3u8 streams (high security).
- **Solution:**
  - Use Playwright to capture the m3u8 URL and all request headers/cookies.
  - Build a `yt-dlp` command with `--add-header` for each required header.
  - Example output from the script:
    ```bash
    yt-dlp --add-header "cookie: ..." --add-header "user-agent: ..." --add-header "referer: ..." "<m3u8_url>"
    ```
- See the script for a working example.

---

## 🔗 Full Pipeline Example
1. **Scrape metadata:**
    - `python problem1.py`
2. **Extract direct video URLs:**
    - Copy URLs from `output.json` to the input for `problem2.py`.
    - `python problem2.py`
3. **Download videos at high speed:**
    - Copy URLs from the output of `problem2.py` to the input for `bonus.py`.
    - `python bonus.py`

---

## 🧩 Modularity & Scaling
- Each task is a standalone script, but functions can be imported and reused.
- Output is always clean, structured JSON for easy database ingestion.
- Designed to be robust against edge cases and varied website structures.

---

## 📝 Notes
- For best results, always use the latest version of `yt-dlp` and `aria2c`.
- Some sites may require additional handling (e.g., login, cookies, or advanced scraping logic).
- **Facebook video extraction can collect all video links and titles, but cannot extract upload dates, so filtering by date is not supported.**
- **All 6 classes for test data in problem1.py are implemented and working, except for Facebook date extraction.**
- **Both tricky tasks are also accomplished successfully.**
- You can further automate the pipeline by combining the scripts or using a workflow manager.

---

## 🏅 Bonus Task: Speed Comparison
- Try downloading a large video with and without `aria2c` to see the speed difference!
- Example command for manual test:
  ```bash
  yt-dlp --external-downloader aria2c --external-downloader-args "-x 16 -k 1M" <video_url>
  ```


