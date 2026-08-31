"""
clean_pipeline.py

Reads raw job JSON files from data/raw/, standardizes the records,
validates data quality, deduplicates records, and writes:

    data/processed/jobs_clean.csv
    data/processed/data_quality_report.json
    data/processed/uncategorized_titles.csv   (ranked by frequency)

Pipeline:

    RAW JSON
       ↓
    Standardize title  (exact regex, then fuzzy fallback)
       ↓
    Standardize location  (official PSGC lookup)
       ↓
    Standardize salary
       ↓
    Validate
       ↓
    Deduplicate
       ↓
    CLEAN CSV

NOTE ON SALARY REPRESENTATION
------------------------------
standardize_salary() (cleaners/standardize_salary.py) still returns
salary_min / salary_max, and is intentionally left untouched -- it
already collapses a single stated figure to salary_min == salary_max,
and its range-parsing logic stays in place as a safety net in case a
future job source (or a rare PhilJobNet posting) genuinely states a
range.

In practice, across the full PhilJobNet dataset, salary_min never
differs from salary_max for a single disclosed posting -- PhilJobNet
postings only ever show one number. So everything downstream of
standardize_salary() (this file, the DB import, the API, the
dashboard) works off ONE representative "salary_amount" figure
(the average of min/max, which equals either one when they're equal),
rather than carrying two duplicate columns through every layer.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

from cleaners.standardize_location import standardize_location
from cleaners.standardize_salary import standardize_salary
from cleaners.standardize_title import standardize_title


# ---------------------------------------------------------------------------
# DIRECTORIES
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"


# ---------------------------------------------------------------------------
# LOAD RAW DATA
# ---------------------------------------------------------------------------

def load_raw_records() -> list[dict]:
    records = []
    json_files = sorted(RAW_DIR.glob("*.json"))
    print(f"Found {len(json_files)} raw JSON files.")

    for path in json_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                print(f"Skipping {path.name}: expected a list of records.")
                continue
            records.extend(data)
            print(f"  Loaded {len(data):,} records from {path.name}")
        except json.JSONDecodeError as e:
            print(f"Skipping {path.name}: invalid JSON ({e})")
        except OSError as e:
            print(f"Skipping {path.name}: could not read file ({e})")

    print(f"\nTotal raw records loaded: {len(records):,}")
    return records


# ---------------------------------------------------------------------------
# COMPANY / EMPLOYER
# ---------------------------------------------------------------------------

def get_company(record: dict) -> str | None:
    company = (
        record.get("company")
        or record.get("employer")
        or record.get("organization")
        or record.get("employer_name")
    )
    if company is None:
        return None
    company = str(company).strip()
    return company if company else None


# ---------------------------------------------------------------------------
# PLACEHOLDER TEXT -> NULL
# ---------------------------------------------------------------------------

import re


def clean_placeholder(value: str | None) -> str | None:
    """
    PhilJobNet uses literal placeholder text instead of leaving fields
    blank ("Job type not specified", "Educ level not specified"). Convert
    these to proper None so they're treated as missing data, not as a
    real category, in analysis and quality checks.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if re.search(r"not\s+specified", text, re.IGNORECASE):
        return None
    return text


# ---------------------------------------------------------------------------
# DEDUPLICATION
# ---------------------------------------------------------------------------

def make_dedup_key(record: dict) -> str:
    """
    Prefer the job_url as the uniqueness key — it's the one field that
    reliably identifies a distinct posting (two different roles at the
    same company/location/category are NOT the same job, even if their
    standardized category matches).

    Falls back to standardized career_category + company + location only
    when no URL is available. This fallback intentionally still collapses
    near-duplicate titles like "Junior Data Analyst" and "Data Analyst I"
    at the same company/location into a single record, as before.
    """
    job_url = (record.get("job_url") or "").strip().lower()

    if job_url:
        # Normalize away query-string/fragment/trailing-slash noise so
        # the same posting isn't treated as "new" due to a tracking param.
        job_url = job_url.split("?")[0].split("#")[0].rstrip("/")
        basis = f"url|{job_url}"
    else:
        category = (record.get("career_category") or "").lower().strip()
        company = (record.get("company") or "").lower().strip()
        location = (record.get("location") or "").lower().strip()
        basis = f"fallback|{category}|{company}|{location}"

    return hashlib.md5(basis.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# SALARY AMOUNT (collapse min/max into one representative figure)
# ---------------------------------------------------------------------------
#
# standardize_salary() returns salary_min / salary_max for compatibility
# and future-proofing (see module docstring above). Every disclosed
# PhilJobNet posting has salary_min == salary_max, so averaging them is
# a no-op for the data we actually have today, while still degrading
# gracefully (to a midpoint) if a genuine range ever shows up from a
# future source.

def compute_salary_amount(row: pd.Series):
    salary_min = row.get("salary_min")
    salary_max = row.get("salary_max")

    if pd.isna(salary_min) and pd.isna(salary_max):
        return None
    if pd.isna(salary_min):
        return round(float(salary_max), 2)
    if pd.isna(salary_max):
        return round(float(salary_min), 2)

    return round((float(salary_min) + float(salary_max)) / 2, 2)


# ---------------------------------------------------------------------------
# SALARY PERIOD INFERENCE (magnitude heuristic)
# ---------------------------------------------------------------------------
#
# PhilJobNet almost never states the salary period explicitly, so
# salary_period comes back blank for the vast majority of disclosed
# salaries. Looking at the real distribution, there's a clear gap: most
# values cluster either under ~1,000 (daily-wage range, matching PH
# minimum wage) or above ~8,000 (monthly range), with very few values
# in between. That gap is what makes a magnitude-based guess defensible
# rather than arbitrary — but it IS still a guess, so we keep it in a
# separate column instead of overwriting the honestly-parsed salary_period.
#
# Bands, based on typical PH figures:
#   <= DAILY_CEILING            -> daily   (PH minimum wage is ~570-650/day)
#   DAILY_CEILING..WEEKLY_CEILING -> weekly (5-6 working days at daily-wage
#                                    levels lands roughly in this band)
#   WEEKLY_CEILING..MONTHLY_FLOOR  -> ambiguous (could be a high daily
#                                    contractor rate, an unusual weekly
#                                    figure, or a low monthly salary —
#                                    left unguessed rather than forced)
#   >= MONTHLY_FLOOR            -> monthly
#
# Revisit these thresholds if your dataset's distribution shifts as more
# data comes in.

DAILY_CEILING = 1000      # at/below this: confidently a daily rate
WEEKLY_CEILING = 5000     # above DAILY_CEILING, at/below this: likely weekly
MONTHLY_FLOOR = 8000      # at/above this: confidently a monthly rate
# Between WEEKLY_CEILING and MONTHLY_FLOOR: genuinely ambiguous.

SALARY_OUTLIER_CEILING = 1_000_000  # above this: almost certainly a data error


def infer_salary_period(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds:
      salary_amount: single representative salary figure (see
        compute_salary_amount) — replaces separately tracking
        salary_min/salary_max downstream.
      salary_period_inferred: "daily" | "weekly" | "monthly" | "ambiguous" | None
      salary_outlier: bool — True if salary_amount looks like a data error
    Does NOT touch the original salary_period column (which stays exactly
    what was parsed from text — usually blank, since PhilJobNet rarely
    states it).
    """
    df = df.copy()

    df["salary_amount"] = df.apply(compute_salary_amount, axis=1)

    def infer_row(row):
        if not row["salary_disclosed"]:
            return None
        if pd.notna(row["salary_period"]) and row["salary_period"]:
            return row["salary_period"]  # explicitly stated — trust it as-is
        val = row["salary_amount"]
        if pd.isna(val):
            return None
        if val <= DAILY_CEILING:
            return "daily"
        if val <= WEEKLY_CEILING:
            return "weekly"
        if val >= MONTHLY_FLOOR:
            return "monthly"
        return "ambiguous"

    df["salary_period_inferred"] = df.apply(infer_row, axis=1)

    df["salary_outlier"] = df["salary_amount"].fillna(0).gt(SALARY_OUTLIER_CEILING)

    return df


# ---------------------------------------------------------------------------
# SALARY NORMALIZATION (monthly equivalent)
# ---------------------------------------------------------------------------
#
# Comparing raw salary_amount across the dataset is misleading: a ₱600/day
# wage and a ₱30,000/month salary land in the same numeric column, so an
# AVG(), a distribution bucket, or a category comparison silently mixes
# daily wages with monthly salaries. This converts every disclosed salary
# to a monthly-equivalent figure using salary_period when it's explicitly
# stated, falling back to salary_period_inferred (the magnitude-based
# guess) otherwise.
#
# Left as None (not guessed) when the period is "ambiguous" — we'd
# rather have a missing value than a confidently wrong one.

WORKING_DAYS_PER_MONTH = 22   # standard PH full-time convention
WORKING_HOURS_PER_DAY = 8
WEEKS_PER_MONTH = 52 / 12


def _monthly_equivalent(value, period):
    if value is None or pd.isna(value) or not period:
        return None
    if period == "daily":
        return round(value * WORKING_DAYS_PER_MONTH, 2)
    if period == "weekly":
        return round(value * WEEKS_PER_MONTH, 2)
    if period == "hourly":
        return round(value * WORKING_HOURS_PER_DAY * WORKING_DAYS_PER_MONTH, 2)
    if period == "monthly":
        return round(value, 2)
    if period == "annual":
        return round(value / 12, 2)
    return None  # "ambiguous" or unrecognized — don't guess


def add_normalized_salary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds:
      salary_amount_monthly: monthly-equivalent figure, or None when the
        period couldn't be confidently determined.
      salary_period_used: the period actually used for the conversion
        ("daily"/"weekly"/"hourly"/"monthly"/"annual"), or None.
      salary_period_estimated: True if salary_period_used came from the
        magnitude-based inference rather than text stated on the posting.
    """
    df = df.copy()

    def resolve_period(row):
        stated = row["salary_period"]
        if pd.notna(stated) and stated:
            return stated, False
        inferred = row["salary_period_inferred"]
        if pd.notna(inferred) and inferred and inferred != "ambiguous":
            return inferred, True
        return None, False

    resolved = df.apply(resolve_period, axis=1, result_type="expand")
    df["salary_period_used"] = resolved[0]
    df["salary_period_estimated"] = resolved[1]

    df["salary_amount_monthly"] = df.apply(
        lambda r: _monthly_equivalent(r["salary_amount"], r["salary_period_used"]),
        axis=1,
    )

    return df


# ---------------------------------------------------------------------------
# CLEAN RECORDS
# ---------------------------------------------------------------------------

def clean_records(raw_records: list[dict]) -> pd.DataFrame:
    cleaned_rows = []

    for record in raw_records:
        title_info = standardize_title(record.get("job_title", ""))
        location_info = standardize_location(record.get("location", ""))

        salary_raw = record.get("salary_text") or record.get("salary") or ""
        salary_info = standardize_salary(salary_raw)

        company = get_company(record)
        date_posted = record.get("date_posted")

        row = {
            "job_title": title_info["job_title"],
            "career_category": title_info["career_category"],
            "title_match_method": title_info.get("match_method"),

            "company": company,

            "location": location_info["location"],
            "region": location_info["region"],

            # Kept only as intermediate inputs to salary_amount below —
            # not carried through to the database (see compute_salary_amount).
            "salary_min": salary_info["salary_min"],
            "salary_max": salary_info["salary_max"],

            "salary_period": salary_info["salary_period"],
            "salary_disclosed": salary_info["salary_disclosed"],
            "currency": salary_info["currency"],

            "date_posted": date_posted,
            "employment_type": clean_placeholder(record.get("employment_type")),
            "education_requirement": clean_placeholder(record.get("education_requirement")),
            "industry": record.get("industry"),
            "description": record.get("description"),

            "source": record.get("source"),
            "job_url": record.get("job_url"),
            "collected_at": record.get("collected_at"),
        }
        row["dedup_key"] = make_dedup_key(row)
        cleaned_rows.append(row)

    return pd.DataFrame(cleaned_rows)


# ---------------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------------

def validate(df: pd.DataFrame) -> dict:
    total = len(df)

    missing_salary = (~df["salary_disclosed"]).sum()
    missing_company = df["company"].isna().sum()
    missing_location = df["location"].eq("Unknown").sum()

    unmapped_location = (
        df["region"].isna()
        & ~df["location"].isin(["Unknown", "Remote"])
    ).sum()

    ambiguous_location = df["region"].eq("Ambiguous").sum()
    overseas_postings = df["region"].eq("Overseas").sum()

    missing_title = df["job_title"].fillna("").eq("").sum()

    duplicate_records = df.duplicated(subset="dedup_key").sum()

    valid_mask = (
        df["job_title"].fillna("").ne("")
        & df["company"].notna()
        & df["location"].fillna("Unknown").ne("Unknown")
        & ~df.duplicated(subset="dedup_key")
    )
    valid_records = valid_mask.sum()

    uncategorized_records = df["career_category"].eq("Uncategorized").sum()
    fuzzy_matched_records = df["title_match_method"].fillna("").str.startswith("fuzzy").sum()

    salary_period_daily = df["salary_period_inferred"].eq("daily").sum() if "salary_period_inferred" in df else 0
    salary_period_weekly = df["salary_period_inferred"].eq("weekly").sum() if "salary_period_inferred" in df else 0
    salary_period_monthly = df["salary_period_inferred"].eq("monthly").sum() if "salary_period_inferred" in df else 0
    salary_period_ambiguous = df["salary_period_inferred"].eq("ambiguous").sum() if "salary_period_inferred" in df else 0
    salary_outliers = int(df["salary_outlier"].sum()) if "salary_outlier" in df else 0
    salary_normalized = (
        int(df["salary_amount_monthly"].notna().sum()) if "salary_amount_monthly" in df else 0
    )
    salary_normalized_estimated_period = (
        int(df["salary_period_estimated"].fillna(False).sum())
        if "salary_period_estimated" in df else 0
    )

    report = {
        "total_records": int(total),
        "duplicate_records": int(duplicate_records),
        "missing_salaries": int(missing_salary),
        "missing_company": int(missing_company),
        "missing_locations": int(missing_location),
        "unmapped_locations": int(unmapped_location),
        "ambiguous_locations": int(ambiguous_location),
        "overseas_postings": int(overseas_postings),
        "missing_titles": int(missing_title),
        "uncategorized_titles": int(uncategorized_records),
        "fuzzy_matched_titles": int(fuzzy_matched_records),
        "salary_period_inferred_daily": int(salary_period_daily),
        "salary_period_inferred_weekly": int(salary_period_weekly),
        "salary_period_inferred_monthly": int(salary_period_monthly),
        "salary_period_ambiguous": int(salary_period_ambiguous),
        "salary_outliers_flagged": salary_outliers,
        "salary_records_monthly_normalized": salary_normalized,
        "salary_records_period_estimated": salary_normalized_estimated_period,
        "valid_records": int(valid_records),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return report


# ---------------------------------------------------------------------------
# PRINT QUALITY REPORT
# ---------------------------------------------------------------------------

def print_report(report: dict):
    print("\n" + "=" * 50)
    print("DATA QUALITY REPORT")
    print("=" * 50)
    print(f"Total Records:          {report['total_records']:,}")
    print(f"Duplicate Records:      {report['duplicate_records']:,}")
    print(f"Missing Salaries:       {report['missing_salaries']:,}")
    print(f"Missing Company:        {report['missing_company']:,}")
    print(f"Missing Locations:      {report['missing_locations']:,}")
    print(f"Unmapped Locations:     {report['unmapped_locations']:,}")
    print(f"Ambiguous Locations:    {report['ambiguous_locations']:,}")
    print(f"Overseas Postings:      {report['overseas_postings']:,}")
    print(f"Missing Titles:         {report['missing_titles']:,}")
    print(f"Uncategorized Titles:   {report['uncategorized_titles']:,}")
    print(f"Fuzzy-Matched Titles:   {report['fuzzy_matched_titles']:,}")
    print(f"Salary Period (daily):   {report.get('salary_period_inferred_daily', 0):,}  [inferred by magnitude]")
    print(f"Salary Period (weekly):  {report.get('salary_period_inferred_weekly', 0):,}  [inferred by magnitude]")
    print(f"Salary Period (monthly): {report.get('salary_period_inferred_monthly', 0):,}  [inferred by magnitude]")
    print(f"Salary Period (ambiguous): {report.get('salary_period_ambiguous', 0):,}")
    print(f"Salary Outliers Flagged: {report.get('salary_outliers_flagged', 0):,}")
    print(f"Salary Monthly-Normalized: {report.get('salary_records_monthly_normalized', 0):,}")
    print(f"  (period estimated, not stated): {report.get('salary_records_period_estimated', 0):,}")
    print(f"Valid Records:          {report['valid_records']:,}")
    print("=" * 50 + "\n")


# ---------------------------------------------------------------------------
# UNCATEGORIZED TITLES LOG (ranked by frequency, for fast taxonomy growth)
# ---------------------------------------------------------------------------

def save_uncategorized_titles(df: pd.DataFrame) -> Path | None:
    uncategorized = df[df["career_category"] == "Uncategorized"]["job_title"].value_counts()
    if len(uncategorized) == 0:
        return None

    out_path = PROCESSED_DIR / "uncategorized_titles.csv"
    uncategorized.to_csv(out_path, header=["count"])
    print(f"{len(uncategorized)} unique uncategorized titles logged to {out_path}")
    print("(sorted by frequency — fix the top of the list first for the biggest payoff)")
    return out_path


# ---------------------------------------------------------------------------
# SAVE
# ---------------------------------------------------------------------------

def save_processed_data(df: pd.DataFrame) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # salary_min / salary_max were only intermediate inputs to
    # salary_amount (see compute_salary_amount) — drop them from the
    # saved CSV so downstream consumers (DB import, API) work off the
    # single salary_amount / salary_amount_monthly figures instead of
    # two always-identical columns.
    out_df = df.drop(columns=["salary_min", "salary_max"], errors="ignore")

    out_path = PROCESSED_DIR / "jobs_clean.csv"
    out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    return out_path


def save_quality_report(report: dict) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    report_path = PROCESSED_DIR / "data_quality_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report_path


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------

def run():
    print("\n" + "=" * 60)
    print("JOB DATA CLEANING PIPELINE")
    print("=" * 60)

    raw_records = load_raw_records()
    if not raw_records:
        print(f"\nNo raw files found in:\n{RAW_DIR}")
        print("\nRun a collector first.")
        return

    print("\nStandardizing records...")
    df = clean_records(raw_records)
    df = infer_salary_period(df)
    df = add_normalized_salary(df)

    report = validate(df)
    print_report(report)

    before_dedup = len(df)
    clean_df = (
        df.drop_duplicates(subset="dedup_key", keep="first")
        .drop(columns=["dedup_key"])
    )
    after_dedup = len(clean_df)
    print(f"Records before deduplication: {before_dedup:,}")
    print(f"Records after deduplication:  {after_dedup:,}")

    out_path = save_processed_data(clean_df)
    print(f"\nSaved cleaned dataset:\n{out_path}")

    report_path = save_quality_report(report)
    print(f"\nSaved quality report:\n{report_path}")

    save_uncategorized_titles(clean_df)

    print("\n" + "=" * 60)
    print("CLEANING COMPLETE")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run()