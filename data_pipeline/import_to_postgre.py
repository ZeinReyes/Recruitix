"""
import_to_postgres.py

Imports the cleaned Recruitix job dataset into PostgreSQL.

Input:
    data/processed/jobs_clean.csv

Database:
    PostgreSQL

The script:
1. Reads jobs_clean.csv
2. Connects to PostgreSQL
3. Creates the jobs table if it does not exist
4. Imports cleaned records
5. Prevents duplicate jobs from being inserted (upserts on re-import)
6. Prints import statistics

Environment variables required:
    DATABASE_URL

Example:
    DATABASE_URL=postgresql://user:superpass@localhost:5432/recruitix
"""

import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


# ---------------------------------------------------------------------------
# DIRECTORIES
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

CSV_PATH = PROCESSED_DIR / "jobs_clean.csv"


# ---------------------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------------------

DATABASE_URL = "postgresql://postgres:superpass@localhost:5432/recruitix"


# ---------------------------------------------------------------------------
# DATABASE SCHEMA
# ---------------------------------------------------------------------------
#
# salary_amount / salary_amount_monthly replace the old salary_min /
# salary_max / salary_min_monthly / salary_max_monthly columns.
#
# Every disclosed PhilJobNet posting states exactly one salary figure
# (standardize_salary() only ever produces salary_min == salary_max for
# this data source), so clean_pipeline.py now collapses that into a
# single salary_amount, and salary_amount_monthly is its monthly-
# normalized equivalent (see clean_pipeline.py's add_normalized_salary()).
# All salary aggregation in the API (app/routers/analytics.py,
# app/routers/jobs.py) reads from salary_amount_monthly.
#

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id BIGSERIAL PRIMARY KEY,

    job_title TEXT NOT NULL,
    career_category TEXT,

    company TEXT NOT NULL,

    location TEXT,
    region TEXT,

    salary_amount NUMERIC,
    salary_period TEXT,
    salary_disclosed BOOLEAN,
    salary_period_inferred TEXT,
    salary_amount_monthly NUMERIC,
    salary_period_used TEXT,
    salary_period_estimated BOOLEAN,
    currency TEXT,

    date_posted DATE,

    employment_type TEXT,
    education_requirement TEXT,
    industry TEXT,

    description TEXT,

    source TEXT,
    job_url TEXT,
    collected_at TIMESTAMPTZ,

    title_match_method TEXT,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (
        job_title,
        career_category,
        company,
        location
    )
);
"""

# ---------------------------------------------------------------------------
# SCHEMA MIGRATION FOR EXISTING TABLES
# ---------------------------------------------------------------------------
#
# CREATE TABLE IF NOT EXISTS is a no-op once the table already exists, so
# tables created before this consolidation (with salary_min/salary_max/
# salary_min_monthly/salary_max_monthly) need the new columns added by
# hand. These ADD COLUMN IF NOT EXISTS statements are safe to run every
# time -- they're no-ops once the columns are present.
#
# The old salary_min / salary_max / salary_min_monthly / salary_max_monthly
# columns are intentionally left in place rather than dropped -- dropping
# columns is destructive and none of your views were confirmed to be
# free of references to them. They will simply stop being written to.
# Drop them manually later once you've confirmed nothing still reads them
# (e.g. `ALTER TABLE jobs DROP COLUMN salary_min, DROP COLUMN salary_max, ...`).
#

ALTER_TABLE_SQL = """
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_amount NUMERIC;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_amount_monthly NUMERIC;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_period_used TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_period_estimated BOOLEAN;
"""


# ---------------------------------------------------------------------------
# LOAD CSV
# ---------------------------------------------------------------------------

def load_csv() -> pd.DataFrame:
    if not CSV_PATH.exists():
        print(f"\nERROR: Cleaned CSV not found:")
        print(CSV_PATH)
        print("\nRun clean_pipeline.py first.")
        sys.exit(1)

    print(f"\nLoading cleaned dataset:")
    print(CSV_PATH)

    df = pd.read_csv(CSV_PATH)

    print(f"Loaded {len(df):,} cleaned records.")

    return df


# ---------------------------------------------------------------------------
# PREPARE DATA
# ---------------------------------------------------------------------------

def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare pandas data for PostgreSQL insertion.

    Converts pandas NaN / NaT values to Python None so PostgreSQL
    receives proper SQL NULL values.
    """

    df = df.copy()

    # -------------------------------------------------------
    # DATE
    # -------------------------------------------------------

    if "date_posted" in df.columns:
        df["date_posted"] = pd.to_datetime(
            df["date_posted"],
            errors="coerce"
        ).dt.date

    # -------------------------------------------------------
    # COLLECTED TIMESTAMP
    # -------------------------------------------------------

    if "collected_at" in df.columns:
        df["collected_at"] = pd.to_datetime(
            df["collected_at"],
            errors="coerce",
            utc=True
        )

    # -------------------------------------------------------
    # BOOLEAN COLUMNS
    # -------------------------------------------------------

    for bool_column in ("salary_disclosed", "salary_period_estimated"):
        if bool_column in df.columns:
            df[bool_column] = df[bool_column].apply(
                lambda x: bool(x) if pd.notna(x) else None
            )

    # -------------------------------------------------------
    # CONVERT ALL NaN / NaT -> None
    # -------------------------------------------------------

    df = df.astype(object).where(pd.notna(df), None)

    return df


# ---------------------------------------------------------------------------
# DEDUPE ON THE DB'S ACTUAL CONFLICT TARGET
# ---------------------------------------------------------------------------

def dedupe_for_conflict_target(df: pd.DataFrame) -> pd.DataFrame:
    """
    The jobs table's UNIQUE constraint is on:
        (job_title, career_category, company, location)

    clean_pipeline.py's dedup_key is based on job_url instead, so two
    CSV rows with different URLs can still share the same
    (job_title, career_category, company, location) tuple -- e.g. the
    same posting re-scraped under a different tracking URL, or two
    genuinely distinct postings that happen to standardize to identical
    title/category/company/location.

    Postgres's ON CONFLICT ... DO UPDATE cannot touch the same
    conflict-target row twice within a single command, so if both
    survive into the same INSERT batch, the whole batch fails with:

        ON CONFLICT DO UPDATE command cannot affect row a second time

    Deduplicating here on the DB's actual conflict columns (keeping the
    most recently collected row) guarantees every batch sent to
    execute_values() is safe, regardless of upstream CSV dedup logic.
    """

    conflict_columns = [
        "job_title",
        "career_category",
        "company",
        "location",
    ]

    missing = [c for c in conflict_columns if c not in df.columns]
    if missing:
        print("\nERROR: Missing conflict-target columns in jobs_clean.csv:")
        for column in missing:
            print(f"  - {column}")
        sys.exit(1)

    before = len(df)

    # Sort so the most recently collected record for a given
    # (title, category, company, location) tuple is kept.
    if "collected_at" in df.columns:
        df = df.sort_values("collected_at", na_position="first")

    df = df.drop_duplicates(subset=conflict_columns, keep="last")

    after = len(df)
    skipped = before - after

    if skipped:
        print(
            f"\nSkipped {skipped:,} CSV rows that share the same "
            f"(job_title, career_category, company, location) as another "
            f"row -- keeping the most recently collected one for each."
        )

    return df


# ---------------------------------------------------------------------------
# INSERT
# ---------------------------------------------------------------------------

INSERT_SQL = """
INSERT INTO jobs (
    job_title,
    career_category,
    company,
    location,
    region,
    salary_amount,
    salary_period,
    salary_disclosed,
    salary_period_inferred,
    salary_amount_monthly,
    salary_period_used,
    salary_period_estimated,
    currency,
    date_posted,
    employment_type,
    education_requirement,
    industry,
    description,
    source,
    job_url,
    collected_at,
    title_match_method
)
VALUES %s

ON CONFLICT (
    job_title,
    career_category,
    company,
    location
)
DO UPDATE SET
    region = EXCLUDED.region,
    salary_amount = EXCLUDED.salary_amount,
    salary_period = EXCLUDED.salary_period,
    salary_disclosed = EXCLUDED.salary_disclosed,
    salary_period_inferred = EXCLUDED.salary_period_inferred,
    salary_amount_monthly = EXCLUDED.salary_amount_monthly,
    salary_period_used = EXCLUDED.salary_period_used,
    salary_period_estimated = EXCLUDED.salary_period_estimated,
    currency = EXCLUDED.currency,
    date_posted = EXCLUDED.date_posted,
    employment_type = EXCLUDED.employment_type,
    education_requirement = EXCLUDED.education_requirement,
    industry = EXCLUDED.industry,
    description = EXCLUDED.description,
    source = EXCLUDED.source,
    job_url = EXCLUDED.job_url,
    collected_at = EXCLUDED.collected_at,
    title_match_method = EXCLUDED.title_match_method
"""


# ---------------------------------------------------------------------------
# INSERT DATA
# ---------------------------------------------------------------------------

def insert_data(conn, df: pd.DataFrame):

    df = dedupe_for_conflict_target(df)

    columns = [
        "job_title",
        "career_category",
        "company",
        "location",
        "region",
        "salary_amount",
        "salary_period",
        "salary_disclosed",
        "salary_period_inferred",
        "salary_amount_monthly",
        "salary_period_used",
        "salary_period_estimated",
        "currency",
        "date_posted",
        "employment_type",
        "education_requirement",
        "industry",
        "description",
        "source",
        "job_url",
        "collected_at",
        "title_match_method",
    ]

    # Make sure every required column exists
    missing_columns = [
        column for column in columns
        if column not in df.columns
    ]

    if missing_columns:
        print("\nERROR: Missing columns in jobs_clean.csv:")
        for column in missing_columns:
            print(f"  - {column}")
        sys.exit(1)

    records = []

    for _, row in df.iterrows():

        values = tuple(
            row[column]
            for column in columns
        )

        records.append(values)

    if not records:
        print("\nNo records to import.")
        return

    with conn.cursor() as cursor:

        execute_values(
            cursor,
            INSERT_SQL,
            records,
            page_size=1000
        )

    conn.commit()

    print(f"\nAttempted to import: {len(records):,} records.")


# ---------------------------------------------------------------------------
# DATABASE STATISTICS
# ---------------------------------------------------------------------------

def get_database_count(conn) -> int:

    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM jobs;")
        return cursor.fetchone()[0]


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def run():

    print("\n" + "=" * 60)
    print("RECRUITIX -> POSTGRESQL IMPORT")
    print("=" * 60)

    # -------------------------------------------------------
    # Check DATABASE_URL
    # -------------------------------------------------------

    if not DATABASE_URL:
        print("\nERROR: DATABASE_URL environment variable is not set.")

        print("\nExample:")
        print(
            "DATABASE_URL="
            "postgresql://username:password@localhost:5432/recruitix"
        )

        sys.exit(1)

    # -------------------------------------------------------
    # Load CSV
    # -------------------------------------------------------

    df = load_csv()

    # -------------------------------------------------------
    # Prepare
    # -------------------------------------------------------

    print("\nPreparing records...")

    df = prepare_dataframe(df)

    # -------------------------------------------------------
    # Connect
    # -------------------------------------------------------

    print("\nConnecting to PostgreSQL...")

    try:

        conn = psycopg2.connect(DATABASE_URL)

        print("PostgreSQL connection successful.")

    except Exception as e:

        print("\nERROR: Could not connect to PostgreSQL.")
        print(e)

        sys.exit(1)

    try:

        # ---------------------------------------------------
        # Create / migrate table
        # ---------------------------------------------------

        print("\nChecking database table...")

        with conn.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
            cursor.execute(ALTER_TABLE_SQL)

        conn.commit()

        print("Table 'jobs' is ready.")

        # ---------------------------------------------------
        # Existing count
        # ---------------------------------------------------

        before_count = get_database_count(conn)

        print(f"\nExisting jobs in database: {before_count:,}")

        # ---------------------------------------------------
        # Insert
        # ---------------------------------------------------

        insert_data(conn, df)

        # ---------------------------------------------------
        # New count
        # ---------------------------------------------------

        after_count = get_database_count(conn)

        inserted = after_count - before_count

        # ---------------------------------------------------
        # Report
        # ---------------------------------------------------

        print("\n" + "=" * 60)
        print("IMPORT COMPLETE")
        print("=" * 60)

        print(f"CSV records:              {len(df):,}")
        print(f"Database before import:   {before_count:,}")
        print(f"New records inserted:     {inserted:,}")
        print(f"Database after import:    {after_count:,}")

        print("=" * 60 + "\n")

    except Exception as e:

        conn.rollback()

        print("\nERROR during import:")
        print(e)

        sys.exit(1)

    finally:

        conn.close()

        print("Database connection closed.")


if __name__ == "__main__":
    run()