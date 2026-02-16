"""Reddit scraper using PRAW (Python Reddit API Wrapper)."""

import os
import re
from datetime import datetime, timezone

import praw


def _detect_products(text: str, known_products: list[str] | None = None) -> list[str]:
    """Detect product names mentioned in text."""
    # Common water softener products (extend per category via config later)
    default_products = [
        "Water2Buy W2B200", "Water2Buy W2B800", "Water2Buy W2B500",
        "Water2Buy", "W2B200", "W2B800", "W2B500",
        "BWT WS555", "BWT WS355", "BWT Perla", "BWT",
        "Harvey", "Harvey's", "Harveys",
        "Kinetico", "Kinetico Premier",
        "Monarch", "Monarch Midi", "Monarch Master",
        "EcoWater", "Eco Water",
        "Culligan", "TwinTec", "Twin Tec",
        "Halcyan", "Eddy", "Tapworks",
    ]
    products = known_products or default_products
    found = []
    text_lower = text.lower()
    for p in products:
        if p.lower() in text_lower:
            # Use the canonical form
            if p not in found:
                found.append(p)
    return found


def _simple_sentiment(text: str) -> str:
    """Basic keyword sentiment scoring."""
    text_lower = text.lower()
    pos_words = ["recommend", "love", "great", "excellent", "brilliant", "best",
                 "fantastic", "perfect", "happy", "pleased", "reliable", "solid",
                 "worth", "impressed", "good quality", "no issues", "well made"]
    neg_words = ["avoid", "terrible", "awful", "rubbish", "waste", "overpriced",
                 "rip off", "ripoff", "scam", "broke", "broken", "useless",
                 "nightmare", "worst", "regret", "problem", "complaint", "expensive"]
    pos = sum(1 for w in pos_words if w in text_lower)
    neg = sum(1 for w in neg_words if w in text_lower)
    if pos > neg:
        return "positive"
    elif neg > pos:
        return "negative"
    return "neutral"


def scrape_reddit(cat_config: dict, settings: dict) -> dict:
    """Scrape Reddit for product discussions."""
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    user_agent = os.environ.get("REDDIT_USER_AGENT", "ugc-pipeline/1.0")

    if not client_id or not client_secret:
        print("  REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET required in .env")
        return None

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
    )

    subreddits = cat_config.get("subreddits", [])
    keywords = cat_config.get("keywords", [])
    max_threads = settings.get("max_threads_per_subreddit", 50)
    max_comments = settings.get("max_comments_per_thread", 100)
    min_score = settings.get("min_score", 2)
    sort = settings.get("sort", "relevance")
    time_filter = settings.get("time_filter", "all")

    all_threads = []
    seen_ids = set()

    for sub_name in subreddits:
        sub_name = sub_name.lstrip("r/")
        print(f"  Searching r/{sub_name}...")
        subreddit = reddit.subreddit(sub_name)

        for keyword in keywords:
            try:
                results = subreddit.search(
                    keyword,
                    sort=sort,
                    time_filter=time_filter,
                    limit=max_threads,
                )
                for submission in results:
                    if submission.id in seen_ids:
                        continue
                    seen_ids.add(submission.id)

                    if submission.score < min_score:
                        continue

                    # Get comments
                    submission.comment_sort = "best"
                    submission.comments.replace_more(limit=0)
                    comments = []
                    for comment in submission.comments.list()[:max_comments]:
                        if hasattr(comment, "body") and comment.score >= min_score:
                            products = _detect_products(comment.body)
                            if products or len(comment.body) > 50:
                                comments.append({
                                    "author": f"u/{comment.author}" if comment.author else "[deleted]",
                                    "text": comment.body,
                                    "score": comment.score,
                                    "products_mentioned": products,
                                    "sentiment": _simple_sentiment(comment.body),
                                    "date": datetime.fromtimestamp(
                                        comment.created_utc, tz=timezone.utc
                                    ).strftime("%Y-%m-%d"),
                                })

                    all_threads.append({
                        "title": submission.title,
                        "url": f"https://reddit.com{submission.permalink}",
                        "subreddit": f"r/{sub_name}",
                        "date": datetime.fromtimestamp(
                            submission.created_utc, tz=timezone.utc
                        ).strftime("%Y-%m-%d"),
                        "score": submission.score,
                        "num_comments": submission.num_comments,
                        "selftext": submission.selftext[:500] if submission.selftext else "",
                        "comments": comments,
                    })
            except Exception as e:
                print(f"  Error searching r/{sub_name} for '{keyword}': {e}")

    print(f"  Total threads: {len(all_threads)}, with comments: {sum(len(t['comments']) for t in all_threads)}")

    return {
        "source": "reddit",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "subreddits": subreddits,
        "keywords": keywords,
        "threads": all_threads,
    }
