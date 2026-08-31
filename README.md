# Recruitix

**Philippine Job Market Intelligence** — an end-to-end data pipeline that scrapes, cleans, stores, and visualizes job postings from [PhilJobNet](https://philjobnet.gov.ph), the Philippine government's official job portal.

Recruitix turns thousands of raw, messy job postings into a standardized dataset and an interactive analytics dashboard covering hiring demand, geographic concentration, employment types, and salary trends across the Philippine labor market.

---

## Why this project

Public job board data is genuinely messy: inconsistent job titles, salary figures buried in free text with no fixed format, placeholder strings instead of nulls, and pagination built on ASP.NET WebForms postbacks rather than a clean API. Recruitix is a full pipeline for turning that mess into something queryable and visual — scraping, standardizing, storing, serving, and charting, all built from scratch rather than through a drag-and-drop BI tool.

---

## Architecture

```
PhilJobNet (ASP.NET WebForms site)
        │
        ▼
┌───────────────────┐
│   Collector        │  philjobnet_collector.py
│   (requests + bs4) │  - handles __doPostBack pagination
└─────────┬──────────┘  - tracks seen job URLs (only marks "seen"
          │                after a full successful pipeline run)
          ▼
   data/raw/*.json
          │
          ▼
┌───────────────────┐
│  Cleaning Pipeline │  clean_pipeline.py
│                    │  - standardize_title.py   (regex taxonomy + fuzzy fallback)
│                    │  - standardize_location.py (PSGC lookup)
│                    │  - standardize_salary.py   (text → figure + period)
│                    │  - magnitude-based period inference
│                    │  - monthly-equivalent normalization
│                    │  - dedup + data quality report
└─────────┬──────────┘
          │
          ▼
data/processed/jobs_clean.csv
          │
          ▼
┌───────────────────┐
│  PostgreSQL Import │  import_to_postgres.py
│                    │  - upsert (ON CONFLICT ... DO UPDATE)
│                    │  - schema migration via ADD COLUMN IF NOT EXISTS
└─────────┬──────────┘
          │
          ▼
     PostgreSQL (jobs table)
          │
          ▼
┌───────────────────┐
│   FastAPI backend  │  /api/jobs, /api/analytics
│                    │  - filtering, pagination, search
│                    │  - derived industry classification
│                    │  - salary aggregation on monthly-normalized figures
└─────────┬──────────┘
          │
          ▼
┌───────────────────┐
│   React frontend   │  Dashboard.jsx, Jobs.jsx
│   (Recharts)        │  - hiring demand, geography, employment, salary charts
│                    │  - filterable job explorer with debounced search
└────────────────────┘
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Scraping | Python, `requests`, `BeautifulSoup4` |
| Data cleaning | Python, `pandas`, `rapidfuzz` |
| Database | PostgreSQL |
| Backend API | FastAPI, SQLAlchemy |
| Frontend | React, Recharts |

---

## Features

- **Resilient scraping** — pages are only marked "seen" after the full scrape → clean → import pipeline succeeds, so a database outage never permanently skips a job posting. Handles ASP.NET WebForms `__doPostBack` pagination by extracting and replaying hidden form state.
- **Job title standardization** — an ordered, specific-to-broad regex taxonomy covering 40+ career categories (IT, healthcare, sales, logistics, skilled trades, maritime, and more), with a conservative fuzzy-matching fallback (`rapidfuzz`) for titles that don't hit an exact pattern.
- **Location standardization** — raw location strings are mapped against the official PSGC (Philippine Standard Geographic Code) reference.
- **Salary parsing and normalization** — free-text salary strings (`"P30,000/month"`, `"30K monthly"`, `"15-20k"`) are parsed into a figure and, when the pay period isn't explicitly stated (the common case on PhilJobNet), inferred from magnitude: figures at or below ₱1,000 are treated as daily, ₱1,000–5,000 as weekly, ₱8,000+ as monthly, with a genuinely ambiguous band left unguessed rather than forced. Every disclosed salary is converted to a monthly-equivalent figure so daily wages and monthly salaries can be compared and averaged correctly.
- **Deduplication** — primarily keyed on normalized job URL; a fallback key (career category + company + location) catches postings without a stable URL, and a second dedup pass on the database's actual unique constraint prevents upsert conflicts within a single import batch.
- **Interactive dashboard** — filterable by career category, region, industry, and employment type, covering hiring demand, geographic concentration, employer activity, employment-type mix, and salary distribution.
- **Job explorer** — searchable, paginated table of individual postings with a debounced search field.

---

## Project structure

```
recruitix/
├── data_pipeline/
│   ├── collectors/
│   │   └── philjobnet_collector.py
│   ├── cleaners/
│   │   ├── standardize_title.py
│   │   ├── standardize_location.py
│   │   └── standardize_salary.py
│   ├── clean_pipeline.py
│   └── import_to_postgre.py
├── data/
│   ├── raw/                  # raw scraped JSON, one file per run
│   └── processed/
│       ├── jobs_clean.csv
│       ├── data_quality_report.json
│       └── uncategorized_titles.csv
├── app/                      # FastAPI backend
│   ├── database.py
│   └── routers/
│       ├── jobs.py
│       └── analytics.py
└── frontend/                 # React app
    └── src/
        ├── pages/
        │   ├── Dashboard.jsx
        │   └── Jobs.jsx
        ├── components/
        │   ├── Header.jsx
        │   ├── StatCard.jsx
        │   ├── JobTable.jsx
        │   └── Loading.jsx
        └── api/
            └── api.js
```

---

## Getting started

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+

### 1. Clone and set up the database

```bash
createdb recruitix
```

Update the `DATABASE_URL` constant in `data_pipeline/import_to_postgre.py` (or refactor it to read from an environment variable — recommended before deploying) to point at your database:

```
postgresql://<user>:<password>@<host>:5432/recruitix
```

### 2. Run the data pipeline

```bash
cd data_pipeline
pip install -r requirements.txt

# 1. Scrape new listings
python collectors/philjobnet_collector.py

# 2. Clean and standardize
python clean_pipeline.py

# 3. Import into PostgreSQL
python import_to_postgre.py
```

`philjobnet_collector.py`'s `run_scrape_and_clean()` chains all three steps together and only marks scraped URLs as "seen" if the cleaning and import steps both succeed — safe to run on a schedule (cron, GitHub Actions, etc.).

### 3. Run the backend

```bash
cd app
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 4. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard will be available at `http://localhost:5173` (or whatever port Vite assigns), talking to the API at `http://localhost:8000`.

---

## API reference

### Jobs

| Endpoint | Description |
|---|---|
| `GET /api/jobs` | Paginated, filterable job listings. Supports `career_category`, `location`, `region`, `industry`, `employment_type`, `search`, `page`/`limit` or `offset`/`limit`. |
| `GET /api/jobs/count` | Count of jobs matching the same filters. |

### Analytics

| Endpoint | Description |
|---|---|
| `GET /api/analytics/summary` | Total jobs, companies, categories, locations, regions, and salary-disclosure count. |
| `GET /api/analytics/categories` | Job counts by standardized career category. |
| `GET /api/analytics/locations` | Job counts by location. |
| `GET /api/analytics/regions` | Job counts by region. |
| `GET /api/analytics/companies` | Job counts by employer. |
| `GET /api/analytics/job-titles` | Most common raw job titles. |
| `GET /api/analytics/industries` | Job counts by derived industry. |
| `GET /api/analytics/employment-types` | Job counts by employment type. |
| `GET /api/analytics/salary-summary` | Average, lowest, and highest monthly-equivalent salary. |
| `GET /api/analytics/salary-by-category` | Average salary per career category. |
| `GET /api/analytics/salary-distribution` | Job counts bucketed into salary ranges. |
| `GET /api/analytics/salary-range-by-category` | Lowest, average, and highest salary *across the postings within* each category. |
| `GET /api/analytics/filter-options` | Distinct values available for each filter dropdown. |

All analytics endpoints accept the same optional filters: `category`, `region`, `industry`, `employment_type`.

---

## Data notes and known limitations

- **Salary disclosure is partial.** Roughly half of scraped postings state a salary at all; the rest are marked `"Not disclosed"` rather than estimated, by design.
- **Salary period is usually inferred, not stated.** PhilJobNet postings almost never say whether a figure is daily, weekly, or monthly. The magnitude-based inference (see `clean_pipeline.py`) is a deliberate, documented heuristic, not a guarantee — postings in the genuinely ambiguous ₱5,000–8,000 band are left unclassified rather than force-guessed.
- **Every disclosed PhilJobNet salary is a single figure, not a range.** `standardize_salary.py` still supports parsing dash-separated ranges (e.g. `"P15,000 - P20,000/month"`) as a safety net for future data sources, but empirically, 0 of ~2,600 disclosed salaries in this dataset were true ranges — every posting states one number. Downstream, the pipeline collapses this to a single `salary_amount` field rather than carrying two always-identical columns through the database, API, and frontend.
- **Industry is derived, not authoritative**, when the source posting doesn't specify one — it's inferred from keyword matches against the job title and description, and defaults to `"Other"` when nothing matches.
- **Career category matching is regex-first, fuzzy-fallback.** Titles that don't match any pattern in the taxonomy and fall below the fuzzy-match confidence threshold are labeled `"Uncategorized"`; `uncategorized_titles.csv` ranks these by frequency so the taxonomy can be extended where it matters most.

---

## Roadmap

- [ ] Move `DATABASE_URL` and other secrets to environment variables before deployment
- [ ] Scheduled scraping (cron / GitHub Actions) instead of manual runs
- [ ] Expand the career-category taxonomy using `uncategorized_titles.csv`
- [ ] Add a second job source to validate the salary-range assumptions at scale
- [ ] Job detail pages with full description text

---

## Author

Built by Zein Reyes as a portfolio project demonstrating a full scrape-to-dashboard data pipeline.
