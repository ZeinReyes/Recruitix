from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int

    job_title: Optional[str] = None
    career_category: Optional[str] = None
    title_match_method: Optional[str] = None

    company: Optional[str] = None

    location: Optional[str] = None
    region: Optional[str] = None

    salary_min: Optional[Decimal] = None
    salary_max: Optional[Decimal] = None

    salary_period: Optional[str] = None
    salary_period_inferred: Optional[str] = None

    salary_disclosed: Optional[bool] = None
    currency: Optional[str] = None

    date_posted: Optional[date] = None

    employment_type: Optional[str] = None
    education_requirement: Optional[str] = None
    industry: Optional[str] = None

    description: Optional[str] = None

    source: Optional[str] = None
    job_url: Optional[str] = None

    collected_at: Optional[datetime] = None


class JobCountResponse(BaseModel):
    count: int