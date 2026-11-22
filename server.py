import sys
import os
import json
import argparse
from starlette.responses import JSONResponse

try:
    # mcp >= 2.0 uses MCPServer
    from mcp.server.mcpserver import MCPServer as FastMCP
    from mcp.server.transport_security import TransportSecuritySettings
except ImportError:
    try:
        # mcp 1.x
        from mcp.server.fastmcp import FastMCP
        TransportSecuritySettings = None
    except ImportError:
        # standalone fastmcp
        from fastmcp import FastMCP
        TransportSecuritySettings = None

from crawler import crawl_video, crawl_playlist, crawl_comments_only

# Initialize FastMCP Server
mcp = FastMCP("youtube-crawler")

# Health check routes
@mcp.custom_route("/", methods=["GET", "HEAD"])
async def root_check(request):
    return JSONResponse({"status": "ok", "server": "youtube-crawler", "protocol": "Streamable HTTP"})

@mcp.custom_route("/health", methods=["GET", "HEAD"])
async def health_check(request):
    return JSONResponse({"status": "ok"})

@mcp.tool()
def crawl_youtube_video(
    url: str,
    include_transcript: bool = True,
    max_comments: int = 30
) -> str:
    """Crawl full YouTube video metadata, transcript, and comments for analysis or spreadsheet generation.

    Args:
        url: The YouTube video URL (e.g. https://www.youtube.com/watch?v=... or Shorts URL).
        include_transcript: Set True to fetch subtitles/transcripts (supports multiple languages).
        max_comments: Number of top comments to retrieve (0 to skip).
    """
    try:
        data = crawl_video(
            url=url,
            include_transcript=include_transcript,
            max_comments=max_comments
        )

        output = []
        output.append(f"## Video Details: {data['title']}\n")
        output.append(f"- Channel / Creator: {data['uploader']}")
        output.append(f"- Duration: {data['duration']}")
        output.append(f"- Views: {data['views']:,} | Likes: {data['likes']:,}")
        output.append(f"- Published Date: {data['upload_date']}")
        output.append(f"- URL: {data['url']}")
        if data['tags']:
            output.append(f"- Tags: {', '.join(data['tags'])}")
        output.append(f"\n### Description:\n{data['description']}\n")

        # Transcript section
        transcripts = data.get('transcript', [])
        if transcripts:
            output.append(f"### Transcript ({len(transcripts)} snippets):\n")
            transcript_text = "\n".join([f"[{t['timestamp']}] {t['text']}" for t in transcripts[:100]])
            if len(transcripts) > 100:
                transcript_text += f"\n... ({len(transcripts) - 100} more snippets)"
            output.append(transcript_text)
            output.append("")

        # Comments section
        comments = data.get('comments', [])
        if comments:
            output.append(f"### Top Comments ({len(comments)} comments):\n")
            output.append("| # | Author | Likes | Time | Content |")
            output.append("|---|---|---|---|---|")
            for idx, c in enumerate(comments, start=1):
                clean_text = c['text'].replace('\n', ' ').replace('|', '\\|')[:200]
                output.append(f"| {idx} | {c['author']} | {c['likes']} | {c['time']} | {clean_text} |")
            output.append("")

        return "\n".join(output)
    except Exception as e:
        return f"Error crawling YouTube data: {str(e)}"

@mcp.tool()
def crawl_youtube_comments(
    url: str,
    max_comments: int = 50
) -> str:
    """Crawl comments list from a YouTube video.

    Args:
        url: The YouTube video URL.
        max_comments: Number of comments to retrieve (default: 50).
    """
    try:
        data = crawl_comments_only(url=url, max_comments=max_comments)
        output = [f"## Comments for: {data['title']} (Total: {data['total_comments']})\n"]
        output.append("| # | Author | Likes | Time | Content |")
        output.append("|---|---|---|---|---|")
        for c in data['comments']:
            clean_text = c['text'].replace('\n', ' ').replace('|', '\\|')[:250]
            output.append(f"| {c['index']} | {c['author']} | {c['likes']} | {c['time']} | {clean_text} |")
        return "\n".join(output)
    except Exception as e:
        return f"Error crawling comments: {str(e)}"

@mcp.tool()
def crawl_youtube_playlist(
    url: str,
    max_videos: int = 30
) -> str:
    """Crawl video listing from a YouTube playlist or channel.

    Args:
        url: YouTube playlist or channel videos URL.
        max_videos: Maximum number of videos to crawl (default: 30).
    """
    try:
        data = crawl_playlist(url=url, max_videos=max_videos)
        output = [f"## Playlist: {data['playlist_title']} (Total: {data['total_videos']} videos)\n"]
        output.append("| # | Title | Duration | Views | Channel | Link |")
        output.append("|---|---|---|---|---|---|")
        for v in data['videos']:
            title = v['title'].replace('|', '\\|')
            output.append(f"| {v['index']} | {title} | {v['duration']} | {v['views']} | {v['channel']} | [Watch]({v['url']}) |")
        return "\n".join(output)
    except Exception as e:
        return f"Error crawling playlist: {str(e)}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube FastMCP Server for Claude")
    parser.add_argument("--transport", choices=["streamable-http", "sse", "stdio"], default="streamable-http", help="Transport protocol (default: streamable-http)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    args = parser.parse_args()

    security = None
    if TransportSecuritySettings:
        security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "sse":
        print(f"Starting MCP Server on SSE at http://{args.host}:{args.port}/sse", file=sys.stderr)
        if security:
            mcp.run(transport="sse", host=args.host, port=args.port, transport_security=security)
        else:
            mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        print(f"Starting MCP Server on Streamable HTTP at http://{args.host}:{args.port}/mcp", file=sys.stderr)
        if security:
            mcp.run(transport="streamable-http", host=args.host, port=args.port, transport_security=security)
        else:
            mcp.run(transport="streamable-http", host=args.host, port=args.port)
