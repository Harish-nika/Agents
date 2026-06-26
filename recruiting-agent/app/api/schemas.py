from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    username: str


class JDCreate(BaseModel):
    title: str
    role: str
    department: str = ""
    seniority: str = "Mid"
    content: str
    skills: list[str] = Field(default_factory=list)


class JDUpdate(JDCreate):
    pass


class JDPublic(BaseModel):
    id: int
    title: str
    role: str
    department: str
    seniority: str
    content: str
    skills: list[str]
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class JDParseRequest(BaseModel):
    raw_text: str


class JDParsed(BaseModel):
    role: str = ""
    title: str = ""
    department: str = ""
    seniority: str = "Mid"
    skills: list[str] = Field(default_factory=list)
    must_haves: list[str] = Field(default_factory=list)
    nice_to_haves: list[str] = Field(default_factory=list)
    content: str = ""


class DashboardStats(BaseModel):
    active_jds: int
    candidates: int
    analyzed: int
    failed: int
    avg_score: float
    pending_questions: int
    ollama_ok: bool
    ollama_cpu: bool = False
    ollama_gpu: bool = False
    groq_ok: bool = False
    using_groq: bool = False


class AnalysisPublic(BaseModel):
    id: int
    candidate_id: int
    jd_id: int
    jd_title: str = ""
    jd_role: str = ""
    technical_score: float
    hr_score: float
    overall_score: float
    fit_summary: str
    strengths: list[str]
    gaps: list[str]
    suspicion_score: float
    suspicion_flags: list[str]
    suspicion_reasoning: str = ""
    hr_verification_summary: str = ""
    recommended_role: str
    similarity_score: float
    created_at: datetime | None = None


class CandidatePublic(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    status: str
    parse_method: str = ""
    created_at: datetime | None = None
    analyses: list[AnalysisPublic] = Field(default_factory=list)
    pending_hr_questions: int = 0
    verification_summary: str = ""
    verification_category_counts: dict[str, int] = Field(default_factory=dict)
    verification_completeness: float | None = None


class HRQuestionPublic(BaseModel):
    id: int
    candidate_id: int
    candidate_name: str = ""
    analysis_id: int
    question: str
    category: str = "general"
    source_flag: str = ""
    resume_excerpt: str = ""
    hr_answer: str = ""
    status: str
    suspicion_score: float = 0.0
    suspicion_flags: list[str] = Field(default_factory=list)
    suspicion_reasoning: str = ""
    jd_title: str = ""
    created_at: datetime | None = None
    answered_at: datetime | None = None


class HRQuestionUpdate(BaseModel):
    status: str | None = None
    hr_answer: str | None = None


class HRCandidateGroup(BaseModel):
    candidate_id: int
    candidate_name: str
    suspicion_score: float = 0.0
    suspicion_flags: list[str] = Field(default_factory=list)
    suspicion_reasoning: str = ""
    jd_title: str = ""
    verification_summary: str = ""
    verification_category_counts: dict[str, int] = Field(default_factory=dict)
    questions: list[HRQuestionPublic] = Field(default_factory=list)


class GroqSettingsPublic(BaseModel):
    has_saved_key: bool
    key_mask: str = ""
    updated_at: str | None = None


class GroqKeySave(BaseModel):
    api_key: str


class JobStepPublic(BaseModel):
    id: str
    label: str
    status: str


class ProcessingJobPublic(BaseModel):
    id: int
    job_type: str
    label: str
    status: str
    current_step: str
    steps: list[JobStepPublic]
    result: dict | None = None
    viz: dict | None = None
    error: str = ""
    candidate_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class JobCreated(BaseModel):
    job_id: int
