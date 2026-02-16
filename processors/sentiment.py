"""Simple keyword-based sentiment scoring for products."""

import re


# Positive and negative signal words with weights
POS_WORDS = {
    "recommend": 2, "love": 2, "brilliant": 2, "excellent": 2, "fantastic": 2,
    "great": 1, "good": 1, "happy": 1, "pleased": 1, "reliable": 1,
    "solid": 1, "worth": 1, "impressed": 1, "perfect": 2, "best": 1,
    "works well": 2, "no issues": 2, "no problems": 2,
    "well made": 1, "good quality": 1, "great value": 2, "best value": 2,
    "easy install": 1, "easy to install": 1, "diy install": 1,
    "years": 1, "still going": 2, "still working": 2,
    "cheap salt": 1, "tablet salt": 1, "standard salt": 1,
    "save": 1, "saved": 1, "saving": 1,
}

NEG_WORDS = {
    "avoid": 3, "terrible": 2, "awful": 2, "rubbish": 2, "waste": 2,
    "overpriced": 2, "rip off": 3, "ripoff": 3, "scam": 3,
    "broke": 2, "broken": 2, "useless": 2, "nightmare": 3,
    "worst": 2, "regret": 2, "expensive": 1, "costly": 1,
    "poor service": 2, "poor quality": 2, "poor support": 2,
    "don't buy": 3, "do not buy": 3, "wouldn't recommend": 3,
    "proprietary salt": 1, "special salt": 1, "salt blocks": 1,
    "complaint": 2, "problem": 1, "issues": 1,
    "leaked": 2, "leaking": 2, "failed": 2,
}


def _score_text(text: str) -> float:
    """Score a single text for sentiment. Returns -1.0 to 1.0."""
    text_lower = text.lower()
    pos_score = 0
    neg_score = 0

    for word, weight in POS_WORDS.items():
        if word in text_lower:
            pos_score += weight
    for word, weight in NEG_WORDS.items():
        if word in text_lower:
            neg_score += weight

    total = pos_score + neg_score
    if total == 0:
        return 0.0
    return round((pos_score - neg_score) / total, 2)


def score_sentiment(products: list[dict]) -> list[dict]:
    """Score sentiment for each product based on its quotes and set verdict.

    Modifies products in-place and returns them.
    """
    for product in products:
        scores = []

        # Score each quote
        for quote in product.get("top_quotes", []):
            score = _score_text(quote.get("text", ""))
            scores.append(score)

        # Also consider pros/cons ratio
        pros_count = len(product.get("common_pros", []))
        cons_count = len(product.get("common_cons", []))

        if scores:
            avg_score = sum(scores) / len(scores)
        else:
            avg_score = 0.0

        # Adjust based on pros/cons
        if pros_count + cons_count > 0:
            pros_ratio = pros_count / (pros_count + cons_count)
            # Blend quote sentiment with pros/cons ratio
            sentiment = round((avg_score * 0.7) + ((pros_ratio * 2 - 1) * 0.3), 2)
        else:
            sentiment = round(avg_score, 2)

        # Clamp to -1 to 1
        sentiment = max(-1.0, min(1.0, sentiment))
        product["sentiment_score"] = sentiment

        # Set verdict
        if sentiment >= 0.5:
            product["verdict"] = "RECOMMENDED"
        elif sentiment >= 0.2:
            product["verdict"] = "GOOD"
        elif sentiment >= -0.2:
            product["verdict"] = "MIXED"
        elif sentiment >= -0.5:
            product["verdict"] = "CAUTION"
        else:
            product["verdict"] = "AVOID"

        # Override: if many avoid/negative keywords in quotes, force AVOID
        all_quote_text = " ".join(q.get("text", "") for q in product.get("top_quotes", []))
        avoid_signals = sum(1 for word in ["avoid", "rip off", "ripoff", "scam", "don't buy", "do not buy"]
                           if word in all_quote_text.lower())
        if avoid_signals >= 2:
            product["verdict"] = "AVOID"
            product["sentiment_score"] = min(product["sentiment_score"], -0.5)

        # Add complaint count for AVOID products
        if product["verdict"] == "AVOID":
            product["complaint_count"] = len([q for q in product.get("top_quotes", [])
                                               if _score_text(q.get("text", "")) < 0])
            product["reason"] = ", ".join(product.get("common_cons", [])[:3]) or "Negative user sentiment"

    return products
