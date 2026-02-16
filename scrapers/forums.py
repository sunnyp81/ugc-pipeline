"""Forum scraper using Playwright for AVForums, MSE, DIYnot, PistonHeads."""

import asyncio
from datetime import datetime, timezone

from playwright.async_api import async_playwright


FORUM_PARSERS = {
    "MoneySavingExpert": {
        "thread_selector": ".discussionList-item, .searchResult",
        "title_selector": "a.discussionList-title, .searchResult-title a",
        "link_selector": "a.discussionList-title, .searchResult-title a",
        "thread_content": ".message-body, .bbWrapper",
        "post_selector": ".message, .comment",
        "post_text": ".message-body .bbWrapper, .comment-body",
        "post_author": ".message-name a, .comment-author",
        "post_date": "time",
    },
    "AVForums": {
        "thread_selector": ".structItem, .searchResult",
        "title_selector": ".structItem-title a, .searchResult-title a",
        "link_selector": ".structItem-title a, .searchResult-title a",
        "thread_content": ".message-body .bbWrapper",
        "post_selector": ".message",
        "post_text": ".message-body .bbWrapper",
        "post_author": ".message-name a",
        "post_date": "time",
    },
    "DIYnot": {
        "thread_selector": ".structItem, .searchResult",
        "title_selector": ".structItem-title a, .searchResult-title a",
        "link_selector": ".structItem-title a, .searchResult-title a",
        "thread_content": ".message-body .bbWrapper",
        "post_selector": ".message",
        "post_text": ".message-body .bbWrapper",
        "post_author": ".message-name a",
        "post_date": "time",
    },
    "PistonHeads": {
        "thread_selector": ".search-result, .topic-list-item",
        "title_selector": "a.search-result__title, .topic-list-item a",
        "link_selector": "a.search-result__title, .topic-list-item a",
        "thread_content": ".post__content, .message-content",
        "post_selector": ".post, .message",
        "post_text": ".post__content, .message-content",
        "post_author": ".post__author, .message-author",
        "post_date": "time, .post__date",
    },
}


async def _scrape_forum(page, forum_config: dict, settings: dict) -> list[dict]:
    """Scrape a single forum search page and extract threads."""
    url = forum_config["url"]
    name = forum_config["name"]
    parser = FORUM_PARSERS.get(name, FORUM_PARSERS["AVForums"])  # fallback
    timeout = settings.get("timeout", 30000)
    max_pages = settings.get("max_pages", 5)

    threads = []

    try:
        await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)  # let JS render

        # Accept cookies if prompted
        for cookie_sel in ["button[id*='accept']", "button[class*='accept']", ".cookie-accept", "#onetrust-accept-btn-handler"]:
            try:
                btn = page.locator(cookie_sel).first
                if await btn.is_visible(timeout=1000):
                    await btn.click()
                    await page.wait_for_timeout(500)
                    break
            except Exception:
                pass

        # Find thread links on search results page
        thread_links = []
        link_elements = await page.locator(parser["link_selector"]).all()

        for el in link_elements[:max_pages * 10]:
            try:
                href = await el.get_attribute("href")
                title = await el.inner_text()
                if href and title:
                    # Make absolute URL
                    if href.startswith("/"):
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        href = f"{parsed.scheme}://{parsed.netloc}{href}"
                    thread_links.append({"url": href, "title": title.strip()})
            except Exception:
                pass

        print(f"    Found {len(thread_links)} threads on {name}")

        # Visit each thread and extract posts
        for link in thread_links[:max_pages * 3]:  # limit threads to visit
            try:
                await page.goto(link["url"], timeout=timeout, wait_until="domcontentloaded")
                await page.wait_for_timeout(1500)

                posts = []
                post_elements = await page.locator(parser["post_selector"]).all()

                for post_el in post_elements[:20]:  # max 20 posts per thread
                    try:
                        text_el = post_el.locator(parser["post_text"]).first
                        text = await text_el.inner_text() if await text_el.count() > 0 else ""
                        text = text.strip()[:1000]  # truncate

                        author = ""
                        try:
                            author_el = post_el.locator(parser["post_author"]).first
                            if await author_el.count() > 0:
                                author = (await author_el.inner_text()).strip()
                        except Exception:
                            pass

                        date = ""
                        try:
                            date_el = post_el.locator(parser["post_date"]).first
                            if await date_el.count() > 0:
                                date = await date_el.get_attribute("datetime") or await date_el.inner_text()
                                date = date.strip()[:10]
                        except Exception:
                            pass

                        if text and len(text) > 20:
                            posts.append({
                                "author": author,
                                "text": text,
                                "date": date,
                            })
                    except Exception:
                        pass

                if posts:
                    threads.append({
                        "title": link["title"],
                        "url": link["url"],
                        "forum": name,
                        "posts": posts,
                    })

            except Exception as e:
                print(f"    Error loading thread: {e}")

    except Exception as e:
        print(f"    Error scraping {name}: {e}")

    return threads


async def _scrape_all_forums(cat_config: dict, settings: dict) -> list[dict]:
    """Scrape all configured forums."""
    forums = cat_config.get("forums", [])
    headless = settings.get("headless", True)
    all_threads = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
        )
        page = await context.new_page()

        for forum in forums:
            print(f"  Scraping {forum['name']}...")
            threads = await _scrape_forum(page, forum, settings)
            all_threads.extend(threads)
            print(f"    Got {len(threads)} threads with posts")

        await browser.close()

    return all_threads


def scrape_forums(cat_config: dict, settings: dict) -> dict:
    """Synchronous wrapper for async forum scraping."""
    threads = asyncio.run(_scrape_all_forums(cat_config, settings))

    print(f"  Total forum threads: {len(threads)}, posts: {sum(len(t['posts']) for t in threads)}")

    return {
        "source": "forums",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "forums": [f["name"] for f in cat_config.get("forums", [])],
        "threads": threads,
    }
