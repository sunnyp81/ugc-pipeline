"""Amazon review scraper — search-based fallback since Amazon blocks direct scraping.

Uses web search to find cached/aggregated Amazon reviews rather than scraping
Amazon directly (which blocks aggressively).
"""

import json
import re
from datetime import datetime, timezone

import requests


def _search_amazon_reviews(query: str, max_results: int) -> list[dict]:
    """Search for Amazon reviews via web search aggregators.

    Since Amazon actively blocks scrapers, this uses a search-based approach
    to find reviews from review aggregator sites and cached pages.
    """
    results = []

    # Search for review summaries from aggregator sites
    search_queries = [
        f"site:amazon.co.uk {query} reviews",
        f"{query} amazon reviews summary UK",
        f"{query} amazon customer reviews UK 2025 2026",
    ]

    # Note: This is a placeholder — in production, integrate with a search API
    # (SerpAPI, Google Custom Search, etc.) or use Playwright to search.
    # For now, we log what would be searched and return empty.
    print(f"    Amazon search queries prepared: {len(search_queries)}")
    print(f"    NOTE: Amazon scraper requires manual search or SerpAPI integration")
    print(f"    Queries: {search_queries}")

    return results


def scrape_amazon(cat_config: dict, settings: dict) -> dict:
    """Scrape Amazon reviews via search-based approach.

    This is the lowest-reliability scraper. Amazon blocks aggressively,
    so we use search engines to find cached reviews and summaries.
    """
    queries = cat_config.get("amazon_queries", [])
    max_results = settings.get("max_results", 20)

    all_results = []
    for query in queries:
        print(f"  Searching Amazon reviews: '{query}'...")
        results = _search_amazon_reviews(query, max_results)
        all_results.extend(results)

    print(f"  Total Amazon results: {len(all_results)}")
    print(f"  TIP: For better Amazon data, manually export reviews or use a review API service")

    return {
        "source": "amazon",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "queries": queries,
        "results": all_results,
        "note": "Amazon scraper uses search-based fallback. Direct scraping blocked by Amazon.",
    }
