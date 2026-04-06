"""
Government Complaint Navigation Platform — FastAPI Backend

A production-ready API that helps Indian citizens navigate government
complaint procedures using AI-powered intent classification and a
comprehensive local knowledge base.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from models.schemas import (
    InterpretRequest,
    InterpretResponse,
    ResolveRequest,
    ResolveResponse,
    SearchResponse,
    ErrorResponse,
)
from services.cache import cache
from services.matcher import (
    keyword_match,
    match_complaint,
    load_complaints_data,
    get_available_categories,
    get_available_districts,
)
from services.llm_service import classify_intent
from utils.helpers import sanitize_input, normalize_category, normalize_problem

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# App Lifecycle
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load complaint data at startup."""
    logger.info("Starting Government Complaint Navigator...")
    try:
        data = load_complaints_data()
        logger.info("Loaded %d complaint entries", len(data))
    except FileNotFoundError as e:
        logger.critical("Failed to load complaint data: %s", e)
        raise
    yield
    logger.info("Shutting down...")


# ──────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────

app = FastAPI(
    title="Government Complaint Navigation Platform",
    description=(
        "AI-powered API to help Indian citizens identify the correct government "
        "department, complaint procedure, escalation path, and RTI filing process "
        "for their grievances."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow all origins for public API access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "status": "active",
        "service": "Government Complaint Navigation Platform",
        "version": "1.0.0",
        "endpoints": {
            "interpret": "POST /interpret — Classify user complaint",
            "resolve": "POST /resolve — Get complaint resolution steps",
            "categories": "GET /categories — List available categories",
            "docs": "GET /docs — API documentation",
        },
    }


@app.get("/health", tags=["Health"])
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "cache_stats": cache.stats,
        "api_key_configured": bool(os.getenv("OPENROUTER_API_KEY")),
    }


# ──────────────────────────────────────────────
# GET /categories
# ──────────────────────────────────────────────

@app.get("/categories", tags=["Reference"])
async def list_categories():
    """List all available complaint categories and problems."""
    return {
        "categories": get_available_categories(),
        "disclaimer": "These are the currently supported categories. More will be added.",
    }


@app.get("/districts", tags=["Reference"])
async def list_districts():
    """List all districts that have district-specific data."""
    return {
        "districts": get_available_districts(),
        "note": "Select a district for localized contact details. If not selected, general information will be shown.",
    }


# ──────────────────────────────────────────────
# POST /interpret
# ──────────────────────────────────────────────

@app.post(
    "/interpret",
    response_model=InterpretResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["Core"],
    summary="Classify a user complaint",
    description=(
        "Accepts a natural language complaint query and returns a structured "
        "classification with category, problem, and confidence score. "
        "Uses keyword matching first, then falls back to LLM."
    ),
)
async def interpret(request: InterpretRequest):
    """
    Interpret user complaint and classify it.
    Pipeline: Input Validation → Cache Check → Keyword Match → LLM → Response
    """
    raw_query = request.query
    query = sanitize_input(raw_query)

    if len(query) < 3:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid input",
                "message": "Query is too short after sanitization.",
                "suggestion": "Please provide a more descriptive complaint.",
            },
        )

    logger.info("Processing query: %s", query[:100])

    # ── Step 1: Check cache ──
    cached = cache.get(query)
    if cached:
        logger.info("Returning cached result")
        cached["source"] = "cache"
        return InterpretResponse(**cached)

    # ── Step 2: Keyword matching (fast, deterministic) ──
    kw_result = keyword_match(query)
    if kw_result:
        result = {
            "category": kw_result["category"],
            "problem": kw_result["problem"],
            "confidence": kw_result["confidence"],
            "source": "keyword",
        }
        cache.set(query, result)
        return InterpretResponse(**result)

    # ── Step 3: LLM classification (fallback) ──
    llm_result = await classify_intent(query)
    if llm_result and llm_result.get("category", "Unknown") != "Unknown":
        result = {
            "category": llm_result["category"],
            "problem": llm_result["problem"],
            "confidence": llm_result["confidence"],
            "source": "llm",
        }
        cache.set(query, result)
        return InterpretResponse(**result)

    # ── Step 4: Nothing worked ──
    logger.warning("No classification found for query: %s", query[:80])
    raise HTTPException(
        status_code=404,
        detail={
            "error": "No result found",
            "message": (
                "Could not classify your complaint. Try rephrasing or "
                "specify the category directly using /resolve."
            ),
            "suggestion": "Use /categories to see available complaint types.",
        },
    )


# ──────────────────────────────────────────────
# POST /resolve
# ──────────────────────────────────────────────

@app.post(
    "/resolve",
    response_model=ResolveResponse,
    responses={404: {"model": ErrorResponse}},
    tags=["Core"],
    summary="Get complaint resolution steps",
    description=(
        "Given a category and problem, returns detailed resolution steps "
        "including department contact, complaint links, escalation path, "
        "and RTI filing guidance."
    ),
)
async def resolve(request: ResolveRequest):
    """
    Resolve a complaint by matching category and problem to the knowledge base.
    """
    category = normalize_category(request.category)
    problem = normalize_problem(request.problem)

    logger.info("Resolving: %s / %s", category, problem)

    result = match_complaint(category, problem)

    if not result:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "No result found",
                "message": f"No resolution found for category '{category}' and problem '{problem}'.",
                "suggestion": "Use /categories to see available complaint types.",
            },
        )

    return ResolveResponse(**result)


# ──────────────────────────────────────────────
# POST /search (combined interpret + resolve)
# ──────────────────────────────────────────────

@app.post(
    "/search",
    response_model=SearchResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    tags=["Core"],
    summary="Search for complaint solution (combined)",
    description=(
        "One-step endpoint: classifies the query AND returns full resolution "
        "data in a single call. Used by the frontend."
    ),
)
async def search(request: InterpretRequest):
    """
    Combined search: interpret the query then resolve it in one call.
    """
    raw_query = request.query
    query = sanitize_input(raw_query)
    district = request.district.strip() if request.district else None

    if len(query) < 3:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid input",
                "message": "Query is too short. Please describe your problem in more detail.",
            },
        )

    logger.info("[/search] Processing: %s (district=%s)", query[:100], district or "none")

    # ── Step 1: Check cache (full result) ──
    cache_key = f"search:{query}:{district or 'general'}"
    cached = cache.get(cache_key)
    if cached:
        logger.info("[/search] Cache hit")
        return SearchResponse(**cached)

    # ── Step 2: Classify (keyword → LLM) ──
    classification = keyword_match(query)
    source = "keyword"

    if not classification:
        llm_result = await classify_intent(query)
        if llm_result and llm_result.get("category", "Unknown") != "Unknown":
            classification = llm_result
            source = "llm"

    if not classification:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "No result found",
                "message": "Could not understand your complaint. Please try rephrasing with more details.",
                "suggestion": "Example: 'There is no electricity in my area' or 'Police is not filing my FIR'",
            },
        )

    # ── Step 3: Resolve from JSON ──
    resolution = match_complaint(classification["category"], classification["problem"], district)

    if not resolution:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "No resolution found",
                "message": f"Identified as {classification['category']} / {classification['problem']}, but no detailed resolution is available yet.",
                "suggestion": "Try using /resolve with a different problem name, or check /categories for available options.",
            },
        )

    # ── Step 4: Combine and cache ──
    result = {
        "category": classification["category"],
        "problem": classification["problem"],
        "district": resolution.get("district", "General"),
        "confidence": classification["confidence"],
        "source": source,
        "matched_keywords": classification.get("matched_keywords", []),
        "primary_action": resolution["primary_action"],
        "escalation": resolution["escalation"],
        "rti": resolution["rti"],
    }
    cache.set(cache_key, result)

    return SearchResponse(**result)


# ──────────────────────────────────────────────
# POST /feedback
# ──────────────────────────────────────────────

@app.post("/feedback", tags=["Feedback"], summary="Submit user feedback")
async def submit_feedback(feedback: dict):
    """
    Accept user feedback on search results.
    Logs feedback for future improvement. No database — simple logging.
    """
    query = feedback.get("query", "unknown")
    category = feedback.get("category", "unknown")
    helpful = feedback.get("helpful", None)

    logger.info(
        "[FEEDBACK] query=%s | category=%s | helpful=%s",
        query[:100],
        category,
        helpful,
    )

    return {
        "status": "received",
        "message": "Thank you for your feedback!",
    }


# ──────────────────────────────────────────────
# Global Exception Handler
# ──────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


# ──────────────────────────────────────────────
# Serve Frontend (must be LAST — catch-all)
# ──────────────────────────────────────────────

frontend_dir = Path(__file__).parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    logger.info("Serving frontend from %s", frontend_dir)
