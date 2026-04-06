"""Pydantic models for request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional, List


# ──────────────────────────────────────────────
# Request schemas
# ──────────────────────────────────────────────

class InterpretRequest(BaseModel):
    """Input for the /interpret and /search endpoints."""
    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="User's complaint or query in natural language.",
        examples=["There is no electricity in my area since morning"],
    )
    district: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional district name for localized results.",
        examples=["Lucknow"],
    )


class ResolveRequest(BaseModel):
    """Input for the /resolve endpoint."""
    category: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Complaint category (e.g., Electricity, Police, Land, Transport, Water).",
        examples=["Electricity"],
    )
    problem: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Specific problem within the category.",
        examples=["Power Outage"],
    )


# ──────────────────────────────────────────────
# Response schemas
# ──────────────────────────────────────────────

class InterpretResponse(BaseModel):
    """Output from the /interpret endpoint."""
    category: str
    problem: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: str = Field(
        default="llm",
        description="Whether the result came from 'keyword' matching or 'llm'.",
    )
    disclaimer: str = Field(
        default="This is an AI-assisted classification. Please verify with the relevant department.",
    )


class PrimaryAction(BaseModel):
    department: str
    complaint_link: str
    helpline: str
    description: str


class Escalation(BaseModel):
    authority: str
    contact: str
    timeline: str


class RTI(BaseModel):
    department: str
    how_to_file: str
    sample_query: str


class ResolveResponse(BaseModel):
    """Output from the /resolve endpoint."""
    category: str
    problem: str
    primary_action: PrimaryAction
    escalation: Escalation
    rti: RTI
    disclaimer: str = Field(
        default="This information is for guidance purposes only. Contact details and procedures may change. Always verify with the official department website.",
    )


class SearchResponse(BaseModel):
    """Combined output from /search — interpret + resolve in one call."""
    category: str
    problem: str
    district: str = Field(default="General", description="District the result applies to.")
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: str
    matched_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords from the database that matched the user query.",
    )
    primary_action: PrimaryAction
    escalation: Escalation
    rti: RTI
    disclaimer: str = Field(
        default="This information is for guidance purposes only. This is not an official government website. Contact details and procedures may change. Always verify with the official department website.",
    )


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    suggestion: Optional[str] = None
