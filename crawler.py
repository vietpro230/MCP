import re
from typing import Dict, Any, List, Optional
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

def format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds to HH:MM:SS or MM:SS."""
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:shorts\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""

def get_video_transcript(video_id: str) -> List[Dict[str, Any]]:
    """Retrieve transcript with multi-language fallback."""
    if not video_id:
        return []
    try:
        ytt = YouTubeTranscriptApi()
        transcript_list = ytt.list(video_id)
        # Try English or Vietnamese manual or generated
        try:
            transcript = transcript_list.find_manually_created_transcript(['en', 'vi'])
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript(['en', 'vi'])
            except Exception:
                transcript = next(iter(transcript_list))
        data = transcript.fetch()
        formatted = []
        for item in data:
            if isinstance(item, dict):
                start_sec = item.get('start', 0)
                dur_sec = item.get('duration', 0)
                text = item.get('text', '')
            else:
                start_sec = getattr(item, 'start', 0)
                dur_sec = getattr(item, 'duration', 0)
                text = getattr(item, 'text', '')

            text = str(text).replace('\n', ' ')
            formatted.append({
                "start": round(float(start_sec), 2),
                "timestamp": format_duration(int(start_sec)),
                "duration": round(float(dur_sec), 2),
                "text": text
            })
        return formatted
    except Exception:
        return []

def crawl_video(url: str, include_transcript: bool = True, max_comments: int = 50) -> Dict[str, Any]:
    """Crawl full video metadata, transcript, and comments without saving files."""
    video_id = extract_video_id(url)

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }

    if max_comments > 0:
        ydl_opts['getcomments'] = True
        ydl_opts['extractor_args'] = {'youtube': {'max_comments': [str(max_comments), 'all', '1', '0']}}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    title = info.get('title', 'Unknown Title')

    # Transcript
    transcript_data = []
    if include_transcript and video_id:
        transcript_data = get_video_transcript(video_id)

    # Comments
    comments_list = []
    raw_comments = info.get('comments') or []
    for c in raw_comments[:max_comments]:
        comments_list.append({
            "author": c.get('author', 'Anonymous'),
            "likes": c.get('like_count', 0),
            "time": c.get('time_text', ''),
            "text": c.get('text', '')
        })

    return {
        "title": title,
        "video_id": info.get('id', video_id),
        "url": info.get('webpage_url', url),
        "uploader": info.get('uploader', ''),
        "uploader_url": info.get('uploader_url', info.get('channel_url', '')),
        "views": info.get('view_count', 0),
        "likes": info.get('like_count', 0),
        "comment_count": info.get('comment_count', len(comments_list)),
        "duration": format_duration(info.get('duration', 0)),
        "upload_date": info.get('upload_date', ''),
        "tags": (info.get('tags') or [])[:10],
        "description": (info.get('description') or "")[:1000],
        "transcript": transcript_data,
        "comments": comments_list
    }

def crawl_playlist(url: str, max_videos: int = 50) -> Dict[str, Any]:
    """Crawl videos from a playlist or channel without saving files."""
    ydl_opts = {
        'extract_flat': True,
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'playlistend': max_videos
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    playlist_title = info.get('title', 'YouTube Playlist')
    entries = info.get('entries') or []
    videos = []

    for idx, item in enumerate(entries, start=1):
        if not item:
            continue
        v_url = item.get('url') or f"https://www.youtube.com/watch?v={item.get('id')}"
        videos.append({
            "index": idx,
            "title": item.get('title', ''),
            "duration": format_duration(item.get('duration', 0)),
            "views": item.get('view_count', 'N/A'),
            "channel": item.get('uploader', item.get('channel', '')),
            "url": v_url,
            "id": item.get('id', '')
        })

    return {
        "playlist_title": playlist_title,
        "total_videos": len(videos),
        "videos": videos
    }

def crawl_comments_only(url: str, max_comments: int = 100) -> Dict[str, Any]:
    """Crawl only comments from video without saving files."""
    video_id = extract_video_id(url)
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'getcomments': True,
        'extractor_args': {'youtube': {'max_comments': [str(max_comments), 'all', '1', '0']}}
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    title = info.get('title', 'YouTube Video')
    raw_comments = info.get('comments') or []
    comments_list = []
    for idx, c in enumerate(raw_comments[:max_comments], start=1):
        comments_list.append({
            "index": idx,
            "author": c.get('author', 'Anonymous'),
            "likes": c.get('like_count', 0),
            "time": c.get('time_text', ''),
            "text": c.get('text', '')
        })

    return {
        "title": title,
        "total_comments": len(comments_list),
        "comments": comments_list
    }
