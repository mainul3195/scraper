import asyncio
from playwright.async_api import async_playwright

VIDEO_PAGE_URL = "https://monticello.viebit.com/watch?hash=HCZTN4vuyJ91LlrS"
# VIDEO_PAGE_URL = "https://play.champds.com/guilderlandny/event/431"

async def get_yt_dlp_command():
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)  # Using Firefox
        context = await browser.new_context()
        page = await context.new_page()

        m3u8_url = None
        headers = {}

        async def log_request(request):
            nonlocal m3u8_url, headers
            if ".m3u8" in request.url and not m3u8_url:
                m3u8_url = request.url
                headers = dict(request.headers)

        page.on("request", log_request)

        print(f"🌐 Navigating to {VIDEO_PAGE_URL} ...")
        await page.goto(VIDEO_PAGE_URL, wait_until="networkidle")
        await asyncio.sleep(8)  # Wait for network requests

        if not m3u8_url:
            print("❌ No .m3u8 URL found. Try headless=False or increase sleep.")
            await browser.close()
            return

        # Get cookies and user-agent
        cookies = await context.cookies()
        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        user_agent = await page.evaluate("() => navigator.userAgent")

        # Build final headers
        final_headers = dict(headers)  # Start with all headers from the request
        final_headers["user-agent"] = user_agent
        final_headers["referer"] = VIDEO_PAGE_URL
        final_headers["cookie"] = cookie_str

        for k, v in headers.items():
            if k.lower() not in final_headers:
                final_headers[k.lower()] = v
        # Build yt-dlp command
        print("\n🎯 Copy and run this yt-dlp command:\n")
        cmd = ["yt-dlp"]
        for k, v in final_headers.items():
            cmd += ["--add-header", f'"{k}: {v}"']
        cmd += [f'"{m3u8_url}"']
        print(" ".join(cmd))

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_yt_dlp_command())
