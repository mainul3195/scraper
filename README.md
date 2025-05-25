# 🧠 Meeting Video Scraper

This repository provides a robust, modular system for scraping and downloading public meeting videos from a variety of platforms. It is designed to be scalable, efficient, and easy to use for both metadata collection and high-speed video downloads.

---

## 📦 Features
- **Problem 1:** Scrape meeting metadata (title, date, link, etc.) from public video directories over a date range.
- **Problem 2:** Extract direct, downloadable video URLs from meeting pages, verifying with `yt-dlp`.
- **Bonus:** Download videos at high speed using `yt-dlp` with `aria2c` as an external downloader.
- Modular, reusable code ready for scale.
- Outputs clean, structured JSON for easy database ingestion.

---

## 🛠️ Requirements
- Python 3.8+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [aria2c](https://aria2.github.io/)
- [playwright](https://playwright.dev/python/) (`pip install playwright`)
- [requests](https://pypi.org/project/requests/) (if used in Problem 1)
- Run `playwright install` after installing the package.

Install dependencies:
```bash
pip install yt-dlp playwright requests
playwright install
```

---

## 🚀 Usage

### 1️⃣ Problem 1: Scraping Meeting Metadata
- **Script:** `task1.py`
- **Input:** JSON with `start_date`, `end_date`, and `base_urls`.
- **Output:** Structured JSON with all matching meeting metadata.

**Note:**
> Currently, the scrapers only have implementations for two websites:
> - [Detroit Cablecast PublicSite](http://detroit-vod.cablecast.tv/CablecastPublicSite)
> - [Lansdale CivicMedia](https://www.lansdale.org/CivicMedia?CID=2024-Council-Meetings-26)
>
> Support for additional sites can be added by extending the `scrapers.py` module.

**Example:**
```json
{
  "start_date": "2024-11-20",
  "end_date": "2024-11-26",
  "base_urls": ["http://detroit-vod.cablecast.tv/CablecastPublicSite"]
}
```

**Run:**
```bash
python task1.py input.json
```

---

### 2️⃣ Problem 2: Video Download URL Resolution
- **Script:** `task2.py`
- **Input:** List of meeting URLs (from Problem 1 output).
- **Output:** List of direct video URLs that are downloadable with `yt-dlp`.

**How it works:**
- Visits each meeting page using Playwright.
- Extracts direct video sources (from HTML, iframes, and network requests).
- Verifies each candidate URL with `yt-dlp --simulate`.
- Outputs only valid, downloadable video URLs.
- **Now also supports extracting direct video URLs from Facebook (without scrolling) and all YouTube videos.**
- **Note:** Upload date extraction is not yet supported for Facebook and YouTube videos.

**Run:**
```bash
python task2.py
```
- Edit the `MEETING_URLS` list in `task2.py` to include your URLs.
- The script prints valid video URLs to the console.

---

### 💡 Bonus: Faster Downloads with aria2c
- **Script:** `task3.py`
- **Input:** List of direct video URLs (from Problem 2 output).
- **Output:** Downloads videos at high speed using `yt-dlp` + `aria2c`.

**How it works:**
- Uses the `yt-dlp` Python API with `aria2c` as the external downloader.
- Configures `aria2c` for multi-threaded, split, and robust retry downloads.

**Run:**
```bash
python task3.py
```
- Edit the `VIDEO_URLS` list in `task3.py` to include your direct video URLs.

---

## 🔗 Full Pipeline Example
1. **Scrape metadata:**
    - `python task1.py input.json > metadata.json`
2. **Extract direct video URLs:**
    - Copy URLs from `metadata.json` to `MEETING_URLS` in `task2.py`.
    - `python task2.py > valid_video_urls.txt`
3. **Download videos at high speed:**
    - Copy URLs from `valid_video_urls.txt` to `VIDEO_URLS` in `task3.py`.
    - `python task3.py`

---

## 🧩 Modularity & Scaling
- Each task is a standalone script, but functions can be imported and reused.
- Output is always clean, structured JSON for easy database ingestion.
- Designed to be robust against edge cases and varied website structures.

---

## 📝 Notes
- For best results, always use the latest version of `yt-dlp` and `aria2c`.
- Some sites may require additional handling (e.g., login, cookies, or advanced scraping logic).
- **Facebook and YouTube video extraction is supported, but upload date extraction is not yet implemented for these platforms.**
- You can further automate the pipeline by combining the scripts or using a workflow manager.

---

## 🏅 Bonus Task: Speed Comparison
- Try downloading a large video with and without `aria2c` to see the speed difference!
- Example command for manual test:
  ```bash
  yt-dlp --external-downloader aria2c --external-downloader-args "-x 16 -k 1M" <video_url>
  ```


