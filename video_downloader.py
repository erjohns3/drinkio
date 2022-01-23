import sys
import youtube_dl


video_info = youtube_dl.YoutubeDL().extract_info(
    url = sys.argv[1],download=False
)
options={
    'format':'best/best',
    'keepvideo':True,
    'outtmpl':sys.argv[2]+".mp4",
}

with youtube_dl.YoutubeDL(options) as ydl:
    ydl.download([video_info['webpage_url']])

print("Download complete")

    