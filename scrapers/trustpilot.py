"""Trustpilot review scraper using Playwright."""

import asyncio
from datetime import datetime, timezone

from playwright.async_api import async_playwright


async def _scrape_company(page, company_slug: str, max_reviews: int) -> dict:
    """Scrape reviews for a single Trustpilot company page."""
    url = f"https://uk.trustpilot.com/review/{company_slug}"
    reviews = []

    try:
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # Get company info
        company_name = ""
        try:
            name_el = page.locator("h1, .company-name, [data-company-name]").first
            company_name = (await name_el.inner_text()).strip()
        except Exception:
            company_name = company_slug

        overall_rating = ""
        try:
            rating_el = page.locator("[data-rating], .star-rating, .tp-widget__header span").first
            overall_rating = (await rating_el.inner_text()).strip()
        except Exception:
            pass

        # Extract reviews
        review_cards = await page.locator("article.review, [data-review-id], .review-card").all()

        for card in review_cards[:max_reviews]:
            try:
                text = ""
                try:
                    text_el = card.locator(".review-content__text, p[data-service-review-text-typography]").first
                    text = (await text_el.inner_text()).strip()
                except Exception:
                    pass

                title = ""
                try:
                    title_el = card.locator("h2, .review-content__title").first
                    title = (await title_el.inner_text()).strip()
                except Exception:
                    pass

                author = ""
                try:
                    author_el = card.locator("[data-consumer-name-typography], .consumer-info__name").first
                    author = (await author_el.inner_text()).strip()
                except Exception:
                    pass

                rating = ""
                try:
                    rating_el = card.locator("[data-service-review-rating], .star-rating").first
                    rating = await rating_el.get_attribute("data-service-review-rating") or ""
                except Exception:
                    pass

                date = ""
                try:
                    date_el = card.locator("time").first
                    date = await date_el.get_attribute("datetime") or ""
                    date = date[:10]
                except Exception:
                    pass

                if text or title:
                    reviews.append({
                        "title": title,
                        "text": text[:500],
                        "author": author,
                        "rating": rating,
                        "date": date,
                    })
            except Exception:
                pass

    except Exception as e:
        print(f"    Error scraping Trustpilot for {company_slug}: {e}")

    return {
        "company": company_name or company_slug,
        "slug": company_slug,
        "overall_rating": overall_rating,
        "review_count": len(reviews),
        "reviews": reviews,
    }


async def _scrape_all(cat_config: dict, settings: dict) -> list[dict]:
    """Scrape all configured Trustpilot companies."""
    companies = cat_config.get("trustpilot_companies", [])
    max_reviews = settings.get("max_reviews", 50)

    if not companies:
        return []

    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 720},
        )
        page = await context.new_page()

        for company in companies:
            print(f"  Scraping Trustpilot: {company}...")
            data = await _scrape_company(page, company, max_reviews)
            results.append(data)
            print(f"    Got {data['review_count']} reviews")

        await browser.close()

    return results


def scrape_trustpilot(cat_config: dict, settings: dict) -> dict:
    """Synchronous wrapper for Trustpilot scraping."""
    results = asyncio.run(_scrape_all(cat_config, settings))

    total = sum(r["review_count"] for r in results)
    print(f"  Total Trustpilot reviews: {total}")

    return {
        "source": "trustpilot",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "companies": results,
        "reviews": results,  # alias for run.py count logic
    }
