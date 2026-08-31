"""
FastAPI application entrypoint.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.modules.clubs import router as clubs
from app.api.routes import admin, auth, faculty, student, placement
from app.ai.router import router as ai_router
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
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


# Existing routers
app.include_router(auth.router)
app.include_router(faculty.router)
app.include_router(student.router)
app.include_router(admin.router)
app.include_router(clubs)

# KEEP PLACEMENT
app.include_router(placement.router)

# ADD AI
app.include_router(ai_router)