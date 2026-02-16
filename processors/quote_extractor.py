"""Extract verbatim quotes with attribution from raw scrape data."""

import re


# Minimum quote length to be useful
MIN_QUOTE_LENGTH = 30
MAX_QUOTE_LENGTH = 300


def _clean_quote(text: str) -> str:
    """Clean a quote for display."""
    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Remove markdown links
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    return text.strip()


def _is_good_quote(text: str) -> bool:
    """Check if text makes a good standalone quote."""
    if len(text) < MIN_QUOTE_LENGTH:
        return False
    # Skip very short or very long
    if len(text) > MAX_QUOTE_LENGTH:
        return False
    # Must contain product-related or opinion language
    opinion_signals = [
        "recommend", "love", "hate", "avoid", "best", "worst",
        "bought", "installed", "using", "years", "months",
        "price", "cost", "cheap", "expensive", "worth",
        "quality", "reliable", "broke", "broken", "works",
        "compared", "better", "worse", "alternative",
        "save", "saved", "waste", "happy", "pleased",
        "regret", "brilliant", "terrible", "excellent",
        "£", "salt", "install", "plumber", "service",
    ]
    text_lower = text.lower()
    return any(w in text_lower for w in opinion_signals)


def _extract_sentence_quotes(text: str) -> list[str]:
    """Extract the best sentences from a longer text as quotes."""
    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)
    quotes = []
    for sent in sentences:
        sent = _clean_quote(sent)
        if _is_good_quote(sent):
            quotes.append(sent)
    return quotes


def extract_quotes(all_data: list[dict]) -> list[dict]:
    """Extract quotes from all raw data sources.

    Returns list of:
    {
        "text": "verbatim quote",
        "source": "Reddit u/username" or "AVForums user123",
        "source_type": "reddit" | "youtube" | "forums" | "trustpilot",
        "url": "source URL",
        "score": numeric score (upvotes, likes, etc),
        "products_mentioned": ["Product A"],
        "date": "2025-01-15",
    }
    """
    quotes = []

    for data in all_data:
        source_type = data.get("source", "unknown")

        if source_type == "reddit":
            for thread in data.get("threads", []):
                thread_url = thread.get("url", "")
                for comment in thread.get("comments", []):
                    text = comment.get("text", "")
                    author = comment.get("author", "anonymous")
                    score = comment.get("score", 0)
                    products = comment.get("products_mentioned", [])

                    # Try full comment first, then extract sentences
                    cleaned = _clean_quote(text)
                    if MIN_QUOTE_LENGTH <= len(cleaned) <= MAX_QUOTE_LENGTH and _is_good_quote(cleaned):
                        quotes.append({
                            "text": cleaned,
                            "source": f"Reddit {author}",
                            "source_type": "reddit",
                            "url": thread_url,
                            "score": score,
                            "products_mentioned": products,
                            "date": comment.get("date", ""),
                        })
                    else:
                        # Extract best sentences
                        for sent in _extract_sentence_quotes(text):
                            quotes.append({
                                "text": sent,
                                "source": f"Reddit {author}",
                                "source_type": "reddit",
                                "url": thread_url,
                                "score": score,
                                "products_mentioned": products,
                                "date": comment.get("date", ""),
                            })

        elif source_type == "youtube":
            for video in data.get("videos", []):
                video_url = video.get("url", "")
                # Comments
                for comment in video.get("comments", []):
                    text = comment.get("text", "")
                    cleaned = _clean_quote(text)
                    if _is_good_quote(cleaned):
                        quotes.append({
                            "text": cleaned[:MAX_QUOTE_LENGTH],
                            "source": f"YouTube {comment.get('author', 'user')}",
                            "source_type": "youtube",
                            "url": video_url,
                            "score": comment.get("likes", 0),
                            "products_mentioned": [],
                            "date": comment.get("date", ""),
                        })
                # Transcript excerpts
                transcript = video.get("transcript_excerpt", "")
                if transcript:
                    for sent in _extract_sentence_quotes(transcript):
                        quotes.append({
                            "text": sent,
                            "source": f"YouTube {video.get('channel', 'channel')}",
                            "source_type": "youtube",
                            "url": video_url,
                            "score": video.get("views", 0),
                            "products_mentioned": [],
                            "date": video.get("published", ""),
                        })

        elif source_type == "forums":
            for thread in data.get("threads", []):
                thread_url = thread.get("url", "")
                forum_name = thread.get("forum", "Forum")
                for post in thread.get("posts", []):
                    text = post.get("text", "")
                    author = post.get("author", "user")
                    for sent in _extract_sentence_quotes(text):
                        quotes.append({
                            "text": sent,
                            "source": f"{forum_name} {author}",
                            "source_type": "forums",
                            "url": thread_url,
                            "score": 0,
                            "products_mentioned": [],
                            "date": post.get("date", ""),
                        })

        elif source_type == "trustpilot":
            for company in data.get("companies", []):
                for review in company.get("reviews", []):
                    text = review.get("text", "") or review.get("title", "")
                    cleaned = _clean_quote(text)
                    if _is_good_quote(cleaned):
                        quotes.append({
                            "text": cleaned[:MAX_QUOTE_LENGTH],
                            "source": f"Trustpilot {review.get('author', 'user')}",
                            "source_type": "trustpilot",
                            "url": f"https://uk.trustpilot.com/review/{company.get('slug', '')}",
                            "score": int(review.get("rating", 0) or 0),
                            "products_mentioned": [],
                            "date": review.get("date", ""),
                        })

    # Sort by score descending
    quotes.sort(key=lambda q: q["score"], reverse=True)
    return quotes
