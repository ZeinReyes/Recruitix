import { useEffect, useMemo, useState } from "react";

import {
  getAnalyticsSummary,
  getCategories,
  getLocations,
  getCompanies,
  getJobTitles,
  getRegions,
  getIndustries,
  getEmploymentTypes,
  getSalarySummary,
  getSalaryByCategory,
  getSalaryDistribution,
  getSalaryRangeByCategory,
  getFilterOptions,
} from "../api/api";

import Header from "../components/Header";
import StatCard from "../components/StatCard";
import Loading from "../components/Loading";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  Legend,
  AreaChart,
  Area,
} from "recharts";


function Dashboard() {

  // =========================================================
  // STATE
  // =========================================================

  const [summary, setSummary] = useState(null);

  const [categories, setCategories] = useState([]);
  const [locations, setLocations] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [jobTitles, setJobTitles] = useState([]);
  const [regions, setRegions] = useState([]);
  const [industries, setIndustries] = useState([]);
  const [employmentTypes, setEmploymentTypes] = useState([]);

  const [salary, setSalary] = useState(null);
  const [salaryByCategory, setSalaryByCategory] = useState([]);
  const [salaryDistribution, setSalaryDistribution] = useState([]);
  const [salaryRangeByCategory, setSalaryRangeByCategory] =
    useState([]);

  const [filterOptions, setFilterOptions] = useState({
    categories: [],
    regions: [],
    industries: [],
    employment_types: [],
  });

  const [filters, setFilters] = useState({
    category: "",
    region: "",
    industry: "",
    employmentType: "",
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");


  // =========================================================
  // LOAD FILTER OPTIONS
  // =========================================================

  useEffect(() => {
    async function loadFilters() {
      try {
        const data = await getFilterOptions();

        setFilterOptions({
          categories: Array.isArray(data?.categories)
            ? data.categories
            : [],

          regions: Array.isArray(data?.regions)
            ? data.regions
            : [],

          industries: Array.isArray(data?.industries)
            ? data.industries
            : [],

          employment_types:
            Array.isArray(data?.employment_types)
              ? data.employment_types
              : [],
        });

      } catch (err) {
        console.error(
          "Unable to load filter options:",
          err
        );
      }
    }

    loadFilters();
  }, []);


  // =========================================================
  // LOAD DASHBOARD
  // =========================================================

  useEffect(() => {

    async function loadDashboard() {

      try {

        setLoading(true);
        setError("");

        const [
          summaryData,
          categoriesData,
          locationsData,
          companiesData,
          jobTitlesData,
          regionsData,
          industriesData,
          employmentTypesData,
          salaryData,
          salaryByCategoryData,
          salaryDistributionData,
          salaryRangeData,
        ] = await Promise.all([

          getAnalyticsSummary(filters),

          getCategories(10, filters),

          getLocations(10, filters),

          getCompanies(10, filters),

          getJobTitles(10, filters),

          getRegions(filters),

          getIndustries(10, filters),

          getEmploymentTypes(filters),

          getSalarySummary(filters),

          getSalaryByCategory(10, filters),

          getSalaryDistribution(filters),

          getSalaryRangeByCategory(
            10,
            filters
          ),
        ]);


        setSummary(summaryData);

        setCategories(
          Array.isArray(categoriesData)
            ? categoriesData
            : []
        );

        setLocations(
          Array.isArray(locationsData)
            ? locationsData
            : []
        );

        setCompanies(
          Array.isArray(companiesData)
            ? companiesData
            : []
        );

        setJobTitles(
          Array.isArray(jobTitlesData)
            ? jobTitlesData
            : []
        );

        setRegions(
          Array.isArray(regionsData)
            ? regionsData
            : []
        );

        setIndustries(
          Array.isArray(industriesData)
            ? industriesData
            : []
        );

        setEmploymentTypes(
          Array.isArray(employmentTypesData)
            ? employmentTypesData
            : []
        );

        setSalary(
          Array.isArray(salaryData)
            ? salaryData[0]
            : salaryData
        );

        setSalaryByCategory(
          Array.isArray(
            salaryByCategoryData
          )
            ? salaryByCategoryData
            : []
        );

        setSalaryDistribution(
          Array.isArray(
            salaryDistributionData
          )
            ? salaryDistributionData
            : []
        );

        setSalaryRangeByCategory(
          Array.isArray(
            salaryRangeData
          )
            ? salaryRangeData
            : []
        );

      } catch (err) {

        console.error(err);

        setError(
          err?.message ||
          "Unable to load analytics."
        );

      } finally {

        setLoading(false);

      }
    }

    loadDashboard();

  }, [
    filters.category,
    filters.region,
    filters.industry,
    filters.employmentType,
  ]);


  // =========================================================
  // FILTER HANDLERS
  // =========================================================

  function updateFilter(
    name,
    value
  ) {
    setFilters((previous) => ({
      ...previous,
      [name]: value,
    }));
  }


  function clearFilters() {
    setFilters({
      category: "",
      region: "",
      industry: "",
      employmentType: "",
    });
  }


  // =========================================================
  // KPI DATA
  // =========================================================

  const totalJobs =
    Number(summary?.total_jobs || 0);

  const totalCompanies =
    Number(summary?.total_companies || 0);

  const totalCategories =
    Number(summary?.total_categories || 0);

  const totalLocations =
    Number(summary?.total_locations || 0);

  const totalRegions =
    Number(summary?.total_regions || 0);

  const jobsWithSalary =
    Number(summary?.jobs_with_salary || 0);


  const salaryDisclosureRate =
    totalJobs > 0
      ? Math.round(
          (jobsWithSalary / totalJobs) *
            100
        )
      : 0;


  // =========================================================
  // SALARY
  // =========================================================
  //
  // NOTE: a single posting only ever states one salary figure
  // (see clean_pipeline.py / standardize_salary.py), so there's no
  // more separate "average minimum" vs "average maximum" KPI -- those
  // were always identical. averageSalary below is the market-wide
  // average of salary_amount_monthly across all disclosed postings.

  const averageSalary =
    Number(
      salary?.average_salary || 0
    );

  const lowestSalary =
    Number(
      salary?.lowest_salary || 0
    );

  const highestSalary =
    Number(
      salary?.highest_salary || 0
    );


  function formatCurrency(value) {

    const number = Number(value || 0);

    if (
      !number ||
      number <= 0 ||
      Number.isNaN(number)
    ) {
      return "N/A";
    }

    return `₱${Math.round(
      number
    ).toLocaleString("en-PH")}`;
  }


  // =========================================================
  // CHART DATA
  // =========================================================

  const categoryChartData =
    useMemo(() => {

      return categories.map((item) => ({
        name:
          item.career_category ||
          "Uncategorized",

        jobs:
          Number(
            item.job_count || 0
          ),
      }));

    }, [categories]);


  const locationChartData =
    useMemo(() => {

      return locations.map((item) => ({
        name:
          item.location ||
          "Unknown",

        jobs:
          Number(
            item.job_count || 0
          ),
      }));

    }, [locations]);


  const regionChartData =
    useMemo(() => {

      return regions.map((item) => ({
        name:
          item.region ||
          "Unknown",

        jobs:
          Number(
            item.job_count || 0
          ),
      }));

    }, [regions]);


  const industryChartData =
    useMemo(() => {

      return industries.map((item) => ({
        name:
          item.industry ||
          "Other",

        jobs:
          Number(
            item.job_count || 0
          ),
      }));

    }, [industries]);


  const companyChartData =
    useMemo(() => {

      return companies.map((item) => ({
        name:
          item.company ||
          "Unknown",

        jobs:
          Number(
            item.job_count || 0
          ),
      }));

    }, [companies]);


  const jobTitleChartData =
    useMemo(() => {

      return jobTitles.map((item) => ({
        name:
          item.job_title ||
          "Unknown",

        jobs:
          Number(
            item.job_count || 0
          ),
      }));

    }, [jobTitles]);


  const employmentChartData =
    useMemo(() => {

      return employmentTypes
        .filter(
          (item) =>
            item.employment_type
        )
        .map((item) => ({
          name:
            item.employment_type,

          value:
            Number(
              item.job_count || 0
            ),
        }));

    }, [employmentTypes]);


  // Single "average" bar per category now -- there's no more separate
  // minimum/maximum average, since a posting only ever states one
  // figure (see analytics.py's SALARY_EXPR note).
  const salaryCategoryChartData =
    useMemo(() => {

      return salaryByCategory.map(
        (item) => ({
          name:
            item.career_category ||
            "Uncategorized",

          average:
            Number(
              item.average_salary ||
                0
            ),

          jobs:
            Number(
              item.job_count || 0
            ),
        })
      );

    }, [salaryByCategory]);


  const salaryDistributionChartData =
    useMemo(() => {

      return salaryDistribution.map(
        (item) => ({
          name:
            item.salary_range,

          jobs:
            Number(
              item.job_count || 0
            ),
        })
      );

    }, [salaryDistribution]);


  // This chart still legitimately compares lowest/average/highest --
  // that's the spread ACROSS the many postings within a category, not
  // a single job's min/max, so it's unaffected by the salary_amount
  // consolidation.
  const salaryRangeChartData =
    useMemo(() => {

      return salaryRangeByCategory.map(
        (item) => ({
          name:
            item.career_category ||
            "Uncategorized",

          minimum:
            Number(
              item.salary_min || 0
            ),

          maximum:
            Number(
              item.salary_max || 0
            ),

          average:
            Number(
              item.average_salary || 0
            ),
        })
      );

    }, [salaryRangeByCategory]);


  // =========================================================
  // TOTAL EMPLOYMENT
  // =========================================================

  const employmentTotal =
    employmentChartData.reduce(
      (sum, item) =>
        sum + item.value,
      0
    );


  // =========================================================
  // FILTER STATUS
  // =========================================================

  const activeFilterCount =
    Object.values(filters).filter(
      Boolean
    ).length;


  // =========================================================
  // LOADING
  // =========================================================

  if (loading) {

    return (
      <Loading
        message="Loading Recruitix analytics..."
      />
    );

  }


  // =========================================================
  // ERROR
  // =========================================================

  if (error) {

    return (
      <div className="app">

        <Header />

        <main className="container">

          <div className="error-box">

            <h2>
              Unable to load dashboard
            </h2>

            <p>
              {error}
            </p>

            <p>
              Make sure the FastAPI backend
              and PostgreSQL database are
              running.
            </p>

          </div>

        </main>

      </div>
    );

  }


  // =========================================================
  // DASHBOARD
  // =========================================================

  return (

    <div className="app">

      <Header />

      <main className="container">

        {/* =================================================
            HEADER
        ================================================= */}

        <section className="dashboard-header">

          <div>

            <p className="eyebrow">
              RECRUITIX ANALYTICS
            </p>

            <h1>
              Philippine Job Market
              <br />
              Intelligence
            </h1>

            <p className="dashboard-intro">
              Explore hiring demand,
              employer activity,
              geographic concentration,
              employment types, and
              salary patterns across the
              Recruitix job market dataset.
            </p>

          </div>


          <div className="dataset-card">

            <span>
              DATASET SIZE
            </span>

            <strong>
              {totalJobs.toLocaleString()}
            </strong>

            <small>
              job postings analyzed
            </small>

          </div>

        </section>


        {/* =================================================
            FILTERS
        ================================================= */}

        <section className="dashboard-filters">

          <div className="filter-heading">

            <div>

              <p className="eyebrow">
                MARKET FILTERS
              </p>

              <h3>
                Explore a specific segment
              </h3>

            </div>

            {activeFilterCount > 0 && (
              <span className="active-filter-count">
                {activeFilterCount} active
              </span>
            )}

          </div>


          <div className="filter-grid">

            {/* CATEGORY */}

            <select
              value={filters.category}
              onChange={(event) =>
                updateFilter(
                  "category",
                  event.target.value
                )
              }
            >

              <option value="">
                All Career Categories
              </option>

              {filterOptions.categories.map(
                (item) => (
                  <option
                    key={item}
                    value={item}
                  >
                    {item}
                  </option>
                )
              )}

            </select>


            {/* REGION */}

            <select
              value={filters.region}
              onChange={(event) =>
                updateFilter(
                  "region",
                  event.target.value
                )
              }
            >

              <option value="">
                All Regions
              </option>

              {filterOptions.regions.map(
                (item) => (
                  <option
                    key={item}
                    value={item}
                  >
                    {item}
                  </option>
                )
              )}

            </select>


            {/* INDUSTRY */}

            <select
              value={filters.industry}
              onChange={(event) =>
                updateFilter(
                  "industry",
                  event.target.value
                )
              }
            >

              <option value="">
                All Industries
              </option>

              {filterOptions.industries.map(
                (item) => (
                  <option
                    key={item}
                    value={item}
                  >
                    {item}
                  </option>
                )
              )}

            </select>


            {/* EMPLOYMENT TYPE */}

            <select
              value={
                filters.employmentType
              }
              onChange={(event) =>
                updateFilter(
                  "employmentType",
                  event.target.value
                )
              }
            >

              <option value="">
                All Employment Types
              </option>

              {filterOptions.employment_types.map(
                (item) => (
                  <option
                    key={item}
                    value={item}
                  >
                    {item}
                  </option>
                )
              )}

            </select>


            <button
              className="clear-filters"
              onClick={clearFilters}
              disabled={
                activeFilterCount === 0
              }
            >
              Clear Filters
            </button>

          </div>

        </section>


        {/* =================================================
            KPI CARDS
        ================================================= */}

        <section className="stats-grid">

          <StatCard
            title="Total Jobs"
            value={totalJobs.toLocaleString()}
            description="Job postings analyzed"
          />

          <StatCard
            title="Companies"
            value={totalCompanies.toLocaleString()}
            description="Unique employers"
          />

          <StatCard
            title="Career Categories"
            value={totalCategories.toLocaleString()}
            description="Standardized categories"
          />

          <StatCard
            title="Locations"
            value={totalLocations.toLocaleString()}
            description={`${totalRegions.toLocaleString()} regions represented`}
          />

        </section>


        <section className="stats-grid">

          <StatCard
            title="Salary Disclosure"
            value={`${salaryDisclosureRate}%`}
            description={`${jobsWithSalary.toLocaleString()} postings disclose salary`}
          />

          <StatCard
            title="Average Salary"
            value={formatCurrency(
              averageSalary
            )}
            description="Market-wide average, normalized to monthly"
          />

          <StatCard
            title="Lowest Observed"
            value={formatCurrency(
              lowestSalary
            )}
            description="Lowest disclosed salary value"
          />

          <StatCard
            title="Highest Observed"
            value={formatCurrency(
              highestSalary
            )}
            description="Highest salary recorded"
          />

        </section>


        {/* =================================================
            1 + 6 + 9
            HIRING DEMAND
        ================================================= */}

        <section className="analytics-section">

          <div className="section-heading">

            <div>

              <p className="eyebrow">
                HIRING DEMAND
              </p>

              <h2>
                Where are the opportunities?
              </h2>

            </div>

            <p>
              Compare demand across career
              categories, industries, and
              individual job titles.
            </p>

          </div>


          <div className="chart-grid">

            {/* CAREER CATEGORY */}

            <div className="chart-card">

              <div className="chart-header">

                <div>

                  <h3>
                    Jobs by Career Category
                  </h3>

                  <p>
                    Top career categories
                  </p>

                </div>

              </div>

              <div className="chart-container">

                <ResponsiveContainer
                  width="100%"
                  height={380}
                >

                  <BarChart
                    data={categoryChartData}
                    layout="vertical"
                    margin={{
                      top: 5,
                      right: 20,
                      left: 20,
                      bottom: 5,
                    }}
                  >

                    <CartesianGrid
                      strokeDasharray="3 3"
                      horizontal={false}
                    />

                    <XAxis type="number" />

                    <YAxis
                      dataKey="name"
                      type="category"
                      width={145}
                      tick={{
                        fontSize: 11,
                      }}
                    />

                    <Tooltip />

                    <Bar
                      dataKey="jobs"
                      fill="#1e3a8a"
                      radius={[
                        0,
                        5,
                        5,
                        0,
                      ]}
                    />

                  </BarChart>

                </ResponsiveContainer>

              </div>

            </div>


            {/* INDUSTRY */}

            <div className="chart-card">

              <div className="chart-header">

                <div>

                  <h3>
                    Jobs by Industry
                  </h3>

                  <p>
                    Industries with the most
                    opportunities
                  </p>

                </div>

              </div>

              <div className="chart-container">

                <ResponsiveContainer
                  width="100%"
                  height={380}
                >

                  <BarChart
                    data={industryChartData}
                    layout="vertical"
                    margin={{
                      top: 5,
                      right: 20,
                      left: 20,
                      bottom: 5,
                    }}
                  >

                    <CartesianGrid
                      strokeDasharray="3 3"
                      horizontal={false}
                    />

                    <XAxis type="number" />

                    <YAxis
                      dataKey="name"
                      type="category"
                      width={145}
                      tick={{
                        fontSize: 10,
                      }}
                    />

                    <Tooltip />

                    <Bar
                      dataKey="jobs"
                      fill="#475569"
                      radius={[
                        0,
                        5,
                        5,
                        0,
                      ]}
                    />

                  </BarChart>

                </ResponsiveContainer>

              </div>

            </div>


            {/* JOB TITLES */}

            <div className="chart-card">

              <div className="chart-header">

                <div>

                  <h3>
                    Most Common Job Titles
                  </h3>

                  <p>
                    Frequently requested
                    positions
                  </p>

                </div>

              </div>

              <div className="chart-container">

                <ResponsiveContainer
                  width="100%"
                  height={380}
                >

                  <BarChart
                    data={jobTitleChartData}
                    layout="vertical"
                    margin={{
                      top: 5,
                      right: 20,
                      left: 25,
                      bottom: 5,
                    }}
                  >

                    <CartesianGrid
                      strokeDasharray="3 3"
                      horizontal={false}
                    />

                    <XAxis type="number" />

                    <YAxis
                      dataKey="name"
                      type="category"
                      width={155}
                      tick={{
                        fontSize: 10,
                      }}
                    />

                    <Tooltip />

                    <Bar
                      dataKey="jobs"
                      fill="#1e3a8a"
                      radius={[
                        0,
                        5,
                        5,
                        0,
                      ]}
                    />

                  </BarChart>

                </ResponsiveContainer>

              </div>

            </div>


            {/* JOB DEMAND COMPARISON */}

            <div className="chart-card">

              <div className="chart-header">

                <div>

                  <h3>
                    Job-Demand Comparison
                  </h3>

                  <p>
                    Compare the most active
                    career categories
                  </p>

                </div>

              </div>

              <div className="chart-container">

                <ResponsiveContainer
                  width="100%"
                  height={380}
                >

                  <BarChart
                    data={categoryChartData.slice(
                      0,
                      8
                    )}
                    margin={{
                      top: 10,
                      right: 20,
                      left: 5,
                      bottom: 65,
                    }}
                  >

                    <CartesianGrid
                      strokeDasharray="3 3"
                    />

                    <XAxis
                      dataKey="name"
                      angle={-35}
                      textAnchor="end"
                      interval={0}
                      height={85}
                      tick={{
                        fontSize: 10,
                      }}
                    />

                    <YAxis />

                    <Tooltip />

                    <Bar
                      dataKey="jobs"
                      fill="#1e3a8a"
                      radius={[
                        5,
                        5,
                        0,
                        0,
                      ]}
                    />

                  </BarChart>

                </ResponsiveContainer>

              </div>

            </div>

          </div>

        </section>


        {/* =================================================
            3 + 10
            GEOGRAPHIC ANALYSIS
        ================================================= */}

        <section className="analytics-section">

          <div className="section-heading">

            <div>

              <p className="eyebrow">
                GEOGRAPHIC ANALYSIS
              </p>

              <h2>
                Where are jobs concentrated?
              </h2>

            </div>

            <p>
              Explore regional and local
              concentrations of job
              opportunities.
            </p>

          </div>


          <div className="chart-grid">

            {/* REGIONS */}

            <div className="chart-card">

              <div className="chart-header">

                <div>

                  <h3>
                    Jobs by Region
                  </h3>

                  <p>
                    Regional distribution
                  </p>

                </div>

              </div>

              <div className="chart-container">

                <ResponsiveContainer
                  width="100%"
                  height={400}
                >

                  <BarChart
                    data={regionChartData}
                    margin={{
                      top: 10,
                      right: 20,
                      left: 10,
                      bottom: 75,
                    }}
                  >

                    <CartesianGrid
                      strokeDasharray="3 3"
                    />

                    <XAxis
                      dataKey="name"
                      angle={-35}
                      textAnchor="end"
                      interval={0}
                      height={95}
                      tick={{
                        fontSize: 10,
                      }}
                    />

                    <YAxis />

                    <Tooltip />

                    <Bar
                      dataKey="jobs"
                      fill="#1e3a8a"
                      radius={[
                        5,
                        5,
                        0,
                        0,
                      ]}
                    />

                  </BarChart>

                </ResponsiveContainer>

              </div>

            </div>


            {/* LOCATIONS */}

            <div className="chart-card">

              <div className="chart-header">

                <div>

                  <h3>
                    Geographic Concentration
                  </h3>

                  <p>
                    Locations with the most
                    postings
                  </p>

                </div>

              </div>

              <div className="chart-container">

                <ResponsiveContainer
                  width="100%"
                  height={400}
                >

                  <BarChart
                    data={locationChartData}
                    layout="vertical"
                    margin={{
                      top: 5,
                      right: 20,
                      left: 20,
                      bottom: 5,
                    }}
                  >

                    <CartesianGrid
                      strokeDasharray="3 3"
                      horizontal={false}
                    />

                    <XAxis type="number" />

                    <YAxis
                      dataKey="name"
                      type="category"
                      width={135}
                      tick={{
                        fontSize: 10,
                      }}
                    />

                    <Tooltip />

                    <Bar
                      dataKey="jobs"
                      fill="#475569"
                      radius={[
                        0,
                        5,
                        5,
                        0,
                      ]}
                    />

                  </BarChart>

                </ResponsiveContainer>

              </div>

            </div>

          </div>

        </section>


        {/* =================================================
            4
            EMPLOYMENT
        ================================================= */}

        <section className="analytics-section">

          <div className="section-heading">

            <div>

              <p className="eyebrow">
                EMPLOYMENT ANALYSIS
              </p>

              <h2>
                How are companies hiring?
              </h2>

            </div>

            <p>
              Distribution of employment
              arrangements in the dataset.
            </p>

          </div>


          <div className="chart-grid">

            <div className="chart-card">

              <div className="chart-header">

                <div>

                  <h3>
                    Employment-Type Distribution
                  </h3>

                  <p>
                    Job arrangements
                  </p>

                </div>

              </div>


              <div className="pie-chart-container">

                <ResponsiveContainer
                  width="100%"
                  height={380}
                >

                  <PieChart>

                    <Pie
                      data={
                        employmentChartData
                      }
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={120}
                      innerRadius={60}
                      paddingAngle={2}
                    >

                      {employmentChartData.map(
                        (_, index) => (

                          <Cell
                            key={
                              `employment-${index}`
                            }
                            fill={
                              [
                                "#1e3a8a",
                                "#3b82f6",
                                "#60a5fa",
                                "#93c5fd",
                                "#64748b",
                                "#94a3b8",
                                "#cbd5e1",
                                "#475569",
                              ][
                                index % 8
                              ]
                            }
                          />

                        )
                      )}

                    </Pie>

                    <Tooltip />

                    <Legend />

                  </PieChart>

                </ResponsiveContainer>

              </div>

              <div className="chart-footnote">
                {employmentTotal.toLocaleString()}
                {" "}classified postings
              </div>

            </div>


            {/* EMPLOYMENT BAR */}

            <div className="chart-card">

              <div className="chart-header">

                <div>

                  <h3>
                    Employment-Type Comparison
                  </h3>

                  <p>
                    Compare hiring volume
                  </p>

                </div>

              </div>

              <div className="chart-container">

                <ResponsiveContainer
                  width="100%"
                  height={380}
                >

                  <BarChart
                    data={
                      employmentChartData
                    }
                    layout="vertical"
                    margin={{
                      top: 5,
                      right: 20,
                      left: 20,
                      bottom: 5,
                    }}
                  >

                    <CartesianGrid
                      strokeDasharray="3 3"
                      horizontal={false}
                    />

                    <XAxis type="number" />

                    <YAxis
                      dataKey="name"
                      type="category"
                      width={125}
                      tick={{
                        fontSize: 11,
                      }}
                    />

                    <Tooltip />

                    <Bar
                      dataKey="value"
                      fill="#1e3a8a"
                      radius={[
                        0,
                        5,
                        5,
                        0,
                      ]}
                    />

                  </BarChart>

                </ResponsiveContainer>

              </div>

            </div>

          </div>

        </section>


        {/* =================================================
            5
            EMPLOYERS
        ================================================= */}

        <section className="analytics-section">

          <div className="section-heading">

            <div>

              <p className="eyebrow">
                EMPLOYER ANALYSIS
              </p>

              <h2>
                Who is hiring?
              </h2>

            </div>

            <p>
              Companies with the highest
              number of job postings.
            </p>

          </div>


          <div className="chart-card">

            <div className="chart-header">

              <div>

                <h3>
                  Top Employers
                </h3>

                <p>
                  Companies with the most
                  postings
                </p>

              </div>

            </div>


            <div className="chart-container">

              <ResponsiveContainer
                width="100%"
                height={430}
              >

                <BarChart
                  data={companyChartData}
                  layout="vertical"
                  margin={{
                    top: 5,
                    right: 20,
                    left: 30,
                    bottom: 5,
                  }}
                >

                  <CartesianGrid
                    strokeDasharray="3 3"
                    horizontal={false}
                  />

                  <XAxis type="number" />

                  <YAxis
                    dataKey="name"
                    type="category"
                    width={175}
                    tick={{
                      fontSize: 10,
                    }}
                  />

                  <Tooltip />

                  <Bar
                    dataKey="jobs"
                    fill="#1e3a8a"
                    radius={[
                      0,
                      5,
                      5,
                      0,
                    ]}
                  />

                </BarChart>

              </ResponsiveContainer>

            </div>

          </div>

        </section>


        {/* =================================================
            2
            SALARY BY CATEGORY
        ================================================= */}

        <section className="analytics-section">

          <div className="section-heading">

            <div>

              <p className="eyebrow">
                SALARY ANALYSIS
              </p>

              <h2>
                What does the market pay?
              </h2>

            </div>

            <p>
              Compare advertised salary
              levels across career
              categories.
            </p>

          </div>


          {/* SALARY KPI */}

          <section className="salary-grid">

            <div className="salary-card">

              <span>
                AVERAGE SALARY
              </span>

              <strong>
                {formatCurrency(
                  averageSalary
                )}
              </strong>

              <p>
                Market-wide average,
                normalized to monthly.
              </p>

            </div>


            <div className="salary-card">

              <span>
                LOWEST OBSERVED
              </span>

              <strong>
                {formatCurrency(
                  lowestSalary
                )}
              </strong>

              <p>
                Lowest disclosed
                salary value.
              </p>

            </div>


            <div className="salary-card">

              <span>
                HIGHEST OBSERVED
              </span>

              <strong>
                {formatCurrency(
                  highestSalary
                )}
              </strong>

              <p>
                Highest disclosed
                salary value.
              </p>

            </div>


            <div className="salary-card">

              <span>
                SALARY DISCLOSURE
              </span>

              <strong>
                {salaryDisclosureRate}%
              </strong>

              <p>
                Postings that disclose
                a salary figure.
              </p>

            </div>

          </section>


          {/* SALARY BY CATEGORY */}

          <div className="chart-card salary-chart-card">

            <div className="chart-header">

              <div>

                <h3>
                  Salary by Career Category
                </h3>

                <p>
                  Average advertised salary,
                  normalized to monthly
                </p>

              </div>

            </div>


            <div className="chart-container">

              <ResponsiveContainer
                width="100%"
                height={430}
              >

                <BarChart
                  data={
                    salaryCategoryChartData
                  }
                  layout="vertical"
                  margin={{
                    top: 5,
                    right: 25,
                    left: 25,
                    bottom: 5,
                  }}
                >

                  <CartesianGrid
                    strokeDasharray="3 3"
                    horizontal={false}
                  />

                  <XAxis
                    type="number"
                    tickFormatter={(value) =>
                      `₱${(
                        value / 1000
                      ).toFixed(0)}K`
                    }
                  />

                  <YAxis
                    dataKey="name"
                    type="category"
                    width={155}
                    tick={{
                      fontSize: 10,
                    }}
                  />

                  <Tooltip
                    formatter={(value) =>
                      formatCurrency(value)
                    }
                  />

                  <Legend />

                  <Bar
                    dataKey="average"
                    name="Avg. Salary"
                    fill="#1e3a8a"
                  />

                </BarChart>

              </ResponsiveContainer>

            </div>

          </div>

        </section>


        {/* =================================================
            7
            SALARY DISTRIBUTION
        ================================================= */}

        <section className="analytics-section">

          <div className="chart-card">

            <div className="chart-header">

              <div>

                <h3>
                  Salary Distribution
                </h3>

                <p>
                  Number of postings within
                  each salary range
                </p>

              </div>

            </div>


            <div className="chart-container">

              <ResponsiveContainer
                width="100%"
                height={400}
              >

                <AreaChart
                  data={
                    salaryDistributionChartData
                  }
                  margin={{
                    top: 10,
                    right: 20,
                    left: 10,
                    bottom: 65,
                  }}
                >

                  <CartesianGrid
                    strokeDasharray="3 3"
                  />

                  <XAxis
                    dataKey="name"
                    angle={-30}
                    textAnchor="end"
                    interval={0}
                    height={80}
                    tick={{
                      fontSize: 10,
                    }}
                  />

                  <YAxis />

                  <Tooltip />

                  <Area
                    type="monotone"
                    dataKey="jobs"
                    name="Job Postings"
                    stroke="#1e3a8a"
                    fill="#bfdbfe"
                  />

                </AreaChart>

              </ResponsiveContainer>

            </div>

          </div>

        </section>


        {/* =================================================
            8
            SALARY RANGE BY CATEGORY
        ================================================= */}

        <section className="analytics-section">

          <div className="chart-card">

            <div className="chart-header">

              <div>

                <h3>
                  Salary Range by Career Category
                </h3>

                <p>
                  Lowest, average, and highest
                  advertised values across
                  postings in each category
                </p>

              </div>

            </div>


            <div className="chart-container">

              <ResponsiveContainer
                width="100%"
                height={430}
              >

                <BarChart
                  data={
                    salaryRangeChartData
                  }
                  layout="vertical"
                  margin={{
                    top: 5,
                    right: 25,
                    left: 25,
                    bottom: 5,
                  }}
                >

                  <CartesianGrid
                    strokeDasharray="3 3"
                    horizontal={false}
                  />

                  <XAxis
                    type="number"
                    tickFormatter={(value) =>
                      `₱${(
                        value / 1000
                      ).toFixed(0)}K`
                    }
                  />

                  <YAxis
                    dataKey="name"
                    type="category"
                    width={155}
                    tick={{
                      fontSize: 10,
                    }}
                  />

                  <Tooltip
                    formatter={(value) =>
                      formatCurrency(value)
                    }
                  />

                  <Legend />

                  <Bar
                    dataKey="minimum"
                    name="Lowest"
                    fill="#64748b"
                  />

                  <Bar
                    dataKey="average"
                    name="Average"
                    fill="#1e3a8a"
                  />

                  <Bar
                    dataKey="maximum"
                    name="Highest"
                    fill="#93c5fd"
                  />

                </BarChart>

              </ResponsiveContainer>

            </div>

          </div>

        </section>


        {/* =================================================
            METHODOLOGY
        ================================================= */}

        <section className="methodology-panel">

          <div>

            <p className="eyebrow">
              DATASET OVERVIEW
            </p>

            <h2>
              About these insights
            </h2>

            <p>
              Recruitix aggregates and
              standardizes job postings to
              make Philippine labor-market
              patterns easier to explore.
              Metrics are calculated from
              the database and update when
              filters are applied.
            </p>

          </div>


          <div className="methodology-grid">

            <div>

              <strong>
                {totalJobs.toLocaleString()}
              </strong>

              <span>
                Total postings
              </span>

            </div>


            <div>

              <strong>
                {totalCompanies.toLocaleString()}
              </strong>

              <span>
                Employers
              </span>

            </div>


            <div>

              <strong>
                {totalLocations.toLocaleString()}
              </strong>

              <span>
                Locations
              </span>

            </div>


            <div>

              <strong>
                {salaryDisclosureRate}%
              </strong>

              <span>
                Salary disclosure
              </span>

            </div>

          </div>

        </section>

      </main>

    </div>

  );
}


export default Dashboard;