from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)

    job_title = Column(String)
    career_category = Column(String)
    title_match_method = Column(String)

    company = Column(String)

    location = Column(String)
    region = Column(String)

    salary_min = Column(Numeric)
    salary_max = Column(Numeric)

    salary_period = Column(String)
    salary_period_inferred = Column(String)

    salary_disclosed = Column(Boolean)
    currency = Column(String)

    date_posted = Column(Date)

    employment_type = Column(String)
    education_requirement = Column(String)
    industry = Column(String)

    description = Column(Text)

    source = Column(String)
    job_url = Column(String)

    collected_at = Column(DateTime)