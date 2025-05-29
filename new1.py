import re
import subprocess

def get_yt_dlp_formats(url):
    result = subprocess.run([
        "yt-dlp", "--list-formats", url
    ], capture_output=True, text=True)
    return result.stdout

def parse_formats(list_formats_output):
    video_formats = []
    audio_formats = []
    for line in list_formats_output.splitlines():
        # More robust regex: allow for variable whitespace and 'audio only' in RESOLUTION
        m = re.match(r"^(hls-[^\s]+)\s+mp4\s+(audio only|[0-9]+x[0-9]+)\s*\|.*\|.*(video only|audio only)", line)
        if m:
            fmt_id = m.group(1)
            res = m.group(2)
            typ = m.group(3)
            if typ == "video only":
                video_formats.append((fmt_id, res))
            elif typ == "audio only":
                audio_formats.append((fmt_id, res))
    return video_formats, audio_formats

if __name__ == "__main__":
    url = "https://video.ibm.com/recorded/134312408"
    print(f"Fetching available formats for: {url}\n")
    formats_output = get_yt_dlp_formats(url)
    print(formats_output)
    video_formats, audio_formats = parse_formats(formats_output)
    print("\nPossible yt-dlp commands to download video and audio separately:")
    for vfmt, vres in video_formats:
        print(f"yt-dlp -f {vfmt} -o video_only.mp4 '{url}'")
    for afmt, ares in audio_formats:
        print(f"yt-dlp -f {afmt} -o audio_only.mp4 '{url}'")
    print("\nTo combine video and audio, use:")
    print("ffmpeg -i video_only.mp4 -i audio_only.mp4 -c copy -map 0:v:0 -map 1:a:0 final_output.mp4")