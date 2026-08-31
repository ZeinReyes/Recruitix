import { useEffect, useMemo, useRef, useState } from "react";

import {
  getCategories,
  getJobCount,
  getJobs,
  getLocations,
} from "../api/api";

import Header from "../components/Header";
import JobTable from "../components/JobTable";
import Loading from "../components/Loading";


const JOBS_PER_PAGE = 10;
const SEARCH_DEBOUNCE_MS = 350;


function Jobs() {

  // --------------------------------------------------
  // JOB DATA
  // --------------------------------------------------

  const [jobs, setJobs] = useState([]);

  const [totalJobs, setTotalJobs] = useState(0);


  // --------------------------------------------------
  // FILTERS
  // --------------------------------------------------
  //
  // searchInput is what the <input> is actually bound to -- it updates
  // on every keystroke so typing always feels instant and the field
  // never fights the user for control.
  //
  // search is the debounced value that actually gets sent to the API.
  // Splitting these two means a fetch isn't fired (and loading state
  // isn't touched) on every single character.
  //

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");

  const [category, setCategory] =
    useState("All");

  const [location, setLocation] =
    useState("All");


  // --------------------------------------------------
  // FILTER OPTIONS
  // --------------------------------------------------

  const [categories, setCategories] =
    useState(["All"]);

  const [locations, setLocations] =
    useState(["All"]);


  // --------------------------------------------------
  // PAGINATION
  // --------------------------------------------------

  const [currentPage, setCurrentPage] =
    useState(1);


  // --------------------------------------------------
  // STATE
  // --------------------------------------------------
  //
  // hasLoadedOnce controls whether we show the full-page <Loading>
  // screen. It's only ever false before the very first successful
  // fetch. Every fetch after that (typing a search term, changing a
  // filter, changing page) uses `refreshing` instead, which does NOT
  // unmount the filters/input -- that unmounting was exactly why the
  // search box lost focus on every keystroke.
  //

  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const [error, setError] =
    useState("");


  // ==================================================
  // DEBOUNCE SEARCH INPUT -> search
  // ==================================================

  useEffect(() => {

    const timeoutId = setTimeout(() => {
      setSearch(searchInput);
      setCurrentPage(1);
    }, SEARCH_DEBOUNCE_MS);

    return () => clearTimeout(timeoutId);

  }, [searchInput]);


  // ==================================================
  // LOAD FILTER OPTIONS
  // ==================================================

  useEffect(() => {

    async function loadFilters() {

      try {

        const [
          categoryData,
          locationData,
        ] = await Promise.all([
          getCategories(),
          getLocations(100),
        ]);


        const categoryValues =
          Array.isArray(categoryData)
            ? categoryData
            : [];


        setCategories([
          "All",
          ...categoryValues
            .map(
              (item) =>
                item.career_category
            )
            .filter(Boolean),
        ]);


        const locationValues =
          Array.isArray(locationData)
            ? locationData
            : [];


        setLocations([
          "All",
          ...locationValues
            .map(
              (item) =>
                item.location
            )
            .filter(Boolean),
        ]);

      } catch (err) {

        console.error(
          "Failed to load filter options:",
          err
        );

      }

    }


    loadFilters();

  }, []);


  // ==================================================
  // LOAD JOBS
  // ==================================================

  useEffect(() => {

    // Guards against a slow earlier request overwriting a newer one
    // (e.g. typing quickly and having an older response land last).
    let isCurrent = true;

    async function loadJobs() {

      try {

        if (hasLoadedOnce) {
          setRefreshing(true);
        }

        setError("");


        const categoryValue =
          category === "All"
            ? ""
            : category;


        const locationValue =
          location === "All"
            ? ""
            : location;


        const offset =
          (currentPage - 1) *
          JOBS_PER_PAGE;


        // --------------------------------------------
        // Load current page
        // --------------------------------------------

        const jobsData =
          await getJobs({

            limit: JOBS_PER_PAGE,

            offset,

            search,

            career_category:
              categoryValue,

            location:
              locationValue,

          });


        const jobData =
          Array.isArray(jobsData)
            ? jobsData
            : jobsData?.jobs || [];


        // --------------------------------------------
        // Load filtered count
        // --------------------------------------------

        const countData =
          await getJobCount({

            search,

            career_category:
              categoryValue,

            location:
              locationValue,

          });


        if (!isCurrent) {
          return;
        }

        setJobs(jobData);

        setTotalJobs(
          countData?.count || 0
        );


      } catch (err) {

        if (!isCurrent) {
          return;
        }

        setError(
          err.message
        );

      } finally {

        if (!isCurrent) {
          return;
        }

        setHasLoadedOnce(true);
        setRefreshing(false);

      }

    }


    loadJobs();

    return () => {
      isCurrent = false;
    };

  }, [
    currentPage,
    search,
    category,
    location,
  ]);


  // ==================================================
  // PAGINATION
  // ==================================================

  const totalPages =
    Math.max(
      1,
      Math.ceil(
        totalJobs /
        JOBS_PER_PAGE
      )
    );


  // ==================================================
  // FILTER HANDLERS
  // ==================================================

  function handleSearchInput(value) {
    // Only updates the local, un-debounced field state -- the actual
    // `search` value (and therefore the API call + page reset) happens
    // in the debounce effect above.
    setSearchInput(value);
  }


  function handleCategory(value) {

    setCategory(value);

    setCurrentPage(1);

  }


  function handleLocation(value) {

    setLocation(value);

    setCurrentPage(1);

  }


  // ==================================================
  // PAGINATION
  // ==================================================

  function goToPage(page) {

    if (
      page < 1 ||
      page > totalPages
    ) {
      return;
    }


    setCurrentPage(page);


    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });

  }


  function getPageNumbers() {

    const pages = [];


    if (totalPages <= 7) {

      for (
        let i = 1;
        i <= totalPages;
        i++
      ) {

        pages.push(i);

      }

      return pages;

    }


    pages.push(1);


    if (currentPage > 4) {

      pages.push("...");

    }


    const start =
      Math.max(
        2,
        currentPage - 1
      );


    const end =
      Math.min(
        totalPages - 1,
        currentPage + 1
      );


    for (
      let i = start;
      i <= end;
      i++
    ) {

      pages.push(i);

    }


    if (
      currentPage <
      totalPages - 3
    ) {

      pages.push("...");

    }


    pages.push(totalPages);


    return pages;

  }


  // ==================================================
  // CURRENT RANGE
  // ==================================================

  const startIndex =
    totalJobs === 0
      ? 0
      : (currentPage - 1) *
        JOBS_PER_PAGE +
        1;


  const endIndex =
    Math.min(
      currentPage *
        JOBS_PER_PAGE,
      totalJobs
    );


  // ==================================================
  // INITIAL LOADING (full-page, only before first fetch ever completes)
  // ==================================================

  if (!hasLoadedOnce && !error) {

    return (
      <Loading
        message="Loading jobs..."
      />
    );

  }


  // ==================================================
  // ERROR
  // ==================================================

  if (error && !hasLoadedOnce) {

    return (
      <div className="app">

        <Header />

        <main className="container">

          <div className="error-box">

            <h2>
              Unable to load jobs
            </h2>

            <p>
              {error}
            </p>

          </div>

        </main>

      </div>
    );

  }


  // ==================================================
  // PAGE
  // ==================================================

  return (

    <div className="app">

      <Header />


      <main className="container">

        {/* ------------------------------------------ */}
        {/* PAGE HEADER */}
        {/* ------------------------------------------ */}

        <div className="page-heading">

          <p className="eyebrow">
            JOB EXPLORER
          </p>


          <h2>
            Find Jobs
          </h2>


          <p>
            Explore job opportunities
            collected and standardized
            by Recruitix.
          </p>

        </div>


        {/* ------------------------------------------ */}
        {/* FILTERS */}
        {/* ------------------------------------------ */}

        <section className="filters">

          <input
            type="text"
            placeholder="Search job title or company..."
            value={searchInput}
            onChange={(e) =>
              handleSearchInput(
                e.target.value
              )
            }
          />


          <select
            value={category}
            onChange={(e) =>
              handleCategory(
                e.target.value
              )
            }
          >

            {categories.map(
              (item) => (

                <option
                  value={item}
                  key={item}
                >
                  {item}
                </option>

              )
            )}

          </select>


          <select
            value={location}
            onChange={(e) =>
              handleLocation(
                e.target.value
              )
            }
          >

            {locations.map(
              (item) => (

                <option
                  value={item}
                  key={item}
                >
                  {item}
                </option>

              )
            )}

          </select>

        </section>


        {/* ------------------------------------------ */}
        {/* ERROR (non-initial -- keeps filters mounted) */}
        {/* ------------------------------------------ */}

        {error && (

          <div className="error-box">

            <h2>
              Unable to load jobs
            </h2>

            <p>
              {error}
            </p>

          </div>

        )}


        {/* ------------------------------------------ */}
        {/* RESULTS */}
        {/* ------------------------------------------ */}

        {!error && (

          <div className="results-count">

            {refreshing ? (

              "Updating results..."

            ) : (

              <>

                Showing{" "}

                <strong>
                  {startIndex.toLocaleString()}
                </strong>

                {" - "}

                <strong>
                  {endIndex.toLocaleString()}
                </strong>

                {" of "}

                <strong>
                  {totalJobs.toLocaleString()}
                </strong>

                {" jobs"}

              </>

            )}

          </div>

        )}


        {/* ------------------------------------------ */}
        {/* TABLE */}
        {/* ------------------------------------------ */}

        {!error && (

          jobs.length > 0 ? (

            <JobTable
              jobs={jobs}
            />

          ) : (

            <div className="no-results">

              <h3>
                No jobs found
              </h3>

              <p>
                Try changing your
                search or filters.
              </p>

            </div>

          )

        )}


        {/* ------------------------------------------ */}
        {/* PAGINATION */}
        {/* ------------------------------------------ */}

        {!error && totalPages > 1 && (

          <div className="pagination">

            {/* PREVIOUS */}

            <button
              className="pagination-button"
              disabled={
                currentPage === 1
              }
              onClick={() =>
                goToPage(
                  currentPage - 1
                )
              }
            >
              ← Previous
            </button>


            {/* PAGE NUMBERS */}

            <div className="pagination-pages">

              {getPageNumbers().map(
                (page, index) => {

                  if (
                    page === "..."
                  ) {

                    return (

                      <span
                        key={`ellipsis-${index}`}
                        className="pagination-ellipsis"
                      >
                        ...
                      </span>

                    );

                  }


                  return (

                    <button
                      key={page}
                      className={
                        `pagination-page ${
                          currentPage === page
                            ? "active"
                            : ""
                        }`
                      }
                      onClick={() =>
                        goToPage(page)
                      }
                    >
                      {page}
                    </button>

                  );

                }
              )}

            </div>


            {/* NEXT */}

            <button
              className="pagination-button"
              disabled={
                currentPage ===
                totalPages
              }
              onClick={() =>
                goToPage(
                  currentPage + 1
                )
              }
            >
              Next →
            </button>

          </div>

        )}

      </main>

    </div>

  );

}


export default Jobs;