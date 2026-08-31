from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db


router = APIRouter(
    prefix="/api/analytics",
    tags=["Analytics"],
)


# =========================================================
# DERIVED INDUSTRY EXPRESSION
# =========================================================
#
# Used everywhere so industry filtering and industry
# grouping produce the same results.
#

INDUSTRY_EXPRESSION = """
COALESCE(
    NULLIF(TRIM(industry), ''),
    CASE
        WHEN LOWER(
            COALESCE(job_title, '') || ' ' ||
            COALESCE(description, '')
        ) LIKE ANY (
            ARRAY[
                '%software%',
                '%developer%',
                '%programmer%',
                '%information technology%',
                '%web developer%',
                '%data analyst%',
                '%data scientist%',
                '%cybersecurity%',
                '%network%',
                '%database%'
            ]
        )
        THEN 'Information Technology'

        WHEN LOWER(
            COALESCE(job_title, '') || ' ' ||
            COALESCE(description, '')
        ) LIKE ANY (
            ARRAY[
                '%accountant%',
                '%accounting%',
                '%finance%',
                '%financial%',
                '%bank%',
                '%audit%',
                '%bookkeeper%'
            ]
        )
        THEN 'Banking & Finance'

        WHEN LOWER(
            COALESCE(job_title, '') || ' ' ||
            COALESCE(description, '')
        ) LIKE ANY (
            ARRAY[
                '%nurse%',
                '%doctor%',
                '%medical%',
                '%healthcare%',
                '%hospital%',
                '%pharmac%',
                '%therapist%'
            ]
        )
        THEN 'Healthcare'

        WHEN LOWER(
            COALESCE(job_title, '') || ' ' ||
            COALESCE(description, '')
        ) LIKE ANY (
            ARRAY[
                '%teacher%',
                '%education%',
                '%school%',
                '%instructor%',
                '%professor%'
            ]
        )
        THEN 'Education'

        WHEN LOWER(
            COALESCE(job_title, '') || ' ' ||
            COALESCE(description, '')
        ) LIKE ANY (
            ARRAY[
                '%sales%',
                '%marketing%',
                '%business development%',
                '%account executive%',
                '%brand%'
            ]
        )
        THEN 'Sales & Marketing'

        WHEN LOWER(
            COALESCE(job_title, '') || ' ' ||
            COALESCE(description, '')
        ) LIKE ANY (
            ARRAY[
                '%construction%',
                '%civil engineer%',
                '%architect%',
                '%structural engineer%',
                '%electrical engineer%',
                '%mechanical engineer%'
            ]
        )
        THEN 'Construction & Engineering'

        WHEN LOWER(
            COALESCE(job_title, '') || ' ' ||
            COALESCE(description, '')
        ) LIKE ANY (
            ARRAY[
                '%hotel%',
                '%restaurant%',
                '%chef%',
                '%hospitality%',
                '%food service%',
                '%housekeeping%'
            ]
        )
        THEN 'Hospitality & Tourism'

        WHEN LOWER(
            COALESCE(job_title, '') || ' ' ||
            COALESCE(description, '')
        ) LIKE ANY (
            ARRAY[
                '%warehouse%',
                '%logistics%',
                '%driver%',
                '%delivery%',
                '%transportation%',
                '%dispatcher%'
            ]
        )
        THEN 'Logistics & Transportation'

        WHEN LOWER(
            COALESCE(job_title, '') || ' ' ||
            COALESCE(description, '')
        ) LIKE ANY (
            ARRAY[
                '%retail%',
                '%store%',
                '%cashier%',
                '%merchandiser%',
                '%sales associate%'
            ]
        )
        THEN 'Retail'

        WHEN LOWER(
            COALESCE(job_title, '') || ' ' ||
            COALESCE(description, '')
        ) LIKE ANY (
            ARRAY[
                '%manufacturing%',
                '%production%',
                '%factory%',
                '%machine operator%',
                '%production operator%'
            ]
        )
        THEN 'Manufacturing'

        WHEN LOWER(
            COALESCE(job_title, '') || ' ' ||
            COALESCE(description, '')
        ) LIKE ANY (
            ARRAY[
                '%real estate%',
                '%property%',
                '%leasing%'
            ]
        )
        THEN 'Real Estate'

        ELSE 'Other'
    END
)
"""


# =========================================================
# SALARY EXPRESSION
# =========================================================
#
# All salary aggregates (averages, distributions, per-category
# comparisons) use the single monthly-normalized column
# (salary_amount_monthly), not the raw salary_amount.
#
# salary_amount mixes pay periods together -- a ₱600/day wage and a
# ₱30,000/month salary land in the same numeric column, which silently
# distorts every AVG(), distribution bucket, and category comparison.
# salary_amount_monthly is produced by clean_pipeline.py's
# add_normalized_salary() step, which converts daily/weekly/hourly/
# annual figures to their monthly equivalent using the stated (or
# confidently inferred) salary_period, and leaves the value NULL when
# the period is genuinely ambiguous rather than guessing.
#
# NOTE: salary_amount replaces the old salary_min/salary_max pair.
# Every disclosed PhilJobNet posting states exactly one figure, so a
# single job never has a "min" and "max" of its own -- but a CATEGORY
# still legitimately spans a range across its many postings (e.g.
# "Sales Representative" jobs range from ₱12,000 to ₱35,000/month
# across different employers). That per-category range is still
# meaningful and is preserved in /salary-range-by-category below.
#
# This column must exist on the `jobs` table (see import_to_postgres.py)
# as a nullable NUMERIC column.

SALARY_EXPR = "salary_amount_monthly"


# =========================================================
# SHARED FILTER
# =========================================================

def build_filters(
    category=None,
    region=None,
    industry=None,
    employment_type=None,
):
    """
    Always returns a WHERE clause beginning with
    WHERE 1=1.

    This allows every query to safely append:
        AND ...

    without producing invalid SQL such as:

        FROM jobs
        AND salary_disclosed = TRUE
    """

    conditions = ["1=1"]
    params = {}

    if category:
        conditions.append(
            "career_category = :category"
        )
        params["category"] = category

    if region:
        conditions.append(
            "region = :region"
        )
        params["region"] = region

    if industry:
        conditions.append(
            f"{INDUSTRY_EXPRESSION} = :industry"
        )
        params["industry"] = industry

    if employment_type:
        conditions.append(
            "employment_type = :employment_type"
        )
        params["employment_type"] = employment_type

    return "WHERE " + " AND ".join(conditions), params


# =========================================================
# SUMMARY
# =========================================================

@router.get("/summary")
def analytics_summary(
    category: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    employment_type: str | None = None,
    db: Session = Depends(get_db),
):
    where, params = build_filters(
        category,
        region,
        industry,
        employment_type,
    )

    query = text(
        f"""
        SELECT
            COUNT(*) AS total_jobs,

            COUNT(
                DISTINCT NULLIF(TRIM(company), '')
            ) AS total_companies,

            COUNT(
                DISTINCT NULLIF(TRIM(career_category), '')
            ) AS total_categories,

            COUNT(
                DISTINCT NULLIF(TRIM(location), '')
            ) AS total_locations,

            COUNT(
                DISTINCT NULLIF(TRIM(region), '')
            ) AS total_regions,

            COUNT(
                CASE
                    WHEN salary_disclosed = TRUE
                    THEN 1
                END
            ) AS jobs_with_salary

        FROM jobs

        {where}
        """
    )

    row = db.execute(query, params).mappings().first()

    return dict(row) if row else {}


# =========================================================
# CATEGORIES
# =========================================================

@router.get("/categories")
def get_categories(
    limit: int = Query(10, ge=1, le=100),
    category: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    employment_type: str | None = None,
    db: Session = Depends(get_db),
):
    where, params = build_filters(
        category,
        region,
        industry,
        employment_type,
    )

    params["limit"] = limit

    query = text(
        f"""
        SELECT
            COALESCE(
                NULLIF(TRIM(career_category), ''),
                'Uncategorized'
            ) AS career_category,

            COUNT(*) AS job_count

        FROM jobs

        {where}

        GROUP BY career_category

        ORDER BY job_count DESC

        LIMIT :limit
        """
    )

    rows = db.execute(query, params).mappings().all()

    return [dict(row) for row in rows]


# =========================================================
# LOCATIONS
# =========================================================

@router.get("/locations")
def get_locations(
    limit: int = Query(10, ge=1, le=100),
    category: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    employment_type: str | None = None,
    db: Session = Depends(get_db),
):
    where, params = build_filters(
        category,
        region,
        industry,
        employment_type,
    )

    params["limit"] = limit

    query = text(
        f"""
        SELECT
            COALESCE(
                NULLIF(TRIM(location), ''),
                'Unknown'
            ) AS location,

            COUNT(*) AS job_count

        FROM jobs

        {where}

        GROUP BY location

        ORDER BY job_count DESC

        LIMIT :limit
        """
    )

    rows = db.execute(query, params).mappings().all()

    return [dict(row) for row in rows]


# =========================================================
# REGIONS
# =========================================================

@router.get("/regions")
def get_regions(
    category: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    employment_type: str | None = None,
    db: Session = Depends(get_db),
):
    where, params = build_filters(
        category,
        region,
        industry,
        employment_type,
    )

    query = text(
        f"""
        SELECT
            COALESCE(
                NULLIF(TRIM(region), ''),
                'Unknown'
            ) AS region,

            COUNT(*) AS job_count

        FROM jobs

        {where}

        GROUP BY region

        ORDER BY job_count DESC
        """
    )

    rows = db.execute(query, params).mappings().all()

    return [dict(row) for row in rows]


# =========================================================
# COMPANIES
# =========================================================

@router.get("/companies")
def get_companies(
    limit: int = Query(10, ge=1, le=100),
    category: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    employment_type: str | None = None,
    db: Session = Depends(get_db),
):
    where, params = build_filters(
        category,
        region,
        industry,
        employment_type,
    )

    params["limit"] = limit

    query = text(
        f"""
        SELECT
            company,
            COUNT(*) AS job_count

        FROM jobs

        {where}

        AND company IS NOT NULL
        AND TRIM(company) <> ''

        GROUP BY company

        ORDER BY job_count DESC

        LIMIT :limit
        """
    )

    rows = db.execute(query, params).mappings().all()

    return [dict(row) for row in rows]


# =========================================================
# JOB TITLES
# =========================================================

@router.get("/job-titles")
def get_job_titles(
    limit: int = Query(10, ge=1, le=100),
    category: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    employment_type: str | None = None,
    db: Session = Depends(get_db),
):
    where, params = build_filters(
        category,
        region,
        industry,
        employment_type,
    )

    params["limit"] = limit

    query = text(
        f"""
        SELECT
            job_title,
            COUNT(*) AS job_count

        FROM jobs

        {where}

        AND job_title IS NOT NULL
        AND TRIM(job_title) <> ''

        GROUP BY job_title

        ORDER BY job_count DESC

        LIMIT :limit
        """
    )

    rows = db.execute(query, params).mappings().all()

    return [dict(row) for row in rows]


# =========================================================
# INDUSTRIES
# =========================================================

@router.get("/industries")
def get_industries(
    limit: int = Query(10, ge=1, le=100),
    category: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    employment_type: str | None = None,
    db: Session = Depends(get_db),
):
    # Industry is derived when the database industry column
    # is NULL or empty.

    where, params = build_filters(
        category,
        region,
        industry,
        employment_type,
    )

    params["limit"] = limit

    query = text(
        f"""
        SELECT
            {INDUSTRY_EXPRESSION} AS industry,
            COUNT(*) AS job_count

        FROM jobs

        {where}

        GROUP BY {INDUSTRY_EXPRESSION}

        ORDER BY job_count DESC

        LIMIT :limit
        """
    )

    rows = db.execute(query, params).mappings().all()

    return [dict(row) for row in rows]


# =========================================================
# EMPLOYMENT TYPES
# =========================================================

@router.get("/employment-types")
def get_employment_types(
    category: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    employment_type: str | None = None,
    db: Session = Depends(get_db),
):
    where, params = build_filters(
        category,
        region,
        industry,
        employment_type,
    )

    query = text(
        f"""
        SELECT
            COALESCE(
                NULLIF(TRIM(employment_type), ''),
                'Not specified'
            ) AS employment_type,

            COUNT(*) AS job_count

        FROM jobs

        {where}

        GROUP BY employment_type

        ORDER BY job_count DESC
        """
    )

    rows = db.execute(query, params).mappings().all()

    return [dict(row) for row in rows]


# =========================================================
# SALARY SUMMARY
# =========================================================
#
# average_salary / lowest_salary / highest_salary describe the overall
# ONE-number-per-posting distribution -- there's no separate "min" and
# "max" per job anymore, so this collapses to plain aggregates over
# salary_amount_monthly.

@router.get("/salary")
@router.get("/salary-summary")
def get_salary_summary(
    category: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    employment_type: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Supports both:

        /api/analytics/salary

    and:

        /api/analytics/salary-summary

    so the frontend does not have to be changed.

    Uses the monthly-normalized salary column so daily/weekly/hourly/
    annual figures don't get averaged in alongside raw monthly figures.
    """

    where, params = build_filters(
        category,
        region,
        industry,
        employment_type,
    )

    query = text(
        f"""
        SELECT

            AVG({SALARY_EXPR}) AS average_salary,

            MIN({SALARY_EXPR}) AS lowest_salary,

            MAX({SALARY_EXPR}) AS highest_salary,

            COUNT(*) AS salary_job_count

        FROM jobs

        {where}

        AND salary_disclosed = TRUE

        AND {SALARY_EXPR} IS NOT NULL
        AND {SALARY_EXPR} > 0
        """
    )

    row = db.execute(query, params).mappings().first()

    return dict(row) if row else {}


# =========================================================
# SALARY BY CAREER CATEGORY
# =========================================================
#
# One average per category (no more separate min/max averages -- those
# were always identical since a single posting only ever has one
# figure).

@router.get("/salary-by-category")
def get_salary_by_category(
    limit: int = Query(10, ge=1, le=100),
    category: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    employment_type: str | None = None,
    db: Session = Depends(get_db),
):
    where, params = build_filters(
        category,
        region,
        industry,
        employment_type,
    )

    params["limit"] = limit

    query = text(
        f"""
        SELECT

            COALESCE(
                NULLIF(TRIM(career_category), ''),
                'Uncategorized'
            ) AS career_category,

            ROUND(
                AVG({SALARY_EXPR})::numeric,
                0
            ) AS average_salary,

            COUNT(*) AS job_count

        FROM jobs

        {where}

        AND salary_disclosed = TRUE

        AND {SALARY_EXPR} IS NOT NULL
        AND {SALARY_EXPR} > 0

        GROUP BY career_category

        ORDER BY job_count DESC

        LIMIT :limit
        """
    )

    rows = db.execute(query, params).mappings().all()

    return [dict(row) for row in rows]


# =========================================================
# SALARY DISTRIBUTION
# =========================================================

@router.get("/salary-distribution")
def get_salary_distribution(
    category: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    employment_type: str | None = None,
    db: Session = Depends(get_db),
):
    where, params = build_filters(
        category,
        region,
        industry,
        employment_type,
    )

    query = text(
        f"""
        WITH salary_values AS (
            SELECT
                {SALARY_EXPR} AS salary

            FROM jobs

            {where}

            AND salary_disclosed = TRUE
            AND {SALARY_EXPR} IS NOT NULL
            AND {SALARY_EXPR} > 0
        ),

        salary_ranges AS (
            SELECT
                salary,

                CASE
                    WHEN salary < 10000
                        THEN 'Below ₱10K'

                    WHEN salary < 20000
                        THEN '₱10K–₱19K'

                    WHEN salary < 30000
                        THEN '₱20K–₱29K'

                    WHEN salary < 40000
                        THEN '₱30K–₱39K'

                    WHEN salary < 50000
                        THEN '₱40K–₱49K'

                    WHEN salary < 75000
                        THEN '₱50K–₱74K'

                    WHEN salary < 100000
                        THEN '₱75K–₱99K'

                    ELSE '₱100K+'
                END AS salary_range

            FROM salary_values

            WHERE salary IS NOT NULL
            AND salary > 0
        )

        SELECT
            salary_range,
            COUNT(*) AS job_count

        FROM salary_ranges

        GROUP BY salary_range

        ORDER BY
            CASE salary_range
                WHEN 'Below ₱10K' THEN 1
                WHEN '₱10K–₱19K' THEN 2
                WHEN '₱20K–₱29K' THEN 3
                WHEN '₱30K–₱39K' THEN 4
                WHEN '₱40K–₱49K' THEN 5
                WHEN '₱50K–₱74K' THEN 6
                WHEN '₱75K–₱99K' THEN 7
                WHEN '₱100K+' THEN 8
                ELSE 99
            END
        """
    )

    rows = db.execute(query, params).mappings().all()

    return [dict(row) for row in rows]


# =========================================================
# SALARY RANGE BY CATEGORY
# =========================================================
#
# NOTE: this is a different kind of "range" than the old per-job min/max
# -- it's the spread of salary_amount_monthly ACROSS the many postings
# within a category (e.g. "Sales Representative" jobs range from
# ₱12,000 to ₱35,000/month across different employers). That's still a
# genuinely meaningful comparison even though a single posting only
# ever states one figure, so this endpoint keeps its salary_min /
# salary_max / average_salary shape.

@router.get("/salary-range-by-category")
def get_salary_range_by_category(
    limit: int = Query(10, ge=1, le=100),
    category: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    employment_type: str | None = None,
    db: Session = Depends(get_db),
):
    where, params = build_filters(
        category,
        region,
        industry,
        employment_type,
    )

    params["limit"] = limit

    query = text(
        f"""
        SELECT

            COALESCE(
                NULLIF(TRIM(career_category), ''),
                'Uncategorized'
            ) AS career_category,

            MIN({SALARY_EXPR}) AS salary_min,

            MAX({SALARY_EXPR}) AS salary_max,

            ROUND(
                AVG({SALARY_EXPR})::numeric,
                0
            ) AS average_salary,

            COUNT(*) AS job_count

        FROM jobs

        {where}

        AND salary_disclosed = TRUE

        AND {SALARY_EXPR} IS NOT NULL
        AND {SALARY_EXPR} > 0

        GROUP BY career_category

        ORDER BY job_count DESC

        LIMIT :limit
        """
    )

    rows = db.execute(query, params).mappings().all()

    return [dict(row) for row in rows]


# =========================================================
# FILTER OPTIONS
# =========================================================

@router.get("/filter-options")
def get_filter_options(
    db: Session = Depends(get_db),
):
    categories = db.execute(
        text(
            """
            SELECT DISTINCT career_category
            FROM jobs
            WHERE career_category IS NOT NULL
            AND TRIM(career_category) <> ''
            ORDER BY career_category
            """
        )
    ).scalars().all()

    regions = db.execute(
        text(
            """
            SELECT DISTINCT region
            FROM jobs
            WHERE region IS NOT NULL
            AND TRIM(region) <> ''
            ORDER BY region
            """
        )
    ).scalars().all()

    employment_types = db.execute(
        text(
            """
            SELECT DISTINCT employment_type
            FROM jobs
            WHERE employment_type IS NOT NULL
            AND TRIM(employment_type) <> ''
            ORDER BY employment_type
            """
        )
    ).scalars().all()

    industries = db.execute(
        text(
            f"""
            SELECT DISTINCT
                {INDUSTRY_EXPRESSION} AS industry

            FROM jobs

            ORDER BY industry
            """
        )
    ).scalars().all()

    return {
        "categories": categories,
        "regions": regions,
        "industries": industries,
        "employment_types": employment_types,
    }