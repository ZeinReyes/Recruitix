"""
run_pipeline.py

Automated Recruitix data pipeline.

Pipeline:
1. Collect new jobs from PhilJobNet
2. Save new raw records
3. Clean and standardize the dataset
4. Import cleaned records into PostgreSQL

If no new jobs are found, the pipeline stops without
re-running the cleaning/import steps.
"""

import sys
from pathlib import Path
from datetime import datetime


# ==========================================================
# PATH SETUP
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "collectors"))


# ==========================================================
# IMPORT PIPELINE MODULES
# ==========================================================

from collectors import philjobnet_collector
import clean_pipeline
import import_to_postgres


# ==========================================================
# LOGGING
# ==========================================================

def log(message):
    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    print(
        f"[{timestamp}] {message}"
    )


# ==========================================================
# MAIN PIPELINE
# ==========================================================

def run_pipeline():

    print()
    print("=" * 70)
    print("RECRUITIX AUTOMATED DATA PIPELINE")
    print("=" * 70)
    print()

    # ------------------------------------------------------
    # STEP 1 — COLLECT
    # ------------------------------------------------------

    log("STEP 1: Checking PhilJobNet for new listings...")

    try:

        jobs = philjobnet_collector.collect(
            incremental=True
        )

    except Exception as e:

        log(
            f"ERROR: Job collection failed: {e}"
        )

        raise

    log(
        f"Collector found {len(jobs):,} new jobs."
    )


    # ------------------------------------------------------
    # NO NEW JOBS
    # ------------------------------------------------------

    if not jobs:

        log(
            "No new listings found."
        )

        log(
            "Database is already up to date."
        )

        print()
        print("=" * 70)
        print("PIPELINE COMPLETE — NOTHING NEW")
        print("=" * 70)
        print()

        return


    # ------------------------------------------------------
    # STEP 2 — SAVE RAW DATA
    # ------------------------------------------------------

    log(
        "STEP 2: Saving raw job data..."
    )

    raw_file = philjobnet_collector.save_raw(
        jobs
    )

    log(
        f"Raw data saved to: {raw_file}"
    )


    # ------------------------------------------------------
    # STEP 3 — CLEAN
    # ------------------------------------------------------

    log(
        "STEP 3: Cleaning and standardizing jobs..."
    )

    try:

        clean_pipeline.run()

    except Exception as e:

        log(
            f"ERROR: Cleaning pipeline failed: {e}"
        )

        raise


    log(
        "Cleaning completed successfully."
    )


    # ------------------------------------------------------
    # STEP 4 — IMPORT TO POSTGRES
    # ------------------------------------------------------

    log(
        "STEP 4: Importing cleaned jobs into PostgreSQL..."
    )

    try:

        import_to_postgres.run()

    except Exception as e:

        log(
            f"ERROR: PostgreSQL import failed: {e}"
        )

        raise


    # ------------------------------------------------------
    # COMPLETE
    # ------------------------------------------------------

    print()
    print("=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)

    log(
        f"New jobs processed: {len(jobs):,}"
    )

    log(
        "Recruitix database is up to date."
    )

    print()


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":

    try:

        run_pipeline()

    except KeyboardInterrupt:

        print()
        log("Pipeline stopped by user.")
        sys.exit(1)

    except Exception as e:

        print()
        print("=" * 70)
        print("PIPELINE FAILED")
        print("=" * 70)

        log(str(e))

        sys.exit(1)