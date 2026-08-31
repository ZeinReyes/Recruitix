const PERIOD_LABELS = {
  daily: "/day",
  weekly: "/week",
  monthly: "/month",
  annual: "/year",
  hourly: "/hour",
};

function formatSalary(job) {
  if (!job.salary_disclosed || job.salary_amount == null) {
    return "Not disclosed";
  }

  const amount = `₱${Number(job.salary_amount).toLocaleString()}`;

  // Prefer the period actually used for monthly normalization (stated
  // on the posting, or inferred by magnitude) over the raw parsed
  // salary_period, which is usually blank -- PhilJobNet rarely states
  // the period explicitly.
  const period = job.salary_period_used || job.salary_period;
  const periodLabel = PERIOD_LABELS[period];

  if (!periodLabel) {
    // No period could be determined at all (e.g. genuinely ambiguous
    // magnitude) -- show the raw figure without guessing a unit.
    return amount;
  }

  // Flag guessed periods so the table doesn't overstate confidence --
  // "estimated" here means the period came from magnitude inference,
  // not text on the posting itself.
  return job.salary_period_estimated
    ? `${amount}${periodLabel} (est.)`
    : `${amount}${periodLabel}`;
}

function JobTable({ jobs }) {
  if (!jobs || jobs.length === 0) {
    return (
      <div className="empty-state">
        No jobs found.
      </div>
    );
  }

  return (
    <div className="table-container">
      <table className="job-table">
        <thead>
          <tr>
            <th>Job Title</th>
            <th>Category</th>
            <th>Company</th>
            <th>Location</th>
            <th>Salary</th>
            <th>Employment Type</th>
            <th>Posting</th>
          </tr>
        </thead>

        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>

              {/* JOB TITLE */}
              <td>
                {job.job_url ? (
                  <a
                    href={job.job_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="job-title-link"
                  >
                    <strong>{job.job_title}</strong>
                  </a>
                ) : (
                  <strong>{job.job_title}</strong>
                )}
              </td>

              {/* CATEGORY */}
              <td>
                <span className="category-badge">
                  {job.career_category || "Uncategorized"}
                </span>
              </td>

              {/* COMPANY */}
              <td>
                {job.company || "Unknown"}
              </td>

              {/* LOCATION */}
              <td>
                {job.location || "Unknown"}
              </td>

              {/* SALARY */}
              <td>
                {formatSalary(job)}
              </td>

              {/* EMPLOYMENT TYPE */}
              <td>
                {job.employment_type || "Not specified"}
              </td>

              {/* ORIGINAL POSTING */}
              <td>
                {job.job_url ? (
                  <a
                    href={job.job_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="posting-link"
                  >
                    View Posting ↗
                  </a>
                ) : (
                  <span className="no-link">
                    Unavailable
                  </span>
                )}
              </td>

            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default JobTable;