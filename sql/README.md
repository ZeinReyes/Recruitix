# sql/

Raw SQL files (Phase 5 in the plan).

- `schema.sql` — CREATE TABLE statements for the PostgreSQL database (companies, jobs, salaries, skills, job_skills, locations, industries, sources)
- `cleaning.sql` — any cleaning/dedup logic you prefer to do in SQL rather than Python
- `analysis.sql` — the analysis queries: top jobs, salary stats, skills, trends, etc.
