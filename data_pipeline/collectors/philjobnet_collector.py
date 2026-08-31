"""
philjobnet_collector.py

Recruitix collector for PhilJobNet.

Pipeline:

    PhilJobNet
        ↓
    Collect NEW listings
        ↓
    Save raw JSON
        ↓
    Clean data
        ↓
    Import into PostgreSQL
        ↓
    Mark URLs as processed

The important rule is:

    A job is NOT marked as "seen" until the cleaning
    and database import have completed successfully.

This prevents jobs from being permanently skipped if
the cleaner or database fails.

PhilJobNet uses ASP.NET WebForms postback pagination,
so pages after page 1 are requested using __doPostBack.
"""

import json
import random
import sys
import time

from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


# ============================================================
# PATHS
# ============================================================

# This file:
#
# project/
# └── data_pipeline/
#     └── collectors/
#         └── philjobnet_collector.py
#
# parents[0] = collectors
# parents[1] = data_pipeline
# parents[2] = project root

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_PIPELINE_DIR = PROJECT_ROOT / "data_pipeline"

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

SEEN_IDS_PATH = (
    PROCESSED_DIR /
    "philjobnet_seen_job_urls.json"
)


# ============================================================
# PHILJOBNET
# ============================================================

BASE_URL = "https://philjobnet.gov.ph"

LISTING_URL = (
    f"{BASE_URL}/job-vacancies/"
)


HEADERS = {
    "User-Agent": (
        "RecruitixBot/0.1 "
        "(student portfolio project)"
    )
}


# ============================================================
# SELECTORS
# ============================================================

JOB_LINK_SELECTOR = (
    "a[href*='/job-vacancies/job/']"
)


# ============================================================
# ASP.NET FORM STATE
# ============================================================

def _extract_form_state(
    soup: BeautifulSoup
) -> dict:
    """
    Extract all hidden ASP.NET form fields.

    Using all hidden fields is more robust than only
    extracting __VIEWSTATE, __EVENTVALIDATION, etc.
    """

    fields = {}

    for element in soup.select(
        "input[type='hidden']"
    ):

        name = element.get("name")

        if not name:
            continue

        fields[name] = element.get(
            "value",
            ""
        )

    return fields


# ============================================================
# ROW PARSER
# ============================================================

def _parse_row_text(
    row_text: str
) -> dict:
    """
    Parse listing text.

    Expected structure:

    TITLE |
    SALARY |
    EMPLOYER |
    LOCATION |
    EDUCATION |
    EMPLOYMENT TYPE |
    Posted on DATE
    """

    parts = [
        p.strip()
        for p in row_text.split("|")
        if p.strip()
    ]

    result = {
        "job_title": None,
        "salary_text": None,
        "employer": None,
        "location": None,
        "education_requirement": None,
        "employment_type": None,
        "date_posted": None,
    }

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    if parts:

        last_part = parts[-1]

        if last_part.lower().startswith(
            "posted on"
        ):

            result["date_posted"] = (
                last_part[
                    len("Posted on"):
                ].strip()
            )

            parts = parts[:-1]

    # --------------------------------------------------------
    # REMAINING FIELDS
    # --------------------------------------------------------

    field_order = [
        "job_title",
        "salary_text",
        "employer",
        "location",
        "education_requirement",
        "employment_type",
    ]

    for field, value in zip(
        field_order,
        parts
    ):

        result[field] = value

    return result


# ============================================================
# LISTING PARSER
# ============================================================

def _parse_listing_rows(
    soup: BeautifulSoup
) -> list[dict]:
    """
    Extract job listings from a PhilJobNet page.
    """

    jobs = []

    links = soup.select(
        JOB_LINK_SELECTOR
    )

    for link in links:

        href = link.get(
            "href",
            ""
        )

        if not href:
            continue

        # ----------------------------------------------------
        # NORMALIZE URL
        # ----------------------------------------------------

        if href.startswith("http"):

            job_url = href

        elif href.startswith("/"):

            job_url = (
                f"{BASE_URL}{href}"
            )

        else:

            job_url = (
                f"{BASE_URL}/{href}"
            )

        # ----------------------------------------------------
        # FIND CONTAINER
        # ----------------------------------------------------

        container = link.find_parent(
            ["li", "div", "tr"]
        )

        if container:

            row_text = container.get_text(
                " | ",
                strip=True
            )

        else:

            row_text = link.get_text(
                " | ",
                strip=True
            )

        if not row_text:
            continue

        # ----------------------------------------------------
        # PARSE
        # ----------------------------------------------------

        fields = _parse_row_text(
            row_text
        )

        fields["job_url"] = job_url

        # Keep original text for debugging.
        fields["raw_row_text"] = (
            row_text
        )

        jobs.append(fields)

    return jobs


# ============================================================
# FETCH LISTING PAGE
# ============================================================

def fetch_listing_page(
    session: requests.Session,
    page_number: int,
    prior_soup: BeautifulSoup | None = None
) -> BeautifulSoup:

    # --------------------------------------------------------
    # PAGE 1
    # --------------------------------------------------------

    if page_number == 1:

        response = session.get(
            LISTING_URL,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        return BeautifulSoup(
            response.text,
            "html.parser"
        )

    # --------------------------------------------------------
    # PAGES 2+
    # --------------------------------------------------------

    if prior_soup is None:

        raise ValueError(
            "prior_soup is required "
            "for pagination."
        )

    form_state = (
        _extract_form_state(
            prior_soup
        )
    )

    payload = {
        **form_state,

        "__EVENTTARGET":
            "ctl00$BodyContentPlaceHolder$GridView1",

        "__EVENTARGUMENT":
            f"Page${page_number}",
    }

    response = session.post(
        LISTING_URL,
        headers=HEADERS,
        data=payload,
        timeout=30
    )

    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "html.parser"
    )


# ============================================================
# JOB DETAIL
# ============================================================

def fetch_job_detail(
    session: requests.Session,
    job_url: str
) -> dict:
    """
    Fetch a job detail page.

    NOTE:
    Some selectors below are still dependent on the actual
    PhilJobNet detail-page HTML.

    The function returns only values that were actually found.
    This prevents missing detail fields from overwriting good
    listing-page values with None.
    """

    response = session.get(
        job_url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    def text_or_none(
        selector: str
    ):

        element = soup.select_one(
            selector
        )

        if not element:
            return None

        text = element.get_text(
            " ",
            strip=True
        )

        return text or None

    details = {}

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    value = text_or_none("h1")

    if value:
        details["job_title"] = value

    # --------------------------------------------------------
    # EMPLOYER
    # --------------------------------------------------------

    value = text_or_none(
        "a[href*='/job-vacancies/company/']"
    )

    if value:
        details["employer"] = value

    # --------------------------------------------------------
    # SALARY
    # --------------------------------------------------------

    value = text_or_none(
        ".salary"
    )

    if value:
        details["salary_text"] = value

    # --------------------------------------------------------
    # LOCATION
    # --------------------------------------------------------

    value = text_or_none(
        ".work-location"
    )

    if value:
        details["location"] = value

    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    value = text_or_none(
        ".job-description"
    )

    if value:
        details["description"] = value

    return details


# ============================================================
# SEEN URL HISTORY
# ============================================================

def load_seen_job_urls() -> set[str]:
    """
    Load URLs successfully processed by previous runs.
    """

    if not SEEN_IDS_PATH.exists():

        return set()

    try:

        data = json.loads(
            SEEN_IDS_PATH.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            data,
            list
        ):

            return set()

        return set(data)

    except (
        json.JSONDecodeError,
        OSError
    ):

        print(
            f"WARNING: Could not read "
            f"{SEEN_IDS_PATH}"
        )

        return set()


def save_seen_job_urls(
    urls: set[str]
) -> None:

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    SEEN_IDS_PATH.write_text(
        json.dumps(
            sorted(urls),
            indent=2
        ),
        encoding="utf-8"
    )


# ============================================================
# COLLECT
# ============================================================

def collect(
    max_pages: int | None = None,
    fetch_details: bool = False,
    safety_cap: int = 600,
    checkpoint_every: int = 25,
    incremental: bool = True
) -> list[dict]:

    """
    Collect NEW jobs from PhilJobNet.

    IMPORTANT:

    This function DOES NOT save the new URLs to the
    seen-job history.

    The URLs are only saved after:

        scrape → clean → database import

    succeeds.

    This prevents data loss when the database is unavailable.
    """

    previously_seen = (
        load_seen_job_urls()
        if incremental
        else set()
    )

    print()
    print("=" * 60)
    print("PHILJOBNET COLLECTION")
    print("=" * 60)

    print(
        f"Previously processed URLs: "
        f"{len(previously_seen):,}"
    )

    session = requests.Session()

    all_jobs = []

    soup = None

    seen_urls_this_run = set()

    page_number = 1

    upper_bound = (
        max_pages
        if max_pages is not None
        else safety_cap
    )

    while page_number <= upper_bound:

        print(
            f"\nFetching listing page "
            f"{page_number}..."
        )

        try:

            soup = fetch_listing_page(
                session=session,
                page_number=page_number,
                prior_soup=soup
            )

        except requests.RequestException as e:

            print(
                f"Request failed on page "
                f"{page_number}: {e}"
            )

            print(
                "Stopping collection."
            )

            break

        page_jobs = (
            _parse_listing_rows(
                soup
            )
        )

        page_urls = {
            job["job_url"]
            for job in page_jobs
            if job.get("job_url")
        }

        # ----------------------------------------------------
        # NO JOBS
        # ----------------------------------------------------

        if not page_jobs:

            print(
                "No listings found."
            )

            print(
                "Reached the end."
            )

            break

        # ----------------------------------------------------
        # PAGINATION STALL CHECK
        # ----------------------------------------------------

        if (
            page_urls
            and
            page_urls.issubset(
                seen_urls_this_run
            )
        ):

            print(
                "Pagination appears to have "
                "stalled because the same jobs "
                "were returned again."
            )

            break

        # ----------------------------------------------------
        # INCREMENTAL CHECK
        # ----------------------------------------------------

        if (
            incremental
            and
            previously_seen
            and
            page_urls.issubset(
                previously_seen
            )
        ):

            print(
                "This page contains only "
                "previously processed jobs."
            )

            print(
                "No newer listings are expected "
                "past this point."
            )

            break

        # ----------------------------------------------------
        # NEW JOBS
        # ----------------------------------------------------

        new_jobs = [
            job
            for job in page_jobs
            if job.get("job_url")
            and job["job_url"]
            not in seen_urls_this_run
            and job["job_url"]
            not in previously_seen
        ]

        print(
            f"Listings on page: "
            f"{len(page_jobs):,}"
        )

        print(
            f"New listings: "
            f"{len(new_jobs):,}"
        )

        all_jobs.extend(
            new_jobs
        )

        seen_urls_this_run.update(
            page_urls
        )

        # ----------------------------------------------------
        # CHECKPOINT
        # ----------------------------------------------------

        if (
            checkpoint_every
            and
            page_number % checkpoint_every == 0
        ):

            print(
                f"Saving checkpoint "
                f"after page "
                f"{page_number}..."
            )

            save_raw(
                all_jobs,
                suffix="_checkpoint"
            )

        page_number += 1

        # ----------------------------------------------------
        # POLITE DELAY
        # ----------------------------------------------------

        time.sleep(
            random.uniform(
                0.5,
                1
            )
        )

    # ========================================================
    # FETCH DETAILS
    # ========================================================

    if fetch_details and all_jobs:

        print()
        print(
            f"Fetching details for "
            f"{len(all_jobs):,} new jobs..."
        )

        for index, job in enumerate(
            all_jobs,
            start=1
        ):

            print(
                f"[{index:,}/{len(all_jobs):,}] "
                f"{job.get('job_title', 'Unknown')}"
            )

            try:

                details = (
                    fetch_job_detail(
                        session,
                        job["job_url"]
                    )
                )

                # Only update fields that actually
                # contain values.
                for key, value in details.items():

                    if value:

                        job[key] = value

            except requests.RequestException as e:

                print(
                    f"  Detail fetch failed: "
                    f"{e}"
                )

            time.sleep(
                random.uniform(
                    1,
                    2
                )
            )

    # ========================================================
    # METADATA
    # ========================================================

    collected_at = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    for job in all_jobs:

        job["source"] = (
            "philjobnet"
        )

        job["collected_at"] = (
            collected_at
        )

    print()
    print(
        f"Collection finished."
    )

    print(
        f"New jobs collected: "
        f"{len(all_jobs):,}"
    )

    return all_jobs


# ============================================================
# SAVE RAW DATA
# ============================================================

def save_raw(
    jobs: list[dict],
    suffix: str = ""
) -> Path:

    RAW_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = (
        datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%dT%H%M%SZ"
        )
    )

    out_path = (
        RAW_DATA_DIR /
        f"philjobnet_{timestamp}"
        f"{suffix}.json"
    )

    out_path.write_text(
        json.dumps(
            jobs,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print()
    print(
        f"Saved {len(jobs):,} raw records:"
    )

    print(
        out_path
    )

    return out_path


# ============================================================
# RUN CLEANING
# ============================================================

def run_cleaning():
    """
    Run the existing Recruitix cleaning pipeline.
    """

    print()
    print("=" * 60)
    print("RUNNING CLEANING PIPELINE")
    print("=" * 60)

    if str(DATA_PIPELINE_DIR) not in sys.path:

        sys.path.insert(
            0,
            str(DATA_PIPELINE_DIR)
        )

    import clean_pipeline

    clean_pipeline.run()

    print()
    print(
        "Cleaning completed successfully."
    )


# ============================================================
# RUN DATABASE IMPORT
# ============================================================

def run_database_import():
    """
    Run the existing PostgreSQL import script.
    """

    print()
    print("=" * 60)
    print("IMPORTING INTO POSTGRESQL")
    print("=" * 60)

    if str(DATA_PIPELINE_DIR) not in sys.path:

        sys.path.insert(
            0,
            str(DATA_PIPELINE_DIR)
        )

    import import_to_postgre

    import_to_postgre.run()

    print()
    print(
        "PostgreSQL import completed successfully."
    )


# ============================================================
# COMPLETE AUTOMATED PIPELINE
# ============================================================

def run_scrape_and_clean(
    incremental: bool = True,
    fetch_details: bool = False
) -> None:

    """
    Complete Recruitix pipeline:

        1. Check PhilJobNet
        2. Collect new listings
        3. Save raw JSON
        4. Clean the dataset
        5. Import into PostgreSQL
        6. Mark URLs as successfully processed

    If any step after collection fails,
    the new URLs are NOT added to the seen history.
    """

    print()
    print("=" * 70)
    print("RECRUITIX AUTOMATED DATA PIPELINE")
    print("=" * 70)

    # ========================================================
    # STEP 1 — COLLECT
    # ========================================================

    jobs = collect(
        incremental=incremental,
        fetch_details=fetch_details
    )

    # ========================================================
    # NOTHING NEW
    # ========================================================

    if not jobs:

        print()
        print(
            "No new PhilJobNet listings found."
        )

        print(
            "Database does not need to be updated."
        )

        print()
        print(
            "PIPELINE FINISHED"
        )

        return

    # ========================================================
    # STEP 2 — SAVE RAW
    # ========================================================

    print()
    print(
        "STEP 2/5 — Saving raw data..."
    )

    save_raw(
        jobs
    )

    # ========================================================
    # STEP 3 — CLEAN
    # ========================================================

    print()
    print(
        "STEP 3/5 — Cleaning data..."
    )

    run_cleaning()

    # ========================================================
    # STEP 4 — DATABASE
    # ========================================================

    print()
    print(
        "STEP 4/5 — Importing into PostgreSQL..."
    )

    run_database_import()

    # ========================================================
    # STEP 5 — MARK AS PROCESSED
    # ========================================================

    print()
    print(
        "STEP 5/5 — Updating processed-job history..."
    )

    previously_seen = (
        load_seen_job_urls()
        if incremental
        else set()
    )

    new_urls = {
        job["job_url"]
        for job in jobs
        if job.get("job_url")
    }

    updated_seen = (
        previously_seen
        | new_urls
    )

    save_seen_job_urls(
        updated_seen
    )

    # ========================================================
    # COMPLETE
    # ========================================================

    print()
    print("=" * 70)
    print("RECRUITIX PIPELINE COMPLETE")
    print("=" * 70)

    print(
        f"New jobs collected: "
        f"{len(jobs):,}"
    )

    print(
        f"URLs tracked: "
        f"{len(updated_seen):,}"
    )

    print(
        "Raw data saved:      YES"
    )

    print(
        "Data cleaned:        YES"
    )

    print(
        "PostgreSQL updated:  YES"
    )

    print(
        "=" * 70
    )
    print()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    run_scrape_and_clean(
        incremental=True,

        # Keep this False until you have verified the
        # detail-page selectors.
        fetch_details=False
    )