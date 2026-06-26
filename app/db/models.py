from datetime import datetime
import json

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import DB_PATH, ensure_dirs


class Base(DeclarativeBase):
    pass


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(255), default="")
    seniority: Mapped[str] = mapped_column(String(100), default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    skills_json: Mapped[str] = mapped_column(Text, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    versions: Mapped[list["JDVersion"]] = relationship(back_populates="job_description")
    analyses: Mapped[list["AnalysisResult"]] = relationship(back_populates="job_description")

    @property
    def skills(self) -> list[str]:
        return json.loads(self.skills_json or "[]")

    @skills.setter
    def skills(self, value: list[str]) -> None:
        self.skills_json = json.dumps(value)


class JDVersion(Base):
    __tablename__ = "jd_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jd_id: Mapped[int] = mapped_column(ForeignKey("job_descriptions.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job_description: Mapped["JobDescription"] = relationship(back_populates="versions")


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="Unknown")
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    parse_method: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    structured_json: Mapped[str] = mapped_column(Text, default="")
    verification_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    analyses: Mapped[list["AnalysisResult"]] = relationship(back_populates="candidate")
    hr_questions: Mapped[list["HRQuestion"]] = relationship(back_populates="candidate")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    jd_id: Mapped[int] = mapped_column(ForeignKey("job_descriptions.id"), nullable=False)
    technical_score: Mapped[float] = mapped_column(Float, default=0.0)
    hr_score: Mapped[float] = mapped_column(Float, default=0.0)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    fit_summary: Mapped[str] = mapped_column(Text, default="")
    strengths_json: Mapped[str] = mapped_column(Text, default="[]")
    gaps_json: Mapped[str] = mapped_column(Text, default="[]")
    suspicion_score: Mapped[float] = mapped_column(Float, default=0.0)
    suspicion_flags_json: Mapped[str] = mapped_column(Text, default="[]")
    suspicion_reasoning: Mapped[str] = mapped_column(Text, default="")
    hr_verification_summary: Mapped[str] = mapped_column(Text, default="")
    recommended_role: Mapped[str] = mapped_column(String(255), default="")
    similarity_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    candidate: Mapped["Candidate"] = relationship(back_populates="analyses")
    job_description: Mapped["JobDescription"] = relationship(back_populates="analyses")
    hr_questions: Mapped[list["HRQuestion"]] = relationship(back_populates="analysis")

    @property
    def strengths(self) -> list[str]:
        return json.loads(self.strengths_json or "[]")

    @property
    def gaps(self) -> list[str]:
        return json.loads(self.gaps_json or "[]")

    @property
    def suspicion_flags(self) -> list[str]:
        return json.loads(self.suspicion_flags_json or "[]")


class HRQuestion(Base):
    __tablename__ = "hr_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analysis_results.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="general")
    source_flag: Mapped[str] = mapped_column(Text, default="")
    resume_excerpt: Mapped[str] = mapped_column(Text, default="")
    hr_answer: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    candidate: Mapped["Candidate"] = relationship(back_populates="hr_questions")
    analysis: Mapped["AnalysisResult"] = relationship(back_populates="hr_questions")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    current_step: Mapped[str] = mapped_column(String(100), default="")
    steps_json: Mapped[str] = mapped_column(Text, default="[]")
    result_json: Mapped[str] = mapped_column(Text, default="")
    viz_json: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    candidate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    groq_api_key: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


ensure_dirs()
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 30},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _connection_record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def init_db() -> None:
    ensure_dirs()
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations() -> None:
    migrations = [
        "ALTER TABLE candidates ADD COLUMN parse_method VARCHAR(100) DEFAULT ''",
        "ALTER TABLE hr_questions ADD COLUMN hr_answer TEXT DEFAULT ''",
        "ALTER TABLE hr_questions ADD COLUMN answered_at DATETIME",
        "ALTER TABLE analysis_results ADD COLUMN suspicion_reasoning TEXT DEFAULT ''",
        "ALTER TABLE analysis_results ADD COLUMN hr_verification_summary TEXT DEFAULT ''",
        "ALTER TABLE processing_jobs ADD COLUMN viz_json TEXT DEFAULT ''",
        "ALTER TABLE candidates ADD COLUMN structured_json TEXT DEFAULT ''",
        "ALTER TABLE candidates ADD COLUMN verification_json TEXT DEFAULT ''",
        "ALTER TABLE hr_questions ADD COLUMN category VARCHAR(50) DEFAULT 'general'",
        "ALTER TABLE hr_questions ADD COLUMN source_flag TEXT DEFAULT ''",
        "ALTER TABLE hr_questions ADD COLUMN resume_excerpt TEXT DEFAULT ''",
    ]
    with engine.begin() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
            except Exception:
                pass


def get_session():
    return SessionLocal()


def commit_with_retry(session, retries: int = 6) -> None:
    import time

    from sqlalchemy.exc import OperationalError

    for attempt in range(retries):
        try:
            session.commit()
            return
        except OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt >= retries - 1:
                raise
            session.rollback()
            time.sleep(0.05 * (2**attempt))
