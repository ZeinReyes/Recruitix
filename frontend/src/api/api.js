const API_BASE_URL = "http://127.0.0.1:8000";


// =========================================================
// HELPER
// =========================================================

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;

    try {
      const errorData = await response.json();

      if (errorData?.detail) {
        if (Array.isArray(errorData.detail)) {
          message = errorData.detail
            .map((item) => item.msg)
            .join(", ");
        } else {
          message = errorData.detail;
        }
      }
    } catch {
      try {
        const errorText = await response.text();

        if (errorText) {
          message = `${message}: ${errorText.substring(0, 200)}`;
        }
      } catch {
        // Ignore response parsing errors
      }
    }

    throw new Error(message);
  }

  const contentType =
    response.headers.get("content-type") || "";

  if (!contentType.includes("application/json")) {
    const text = await response.text();

    throw new Error(
      `Expected JSON but received ${contentType || "unknown content type"}: ${text.substring(0, 200)}`
    );
  }

  return response.json();
}


// =========================================================
// ANALYTICS FILTER BUILDER
// =========================================================

function buildAnalyticsQueryParams(filters = {}) {
  const params = new URLSearchParams();

  if (filters.category) {
    params.set("category", filters.category);
  }

  if (filters.region) {
    params.set("region", filters.region);
  }

  if (filters.industry) {
    params.set("industry", filters.industry);
  }

  if (filters.employmentType) {
    params.set(
      "employment_type",
      filters.employmentType
    );
  }

  return params;
}


// =========================================================
// SUMMARY
// =========================================================

export async function getAnalyticsSummary(
  filters = {}
) {
  const params =
    buildAnalyticsQueryParams(filters);

  const query = params.toString();

  return fetchJSON(
    `${API_BASE_URL}/api/analytics/summary${
      query ? `?${query}` : ""
    }`
  );
}


// =========================================================
// CAREER CATEGORIES
// =========================================================

export async function getCategories(
  limit = 10,
  filters = {}
) {
  const params =
    buildAnalyticsQueryParams(filters);

  params.set(
    "limit",
    String(Number(limit) || 10)
  );

  return fetchJSON(
    `${API_BASE_URL}/api/analytics/categories?${params.toString()}`
  );
}


// =========================================================
// LOCATIONS
// =========================================================

export async function getLocations(
  limit = 10,
  filters = {}
) {
  const params =
    buildAnalyticsQueryParams(filters);

  params.set(
    "limit",
    String(Number(limit) || 10)
  );

  return fetchJSON(
    `${API_BASE_URL}/api/analytics/locations?${params.toString()}`
  );
}


// =========================================================
// REGIONS
// =========================================================

export async function getRegions(
  filters = {}
) {
  const params =
    buildAnalyticsQueryParams(filters);

  const query = params.toString();

  return fetchJSON(
    `${API_BASE_URL}/api/analytics/regions${
      query ? `?${query}` : ""
    }`
  );
}


// =========================================================
// COMPANIES
// =========================================================

export async function getCompanies(
  limit = 10,
  filters = {}
) {
  const params =
    buildAnalyticsQueryParams(filters);

  params.set(
    "limit",
    String(Number(limit) || 10)
  );

  return fetchJSON(
    `${API_BASE_URL}/api/analytics/companies?${params.toString()}`
  );
}


// =========================================================
// JOB TITLES
// =========================================================

export async function getJobTitles(
  limit = 10,
  filters = {}
) {
  const params =
    buildAnalyticsQueryParams(filters);

  params.set(
    "limit",
    String(Number(limit) || 10)
  );

  return fetchJSON(
    `${API_BASE_URL}/api/analytics/job-titles?${params.toString()}`
  );
}


// =========================================================
// INDUSTRIES
// =========================================================

export async function getIndustries(
  limit = 10,
  filters = {}
) {
  const params =
    buildAnalyticsQueryParams(filters);

  params.set(
    "limit",
    String(Number(limit) || 10)
  );

  return fetchJSON(
    `${API_BASE_URL}/api/analytics/industries?${params.toString()}`
  );
}


// =========================================================
// EMPLOYMENT TYPES
// =========================================================

export async function getEmploymentTypes(
  filters = {}
) {
  const params =
    buildAnalyticsQueryParams(filters);

  const query = params.toString();

  return fetchJSON(
    `${API_BASE_URL}/api/analytics/employment-types${
      query ? `?${query}` : ""
    }`
  );
}


// =========================================================
// SALARY SUMMARY
// =========================================================

export async function getSalarySummary(
  filters = {}
) {
  const params =
    buildAnalyticsQueryParams(filters);

  const query = params.toString();

  return fetchJSON(
    `${API_BASE_URL}/api/analytics/salary-summary${
      query ? `?${query}` : ""
    }`
  );
}


// =========================================================
// SALARY BY CAREER CATEGORY
// =========================================================

export async function getSalaryByCategory(
  limit = 10,
  filters = {}
) {
  const params =
    buildAnalyticsQueryParams(filters);

  params.set(
    "limit",
    String(Number(limit) || 10)
  );

  return fetchJSON(
    `${API_BASE_URL}/api/analytics/salary-by-category?${params.toString()}`
  );
}


// =========================================================
// SALARY DISTRIBUTION
// =========================================================

export async function getSalaryDistribution(
  filters = {}
) {
  const params =
    buildAnalyticsQueryParams(filters);

  const query = params.toString();

  return fetchJSON(
    `${API_BASE_URL}/api/analytics/salary-distribution${
      query ? `?${query}` : ""
    }`
  );
}


// =========================================================
// SALARY RANGE BY CATEGORY
// =========================================================

export async function getSalaryRangeByCategory(
  limit = 10,
  filters = {}
) {
  const params =
    buildAnalyticsQueryParams(filters);

  params.set(
    "limit",
    String(Number(limit) || 10)
  );

  return fetchJSON(
    `${API_BASE_URL}/api/analytics/salary-range-by-category?${params.toString()}`
  );
}


// =========================================================
// FILTER OPTIONS
// =========================================================

export async function getFilterOptions() {
  return fetchJSON(
    `${API_BASE_URL}/api/analytics/filter-options`
  );
}


// =========================================================
// JOBS FILTER BUILDER
// =========================================================
//
// IMPORTANT:
// Jobs router uses:
//
// career_category
// location
// region
// industry
// employment_type
// search
// page
// limit
//
// These are different from the Analytics parameter names.
//

function buildJobsQueryParams(filters = {}) {
  const params = new URLSearchParams();

  if (filters.career_category) {
    params.set(
      "career_category",
      filters.career_category
    );
  }

  if (filters.location) {
    params.set(
      "location",
      filters.location
    );
  }

  if (filters.region) {
    params.set(
      "region",
      filters.region
    );
  }

  if (filters.industry) {
    params.set(
      "industry",
      filters.industry
    );
  }

  if (filters.employment_type) {
    params.set(
      "employment_type",
      filters.employment_type
    );
  }

  if (filters.search) {
    params.set(
      "search",
      filters.search
    );
  }

  return params;
}


// =========================================================
// GET JOBS
// =========================================================

export async function getJobs({
  page = 1,
  limit = 20,
  career_category = "",
  location = "",
  region = "",
  industry = "",
  employment_type = "",
  search = "",
} = {}) {

  // -------------------------------------------------------
  // SAFELY CONVERT PAGE
  // -------------------------------------------------------

  const numericPage = Number(page);

  const safePage =
    Number.isFinite(numericPage) &&
    numericPage >= 1
      ? Math.floor(numericPage)
      : 1;


  // -------------------------------------------------------
  // SAFELY CONVERT LIMIT
  // -------------------------------------------------------

  const numericLimit = Number(limit);

  const safeLimit =
    Number.isFinite(numericLimit) &&
    numericLimit >= 1
      ? Math.min(Math.floor(numericLimit), 100)
      : 20;


  // -------------------------------------------------------
  // BUILD PARAMETERS
  // -------------------------------------------------------

  const params = buildJobsQueryParams({
    career_category,
    location,
    region,
    industry,
    employment_type,
    search,
  });


  // -------------------------------------------------------
  // PAGINATION
  // -------------------------------------------------------

  params.set(
    "page",
    String(safePage)
  );

  params.set(
    "limit",
    String(safeLimit)
  );


  // -------------------------------------------------------
  // REQUEST
  // -------------------------------------------------------

  return fetchJSON(
    `${API_BASE_URL}/api/jobs/?${params.toString()}`
  );
}


// =========================================================
// JOB COUNT
// =========================================================

export async function getJobCount(
  filters = {}
) {

  const params = buildJobsQueryParams({
    career_category:
      filters.career_category ||
      filters.category ||
      "",

    location:
      filters.location || "",

    region:
      filters.region || "",

    industry:
      filters.industry || "",

    employment_type:
      filters.employment_type ||
      filters.employmentType ||
      "",

    search:
      filters.search || "",
  });


  return fetchJSON(
    `${API_BASE_URL}/api/jobs/count${
      params.toString()
        ? `?${params.toString()}`
        : ""
    }`
  );
}