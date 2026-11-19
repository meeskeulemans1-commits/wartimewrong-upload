"""Upload een video uit een GitHub-release naar het Wartime Wrong-kanaal (YouTube Data API v3)."""
import os, sys, json, glob, subprocess, datetime as dt
from zoneinfo import ZoneInfo
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

TOKEN_URI = "https://oauth2.googleapis.com/token"


def service():
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri=TOKEN_URI,
                        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                        scopes=["https://www.googleapis.com/auth/youtube.upload"])
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def next_publish_utc(hour=18, tz="Europe/Amsterdam"):
    z = ZoneInfo(tz); now = dt.datetime.now(z)
    t = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if t <= now + dt.timedelta(minutes=20): t += dt.timedelta(days=1)
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def main():
    tag, mode = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "public")
    os.makedirs("dl", exist_ok=True)
    subprocess.run(["gh", "release", "download", tag, "-D", "dl", "--clobber"], check=True)
    meta = json.load(open(glob.glob("dl/*.json")[0], encoding="utf-8"))
    video = os.path.join("dl", meta["video"])
    thumb = os.path.join("dl", meta["thumbnail"]) if meta.get("thumbnail") else None
    print(f"[upload] {meta['title']} ({os.path.getsize(video)//1048576} MB), modus={mode}", flush=True)

    status = {"selfDeclaredMadeForKids": False, "embeddable": True}
    if mode == "scheduled":
        status["privacyStatus"] = "private"; status["publishAt"] = next_publish_utc()
    else:
        status["privacyStatus"] = mode
    body = {"snippet": {"title": meta["title"][:100], "description": meta["description"][:4900],
                        "tags": meta.get("tags", [])[:30], "categoryId": "27",
                        "defaultLanguage": "en", "defaultAudioLanguage": "en"}, "status": status}
    yt = service()
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(video, chunksize=32 * 1024 * 1024, resumable=True, mimetype="video/mp4"))
    resp = None
    while resp is None:
        st, resp = req.next_chunk()
        if st: print(f"[upload] {int(st.progress()*100)}%", flush=True)
    vid = resp["id"]
    print(f"[upload] klaar: https://youtu.be/{vid} status={resp.get('status', {}).get('privacyStatus')}", flush=True)
    if thumb and os.path.exists(thumb):
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb, mimetype="image/jpeg")).execute()
            print("[upload] thumbnail gezet", flush=True)
        except Exception as e:
            print("[upload] thumbnail mislukt:", str(e)[:200], flush=True)


if __name__ == "__main__":
    main()
