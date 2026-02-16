# UGC Pipeline

Automated scraping and processing of user-generated content (Reddit, YouTube, forums, Trustpilot) for affiliate content generation.

## Setup

1. Copy `.env.example` to `.env` and add API keys
2. `pip install -r requirements.txt`
3. `playwright install chromium`

## Usage

```bash
# Scrape a category
python run.py --category water-softeners

# Scrape a single source
python run.py --category water-softeners --source reddit

# Process existing raw data only
python run.py --category water-softeners --process-only

# Scrape all categories
python run.py --all-categories
```

## GitHub Actions

- **Scheduled**: Runs every Sunday at 2am UTC
- **Manual**: Trigger from Actions tab with category/source options

### Required Secrets

- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `YOUTUBE_API_KEY`

## Dashboard

Deployed to GitHub Pages — see run status, product rankings, and scrape history.
