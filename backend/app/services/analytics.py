from app.database import get_connection


def get_salary_statistics():
    """
    Calculate overall salary statistics.
    """

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    COUNT(*) AS jobs_with_salary,
                    AVG(salary_min),
                    AVG(salary_max),
                    MIN(salary_min),
                    MAX(salary_max)
                FROM jobs
                WHERE salary_disclosed = TRUE
                  AND salary_min IS NOT NULL
            """)

            return cursor.fetchone()

    finally:
        conn.close()