"""YouTube scraper using Data API v3 + youtube-transcript-api."""

import os
from datetime import datetime, timezone

from googleapiclient.discovery import build


def _get_transcripts(video_ids: list[str]) -> dict[str, str]:
    """Get transcripts for videos using youtube-transcript-api."""
    transcripts = {}
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        for vid in video_ids:
            try:
                entries = YouTubeTranscriptApi.get_transcript(vid, languages=["en", "en-GB"])
                text = " ".join(e["text"] for e in entries)
                # Truncate to first 2000 chars for storage
                transcripts[vid] = text[:2000]
            except Exception:
                pass  # No transcript available
    except ImportError:
        print("  youtube-transcript-api not installed, skipping transcripts")
    return transcripts


def scrape_youtube(cat_config: dict, settings: dict) -> dict:
    """Scrape YouTube for product reviews — video metadata, comments, transcripts."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("  YOUTUBE_API_KEY required in .env")
        return None

    youtube = build("youtube", "v3", developerKey=api_key)
    queries = cat_config.get("youtube_queries", [])
    max_results = settings.get("max_results", 20)
    max_comments = settings.get("max_comments", 100)

    all_videos = []
    seen_ids = set()

    for query in queries:
        print(f"  Searching YouTube: '{query}'...")
        try:
            search_resp = youtube.search().list(
                q=query,
                part="snippet",
                type="video",
                maxResults=max_results,
                order="relevance",
                relevanceLanguage="en",
                regionCode="GB",
            ).execute()

            video_ids = []
            for item in search_resp.get("items", []):
                vid = item["id"]["videoId"]
                if vid in seen_ids:
                    continue
                seen_ids.add(vid)
                video_ids.append(vid)

            if not video_ids:
                continue

            # Get video stats
            stats_resp = youtube.videos().list(
                part="statistics,snippet,contentDetails",
                id=",".join(video_ids),
            ).execute()

            stats_map = {}
            for item in stats_resp.get("items", []):
                stats_map[item["id"]] = {
                    "title": item["snippet"]["title"],
                    "channel": item["snippet"]["channelTitle"],
                    "published": item["snippet"]["publishedAt"][:10],
                    "description": item["snippet"]["description"][:500],
                    "views": int(item["statistics"].get("viewCount", 0)),
                    "likes": int(item["statistics"].get("likeCount", 0)),
                    "comments_count": int(item["statistics"].get("commentCount", 0)),
                }

            # Get transcripts in bulk
            transcripts = _get_transcripts(video_ids)

            # Get comments for each video
            for vid in video_ids:
                comments = []
                try:
                    comments_resp = youtube.commentThreads().list(
                        part="snippet",
                        videoId=vid,
                        maxResults=min(max_comments, 100),
                        order="relevance",
                        textFormat="plainText",
                    ).execute()

                    for citem in comments_resp.get("items", []):
                        snippet = citem["snippet"]["topLevelComment"]["snippet"]
                        comments.append({
                            "author": snippet["authorDisplayName"],
                            "text": snippet["textDisplay"][:500],
                            "likes": snippet["likeCount"],
                            "date": snippet["publishedAt"][:10],
                        })
                except Exception:
                    pass  # Comments disabled or API error

                info = stats_map.get(vid, {})
                all_videos.append({
                    "video_id": vid,
                    "url": f"https://youtube.com/watch?v={vid}",
                    "title": info.get("title", ""),
                    "channel": info.get("channel", ""),
                    "published": info.get("published", ""),
                    "views": info.get("views", 0),
                    "likes": info.get("likes", 0),
                    "description": info.get("description", ""),
                    "transcript_excerpt": transcripts.get(vid, ""),
                    "comments": comments,
                })

        except Exception as e:
            print(f"  Error searching YouTube for '{query}': {e}")

    print(f"  Total videos: {len(all_videos)}, comments: {sum(len(v['comments']) for v in all_videos)}")

    return {
        "source": "youtube",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "queries": queries,
        "videos": all_videos,
    }
