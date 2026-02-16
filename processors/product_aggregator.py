"""Aggregate product mentions across all sources."""

import re
from collections import Counter, defaultdict


# Product name normalization map — maps variants to canonical names
PRODUCT_ALIASES = {
    # Water softener products (extend per category)
    "w2b200": "Water2Buy W2B200",
    "w2b800": "Water2Buy W2B800",
    "w2b500": "Water2Buy W2B500",
    "water2buy w2b200": "Water2Buy W2B200",
    "water2buy w2b800": "Water2Buy W2B800",
    "water2buy w2b500": "Water2Buy W2B500",
    "water2buy": "Water2Buy",
    "bwt ws555": "BWT WS555",
    "bwt ws355": "BWT WS355",
    "bwt perla": "BWT Perla",
    "bwt": "BWT",
    "harvey": "Harvey",
    "harvey's": "Harvey",
    "harveys": "Harvey",
    "kinetico": "Kinetico",
    "kinetico premier": "Kinetico Premier",
    "monarch": "Monarch",
    "monarch midi": "Monarch Midi",
    "monarch master": "Monarch Master",
    "ecowater": "EcoWater",
    "eco water": "EcoWater",
    "culligan": "Culligan",
    "twintec": "TwinTec",
    "twin tec": "TwinTec",
    "halcyan": "Halcyan",
    "eddy": "Eddy",
    "tapworks": "Tapworks",
}


def _normalize_product(name: str) -> str:
    """Normalize product name to canonical form."""
    return PRODUCT_ALIASES.get(name.lower(), name)


def _detect_products_in_text(text: str) -> list[str]:
    """Find all product mentions in text."""
    found = set()
    text_lower = text.lower()
    for alias, canonical in PRODUCT_ALIASES.items():
        if alias in text_lower:
            found.add(canonical)
    return list(found)


def _extract_prices(text: str) -> list[str]:
    """Extract GBP price mentions from text."""
    prices = re.findall(r"£[\d,]+(?:\.\d{2})?", text)
    return prices


def _extract_pros_cons(quotes: list[dict], product_name: str) -> tuple[list[str], list[str]]:
    """Extract common pros and cons from quotes about a product."""
    pro_patterns = {
        "cheap salt": r"cheap\s+salt|tablet\s+salt|standard\s+salt",
        "easy install": r"easy\s+(?:to\s+)?install|diy\s+install|self\s+install",
        "reliable": r"reliable|no\s+(?:issues|problems)|been\s+running|years?\s+(?:old|running)",
        "good value": r"good\s+value|worth\s+(?:the\s+)?money|great\s+price|best\s+value",
        "compact": r"compact|small\s+(?:size|footprint)|doesn't?\s+take.*space",
        "quiet": r"quiet|silent|can't\s+hear",
        "effective": r"effective|works\s+(?:well|great|brilliantly)|soft\s+water",
        "good support": r"good\s+(?:support|service)|helpful|responsive",
    }
    con_patterns = {
        "basic display": r"basic\s+display|simple\s+display|no\s+(?:display|screen)",
        "plastic feel": r"plastic|cheap\s+(?:feel|looking|build)",
        "noisy": r"noisy|loud|hear\s+it",
        "expensive": r"expensive|overpriced|rip\s*off|costly",
        "proprietary salt": r"proprietary\s+salt|special\s+salt|own\s+salt|salt\s+blocks",
        "poor service": r"poor\s+(?:service|support|customer)|terrible\s+service|no\s+response",
        "hard to install": r"hard\s+to\s+install|difficult\s+install|need\s+(?:a\s+)?plumber",
        "bulky": r"bulky|large|takes?\s+up.*space|big\s+unit",
    }

    pros = []
    cons = []
    product_quotes = [q for q in quotes if product_name in q.get("products_mentioned", [])
                      or product_name.lower() in q.get("text", "").lower()]

    combined_text = " ".join(q["text"] for q in product_quotes).lower()

    for label, pattern in pro_patterns.items():
        if re.search(pattern, combined_text):
            pros.append(label)
    for label, pattern in con_patterns.items():
        if re.search(pattern, combined_text):
            cons.append(label)

    return pros, cons


def aggregate_products(all_data: list[dict], quotes: list[dict]) -> list[dict]:
    """Aggregate product mentions and build product profiles.

    Returns list of product dicts with mentions, quotes, pros, cons, verdict.
    """
    mention_counts = Counter()
    product_scores = defaultdict(list)
    product_quotes = defaultdict(list)
    product_prices = defaultdict(list)

    # Count mentions from all raw data
    for data in all_data:
        source_type = data.get("source", "unknown")

        if source_type == "reddit":
            for thread in data.get("threads", []):
                # Check thread title + selftext
                combined = thread.get("title", "") + " " + thread.get("selftext", "")
                for product in _detect_products_in_text(combined):
                    mention_counts[product] += 1

                for comment in thread.get("comments", []):
                    for product in comment.get("products_mentioned", []):
                        canonical = _normalize_product(product)
                        mention_counts[canonical] += 1
                        product_scores[canonical].append(comment.get("score", 0))

                    # Also detect in text
                    for product in _detect_products_in_text(comment.get("text", "")):
                        mention_counts[product] += 1
                        product_prices[product].extend(_extract_prices(comment.get("text", "")))

        elif source_type == "youtube":
            for video in data.get("videos", []):
                combined = video.get("title", "") + " " + video.get("description", "")
                for product in _detect_products_in_text(combined):
                    mention_counts[product] += 1

                for comment in video.get("comments", []):
                    for product in _detect_products_in_text(comment.get("text", "")):
                        mention_counts[product] += 1

                transcript = video.get("transcript_excerpt", "")
                for product in _detect_products_in_text(transcript):
                    mention_counts[product] += 1

        elif source_type == "forums":
            for thread in data.get("threads", []):
                for product in _detect_products_in_text(thread.get("title", "")):
                    mention_counts[product] += 1
                for post in thread.get("posts", []):
                    text = post.get("text", "")
                    for product in _detect_products_in_text(text):
                        mention_counts[product] += 1
                        product_prices[product].extend(_extract_prices(text))

        elif source_type == "trustpilot":
            for company in data.get("companies", []):
                for review in company.get("reviews", []):
                    text = review.get("text", "") + " " + review.get("title", "")
                    for product in _detect_products_in_text(text):
                        mention_counts[product] += 1

    # Assign quotes to products
    for quote in quotes:
        text_lower = quote.get("text", "").lower()
        for product in mention_counts:
            if product.lower() in text_lower:
                product_quotes[product].append(quote)

    # Build product profiles
    products = []
    for product_name, count in mention_counts.most_common():
        if count < 2:  # skip products with <2 mentions
            continue

        # Get top quotes sorted by score
        top_quotes = sorted(product_quotes[product_name], key=lambda q: q["score"], reverse=True)[:10]

        # Format top quotes for output
        formatted_quotes = [
            {
                "text": q["text"],
                "source": q["source"],
                "url": q["url"],
                "score": q["score"],
            }
            for q in top_quotes
        ]

        # Extract pros/cons
        pros, cons = _extract_pros_cons(quotes, product_name)

        # Average thread/comment score
        scores = product_scores.get(product_name, [0])
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0

        # Unique prices
        prices = list(set(product_prices.get(product_name, [])))

        products.append({
            "name": product_name,
            "mentions": count,
            "sentiment_score": 0.0,  # filled by sentiment processor
            "avg_thread_score": avg_score,
            "top_quotes": formatted_quotes,
            "price_mentions": prices[:5],
            "common_pros": pros,
            "common_cons": cons,
            "verdict": "PENDING",  # filled by sentiment processor
        })

    return products
