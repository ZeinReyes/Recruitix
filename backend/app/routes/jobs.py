from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db


router = APIRouter(
    prefix="/api/jobs",
    tags=["Jobs"],
)


# ==========================================================
# DERIVED INDUSTRY EXPRESSION
# ==========================================================
#
# Some records have NULL/empty industry values.
# We derive the industry from job_title + description
# so that Jobs filtering is consistent with Analytics.
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


# ==========================================================
# SHARED FILTER BUILDER
# ==========================================================

def build_job_filters(
    career_category: Optional[str] = None,
    location: Optional[str] = None,
    region: Optional[str] = None,
    industry: Optional[str] = None,
    employment_type: Optional[str] = None,
    search: Optional[str] = None,
):
    conditions = []
    params = {}

    # ------------------------------------------------------
    # CATEGORY
    # ------------------------------------------------------

    if career_category:
        conditions.append(
            "career_category ILIKE :career_category"
        )
        params["career_category"] = f"%{career_category}%"

    # ------------------------------------------------------
    # LOCATION
    # ------------------------------------------------------

    if location:
        conditions.append(
            "location ILIKE :location"
        )
        params["location"] = f"%{location}%"

    # ------------------------------------------------------
    # REGION
    # ------------------------------------------------------

    if region:
        conditions.append(
            "region ILIKE :region"
        )
        params["region"] = f"%{region}%"

    # ------------------------------------------------------
    # INDUSTRY
    # ------------------------------------------------------

    if industry:
        conditions.append(
            f"""
            {INDUSTRY_EXPRESSION} ILIKE :industry
            """
        )
        params["industry"] = f"%{industry}%"

    # ------------------------------------------------------
    # EMPLOYMENT TYPE
    # ------------------------------------------------------

    if employment_type:
        conditions.append(
            "employment_type ILIKE :employment_type"
        )
        params["employment_type"] = f"%{employment_type}%"

    # ------------------------------------------------------
    # SEARCH
    # ------------------------------------------------------

    if search:
        conditions.append(
            """
            (
                job_title ILIKE :search
                OR company ILIKE :search
                OR career_category ILIKE :search
                OR location ILIKE :search
                OR region ILIKE :search
            )
            """
        )

        params["search"] = f"%{search}%"

    # ------------------------------------------------------
    # FINAL WHERE
    # ------------------------------------------------------

    if conditions:
        return (
            "WHERE " + " AND ".join(conditions),
            params,
        )

    return "WHERE 1=1", params


# ==========================================================
# GET JOBS
# ==========================================================

@router.get("/")
def get_jobs(
    career_category: Optional[str] = Query(
        None,
        description="Filter by career category",
    ),

    location: Optional[str] = Query(
        None,
        description="Filter by location",
    ),

    region: Optional[str] = Query(
        None,
        description="Filter by region",
    ),

    industry: Optional[str] = Query(
        None,
        description="Filter by industry",
    ),

    employment_type: Optional[str] = Query(
        None,
        description="Filter by employment type",
    ),

    search: Optional[str] = Query(
        None,
        description="Search job title, company, career category, or location",
    ),

    # Frontend-friendly pagination
    page: int = Query(
        1,
        ge=1,
        description="Page number",
    ),

    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Number of jobs per page",
    ),

    # Keep offset available for backwards compatibility
    offset: Optional[int] = Query(
        None,
        ge=0,
        description="Number of jobs to skip",
    ),

    db: Session = Depends(get_db),
):
    """
    Return jobs with filtering and server-side pagination.

    Supports:
        page + limit

    or:

        offset + limit
    """

    try:
        where, params = build_job_filters(
            career_category=career_category,
            location=location,
            region=region,
            industry=industry,
            employment_type=employment_type,
            search=search,
        )

        # --------------------------------------------------
        # PAGINATION
        # --------------------------------------------------

        if offset is not None:
            calculated_offset = offset
        else:
            calculated_offset = (page - 1) * limit

        params["limit"] = limit
        params["offset"] = calculated_offset

        # --------------------------------------------------
        # QUERY
        # --------------------------------------------------
        #
        # NOTE: salary_amount / salary_amount_monthly replace the old
        # salary_min / salary_max pair. Every disclosed PhilJobNet
        # posting states exactly one figure (see clean_pipeline.py),
        # so carrying two always-identical columns end-to-end (CSV ->
        # Postgres -> API -> frontend) was pure duplication. If a
        # future job source ever posts genuine ranges, re-introduce a
        # min/max pair at that point rather than guessing now.
        #

        query = text(
            f"""
            SELECT
                id,
                job_title,
                career_category,
                title_match_method,
                company,
                location,
                region,
                salary_amount,
                salary_period,
                salary_period_inferred,
                salary_amount_monthly,
                salary_period_used,
                salary_period_estimated,
                salary_disclosed,
                currency,
                date_posted,
                employment_type,
                education_requirement,
                industry,
                description,
                source,
                job_url,
                collected_at

            FROM jobs

            {where}

            ORDER BY id DESC

            LIMIT :limit
            OFFSET :offset
            """
        )

        rows = (
            db.execute(query, params)
            .mappings()
            .all()
        )

        return [dict(row) for row in rows]

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve jobs: {str(e)}",
        )


# ==========================================================
# GET JOB COUNT
# ==========================================================

@router.get("/count")
def get_job_count(
    career_category: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    employment_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),

    db: Session = Depends(get_db),
):
    """
    Return the number of jobs matching the filters.
    """

    try:

        where, params = build_job_filters(
            career_category=career_category,
            location=location,
            region=region,
            industry=industry,
            employment_type=employment_type,
            search=search,
        )

        query = text(
            f"""
            SELECT COUNT(*) AS count

            FROM jobs

            {where}
            """
        )

        row = (
            db.execute(query, params)
            .mappings()
            .first()
        )

        return {
            "count": int(row["count"]) if row else 0
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve job count: {str(e)}",
        )