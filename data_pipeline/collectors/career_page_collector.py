"""
career_page_collector.py

Generic template for collecting job postings from a public company career page.

HOW TO USE:
1. Before touching any site: check its /robots.txt and Terms of Service.
   If automated collection is disallowed, don't use this on that site.
2. Duplicate this file per company (or per site pattern) and fill in the
   `CONFIG` block below with that site's specifics.
3. Run it. It saves raw, unmodified JSON to data/raw/ — no cleaning here.
   Cleaning happens later in the cleaners/ pipeline, on purpose, so you
   always have the original data to fall back on.

This template assumes a simple case: a career page that lists jobs as
HTML cards. Many career pages (Greenhouse, Lever, Workday, SmartRecruiters)
actually expose a JSON API under the hood — inspect Network tab in devtools
first, since a JSON endpoint is far more reliable than parsing HTML.
"""

import json
import time
import random
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# CONFIG — fill this in per company/site. This is the only section you
# should need to touch for most simple career pages.
# ---------------------------------------------------------------------------
CONFIG = {
    "source_name": "example_company",       # short slug, used in filenames
    "career_page_url": "https://example.com/careers",
    "job_card_selector": "div.job-card",     # CSS selector for each job listing
    "field_selectors": {
        "job_title": "h3.job-title",
        "location": "span.job-location",
        "job_url": "a.job-link",             # will read href attribute
        "date_posted": "span.job-date",      # optional, may not exist
    },
    "request_delay_seconds": (2, 5),          # random delay range, be polite
    "user_agent": "RecruitixBot/0.1 (+student portfolio project; contact: you@example.com)",
}

RAW_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def fetch_page(url: str, user_agent: str) -> str:
    """Fetch a single page's HTML. Raises on non-200 so failures aren't silent."""
    headers = {"User-Agent": user_agent}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.text


def parse_job_cards(html: str, config: dict) -> list[dict]:
    """Extract raw job fields from HTML using the configured selectors."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(config["job_card_selector"])

    jobs = []
    for card in cards:
        job = {}
        for field, selector in config["field_selectors"].items():
            el = card.select_one(selector)
            if el is None:
                job[field] = None
            elif field == "job_url":
                job[field] = el.get("href")
            else:
                job[field] = el.get_text(strip=True)
        jobs.append(job)
    return jobs


def collect(config: dict = CONFIG) -> list[dict]:
    """Run one collection pass and return the raw job records."""
    print(f"Fetching {config['career_page_url']} ...")
    html = fetch_page(config["career_page_url"], config["user_agent"])

    # Be a polite bot: small delay before/after parsing-adjacent requests.
    delay = random.uniform(*config["request_delay_seconds"])
    time.sleep(delay)

    jobs = parse_job_cards(html, config)
    print(f"Found {len(jobs)} job cards.")

    # Attach collection metadata to every record — critical for traceability
    # and for the "source" field your schema (Section 7) requires.
    collected_at = datetime.now(timezone.utc).isoformat()
    for job in jobs:
        job["source"] = config["source_name"]
        job["source_url"] = config["career_page_url"]
        job["collected_at"] = collected_at

    return jobs


def save_raw(jobs: list[dict], config: dict = CONFIG) -> Path:
    """Save raw collected records as timestamped JSON. Never overwrite — always append a new file."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RAW_DATA_DIR / f"{config['source_name']}_{timestamp}.json"
    out_path.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(jobs)} raw records to {out_path}")
    return out_path


if __name__ == "__main__":
    jobs = collect()
    save_raw(jobs)
