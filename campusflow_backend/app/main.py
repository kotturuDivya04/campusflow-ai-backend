"""
FastAPI application entrypoint.

  * mounts the four routers (auth, faculty, student, admin)
  * translates every CampusFlowError into its documented HTTP status
  * exposes /health and auto-generated OpenAPI docs at /docs
"""
from __future__ import annotations
from app.modules.clubs import router as clubs
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin, auth, faculty, student, placement
from app.core.config import settings
from app.core.errors import CampusFlowError

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "CampusFlow AI — student/faculty appointment scheduling with a live "
        "token queue, built directly on the finalized PostgreSQL schema."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(CampusFlowError)
async def campusflow_error_handler(_: Request, exc: CampusFlowError):
    return JSONResponse(
        status_code=exc.http_status,
        content={"error": exc.code, "detail": exc.message},
    )


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


app.include_router(auth.router)
app.include_router(faculty.router)
app.include_router(student.router)
app.include_router(admin.router)
app.include_router(clubs)
app.include_router(placement.router)