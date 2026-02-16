#!/usr/bin/env python3
"""UGC Pipeline CLI — scrape, process, and store user-generated content."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

PIPELINE_DIR = Path(__file__).parent
load_dotenv(PIPELINE_DIR / ".env")

CONFIG_PATH = PIPELINE_DIR / "config.yaml"
DATA_DIR = PIPELINE_DIR / "data"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_dirs(site: str, category: str):
    """Create data directories for a site/category."""
    base = DATA_DIR / site
    (base / "raw").mkdir(parents=True, exist_ok=True)
    (base / "processed").mkdir(parents=True, exist_ok=True)
    (base / "approved").mkdir(parents=True, exist_ok=True)


def get_data_dir(site: str) -> Path:
    return DATA_DIR / site


def save_raw(data: dict, site: str, category: str, source: str) -> Path:
    """Save raw scrape data as JSON."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = get_data_dir(site) / "raw" / f"{category}-{source}-{today}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Saved: {path}")
    return path


def run_scraper(source: str, cat_config: dict, settings: dict):
    """Run a single scraper and return its data."""
    if source == "reddit":
        from scrapers.reddit import scrape_reddit
        return scrape_reddit(cat_config, settings.get("reddit", {}))
    elif source == "youtube":
        from scrapers.youtube import scrape_youtube
        return scrape_youtube(cat_config, settings.get("youtube", {}))
    elif source == "forums":
        from scrapers.forums import scrape_forums
        return scrape_forums(cat_config, settings.get("forums", {}))
    elif source == "trustpilot":
        from scrapers.trustpilot import scrape_trustpilot
        return scrape_trustpilot(cat_config, settings.get("trustpilot", {}))
    elif source == "amazon":
        from scrapers.amazon_reviews import scrape_amazon
        return scrape_amazon(cat_config, settings.get("amazon", {}))
    else:
        print(f"  Unknown source: {source}")
        return None


def run_processors(site: str, category: str):
    """Run all processors on raw data to produce analysis JSON."""
    from processors.product_aggregator import aggregate_products
    from processors.quote_extractor import extract_quotes
    from processors.sentiment import score_sentiment

    raw_dir = get_data_dir(site) / "raw"
    raw_files = sorted(raw_dir.glob(f"{category}-*.json"))

    if not raw_files:
        print(f"  No raw data found for {category}")
        return None

    all_data = []
    for f in raw_files:
        with open(f, "r", encoding="utf-8") as fh:
            all_data.append(json.load(fh))
    print(f"  Loaded {len(all_data)} raw data files")

    quotes = extract_quotes(all_data)
    print(f"  Extracted {len(quotes)} quotes")

    products = aggregate_products(all_data, quotes)
    print(f"  Found {len(products)} products")

    products = score_sentiment(products)
    products.sort(key=lambda p: p["mentions"], reverse=True)

    recommended = [p for p in products if p.get("verdict") != "AVOID"]
    avoid = [p for p in products if p.get("verdict") == "AVOID"]

    analysis = {
        "category": category,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_mentions": sum(p["mentions"] for p in products),
        "sources_used": [d.get("source", "unknown") for d in all_data],
        "products": recommended,
        "avoid_products": avoid,
    }

    out_path = get_data_dir(site) / "processed" / f"{category}-analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Saved analysis: {out_path}")
    return analysis


def write_dashboard_data(results: dict, site: str):
    """Write dashboard JSON for GitHub Pages to consume."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    dashboard_path = PIPELINE_DIR / "docs" / "data" / f"{site}-status.json"
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing dashboard data or create new
    if dashboard_path.exists():
        with open(dashboard_path, "r", encoding="utf-8") as f:
            dashboard = json.load(f)
    else:
        dashboard = {"site": site, "runs": []}

    run_entry = {
        "timestamp": now,
        "categories": {},
    }

    for cat, info in results.items():
        run_entry["categories"][cat] = {
            "sources": info.get("sources", {}),
            "products_found": info.get("products", 0),
            "error": info.get("error"),
        }

    # Keep last 30 runs
    dashboard["runs"].append(run_entry)
    dashboard["runs"] = dashboard["runs"][-30:]
    dashboard["last_run"] = now

    with open(dashboard_path, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, indent=2, default=str)

    # Also write a summary for each category's latest processed data
    for cat in results:
        processed_path = get_data_dir(site) / "processed" / f"{cat}-analysis.json"
        if processed_path.exists():
            summary_path = PIPELINE_DIR / "docs" / "data" / f"{site}-{cat}-summary.json"
            with open(processed_path, "r", encoding="utf-8") as f:
                analysis = json.load(f)
            # Create a lighter summary for dashboard
            summary = {
                "category": cat,
                "generated": analysis.get("generated"),
                "total_mentions": analysis.get("total_mentions", 0),
                "sources_used": analysis.get("sources_used", []),
                "products": [
                    {
                        "name": p["name"],
                        "mentions": p["mentions"],
                        "sentiment_score": p["sentiment_score"],
                        "verdict": p["verdict"],
                        "top_quote": p["top_quotes"][0]["text"] if p.get("top_quotes") else "",
                        "pros": p.get("common_pros", []),
                        "cons": p.get("common_cons", []),
                    }
                    for p in analysis.get("products", [])
                ],
                "avoid_products": [
                    {
                        "name": p["name"],
                        "mentions": p["mentions"],
                        "reason": p.get("reason", ""),
                        "complaint_count": p.get("complaint_count", 0),
                    }
                    for p in analysis.get("avoid_products", [])
                ],
            }
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, default=str)

    print(f"\nDashboard data updated: {dashboard_path}")


def write_last_run(results: dict):
    """Write last-run.md summary."""
    path = PIPELINE_DIR / "last-run.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# UGC Pipeline Last Run\n\n**Date**: {now}\n"]
    for cat, info in results.items():
        lines.append(f"\n## {cat}\n\n")
        for source, count in info.get("sources", {}).items():
            lines.append(f"- **{source}**: {count} items scraped\n")
        if info.get("products"):
            lines.append(f"- **Products found**: {info['products']}\n")
        if info.get("error"):
            lines.append(f"- **Error**: {info['error']}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"Summary written to {path}")


ALL_SOURCES = ["reddit", "youtube", "forums", "trustpilot", "amazon"]


def main():
    parser = argparse.ArgumentParser(description="UGC Pipeline — scrape and process user-generated content")
    parser.add_argument("--site", default="bestreviews.co.uk", help="Site to scrape for")
    parser.add_argument("--category", help="Single category to scrape")
    parser.add_argument("--all-categories", action="store_true", help="Scrape all configured categories")
    parser.add_argument("--source", help="Single source (reddit, youtube, forums, trustpilot, amazon)")
    parser.add_argument("--process-only", action="store_true", help="Skip scraping, only process existing raw data")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be scraped")
    args = parser.parse_args()

    config = load_config()
    site_config = config["sites"].get(args.site)
    if not site_config:
        print(f"Site '{args.site}' not found in config.yaml")
        sys.exit(1)

    settings = config.get("settings", {})
    categories = site_config["categories"]

    if args.all_categories:
        cats_to_run = list(categories.keys())
    elif args.category:
        if args.category not in categories:
            print(f"Category '{args.category}' not found. Available: {list(categories.keys())}")
            sys.exit(1)
        cats_to_run = [args.category]
    else:
        print("Specify --category <name> or --all-categories")
        sys.exit(1)

    sources = [args.source] if args.source else ALL_SOURCES

    if args.dry_run:
        print("DRY RUN — would scrape:")
        for cat in cats_to_run:
            print(f"\n  Category: {cat}")
            for src in sources:
                print(f"    Source: {src}")
        return

    run_results = {}

    for cat in cats_to_run:
        print(f"\n{'='*60}")
        print(f"Category: {cat}")
        print(f"{'='*60}")

        ensure_dirs(args.site, cat)
        cat_config = categories[cat]
        run_results[cat] = {"sources": {}}

        if not args.process_only:
            for src in sources:
                print(f"\n--- Scraping: {src} ---")
                try:
                    data = run_scraper(src, cat_config, settings)
                    if data:
                        save_raw(data, args.site, cat, src)
                        count = len(data.get("threads", data.get("videos", data.get("reviews", data.get("results", [])))))
                        run_results[cat]["sources"][src] = count
                        print(f"  {src}: {count} items")
                    else:
                        run_results[cat]["sources"][src] = 0
                except Exception as e:
                    print(f"  ERROR scraping {src}: {e}")
                    run_results[cat]["sources"][src] = 0
                    run_results[cat]["error"] = str(e)

        print(f"\n--- Processing: {cat} ---")
        try:
            analysis = run_processors(args.site, cat)
            if analysis:
                run_results[cat]["products"] = len(analysis.get("products", []))
        except Exception as e:
            print(f"  ERROR processing: {e}")
            run_results[cat]["error"] = str(e)

    write_last_run(run_results)
    write_dashboard_data(run_results, args.site)
    print("\nDone.")


if __name__ == "__main__":
    main()
