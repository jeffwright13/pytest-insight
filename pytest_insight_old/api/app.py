# filepath: /Users/jwr003/coding/pytest-insight/pytest_insight/api/app.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pytest_insight.api.routes import router

app = FastAPI(
    title="pytest-insight API", description="API for analyzing and comparing pytest test results", version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the router
app.include_router(router)


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}


# Root endpoint with API information
@app.get("/")
async def root():
    return {
        "name": "pytest-insight API",
        "version": "0.1.0",
        "documentation": "/docs",
        "endpoints": {
            "sessions": "/api/v1/sessions",
            "compare": "/api/v1/compare",
        },
    }
