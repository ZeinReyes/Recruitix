from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import jobs, analytics

app = FastAPI(
    title="Recruitix API",
    description="Philippine Job Market Analytics API",
    version="1.0.0",
)


# ------------------------------------------------------------------
# CORS
# ------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,

    # Development
    allow_origins=["*"],

    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# ROUTERS
# ------------------------------------------------------------------

app.include_router(jobs.router)
app.include_router(analytics.router)


# ------------------------------------------------------------------
# ROOT
# ------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "name": "Recruitix API",
        "version": "1.0.0",
        "status": "running",
    }


# ------------------------------------------------------------------
# HEALTH CHECK
# ------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }