from sqlalchemy.orm import Session

from app.db.models import AnalysisResult, HRQuestion, JDVersion, JobDescription
from app.services.jd_format import normalize_jd_content
from app.services.vector_store import vector_store


def list_active_jds(session: Session) -> list[JobDescription]:
    return (
        session.query(JobDescription)
        .filter(JobDescription.is_active.is_(True))
        .order_by(JobDescription.updated_at.desc())
        .all()
    )


def list_all_jds(session: Session) -> list[JobDescription]:
    return session.query(JobDescription).order_by(JobDescription.updated_at.desc()).all()


def get_jd(session: Session, jd_id: int) -> JobDescription | None:
    return session.query(JobDescription).filter(JobDescription.id == jd_id).first()


def create_jd(
    session: Session,
    title: str,
    role: str,
    department: str,
    seniority: str,
    content: str,
    skills: list[str],
) -> JobDescription:
    content = normalize_jd_content(content)
    jd = JobDescription(
        title=title,
        role=role,
        department=department,
        seniority=seniority,
        content=content,
        skills_json="[]",
    )
    jd.skills = skills
    session.add(jd)
    session.flush()

    version = JDVersion(jd_id=jd.id, version=1, content_snapshot=content)
    session.add(version)
    session.commit()
    session.refresh(jd)

    vector_store.index_jd(jd.id, jd.title, jd.role, jd.content, jd.skills)
    return jd


def update_jd(
    session: Session,
    jd_id: int,
    title: str,
    role: str,
    department: str,
    seniority: str,
    content: str,
    skills: list[str],
) -> JobDescription:
    jd = get_jd(session, jd_id)
    if not jd:
        raise ValueError(f"JD {jd_id} not found")

    jd.title = title
    jd.role = role
    jd.department = department
    jd.seniority = seniority
    jd.content = normalize_jd_content(content)
    jd.skills = skills

    latest_version = (
        session.query(JDVersion)
        .filter(JDVersion.jd_id == jd_id)
        .order_by(JDVersion.version.desc())
        .first()
    )
    next_version = (latest_version.version + 1) if latest_version else 1
    session.add(JDVersion(jd_id=jd_id, version=next_version, content_snapshot=content))
    session.commit()
    session.refresh(jd)

    vector_store.index_jd(jd.id, jd.title, jd.role, jd.content, jd.skills)
    return jd


def restore_jd(session: Session, jd_id: int) -> JobDescription:
    jd = get_jd(session, jd_id)
    if not jd:
        raise ValueError(f"JD {jd_id} not found")
    jd.is_active = True
    session.commit()
    session.refresh(jd)
    vector_store.index_jd(jd.id, jd.title, jd.role, jd.content, jd.skills)
    return jd


def archive_jd(session: Session, jd_id: int) -> None:
    jd = get_jd(session, jd_id)
    if not jd:
        raise ValueError(f"JD {jd_id} not found")
    jd.is_active = False
    session.commit()
    vector_store.delete_jd(jd_id)


def delete_jd(session: Session, jd_id: int) -> None:
    jd = get_jd(session, jd_id)
    if not jd:
        raise ValueError(f"JD {jd_id} not found")

    analysis_ids = [
        row[0]
        for row in session.query(AnalysisResult.id).filter(AnalysisResult.jd_id == jd_id).all()
    ]
    if analysis_ids:
        session.query(HRQuestion).filter(HRQuestion.analysis_id.in_(analysis_ids)).delete(
            synchronize_session=False
        )
        session.query(AnalysisResult).filter(AnalysisResult.jd_id == jd_id).delete(
            synchronize_session=False
        )

    session.query(JDVersion).filter(JDVersion.jd_id == jd_id).delete(synchronize_session=False)
    session.delete(jd)
    session.commit()
    vector_store.delete_jd(jd_id)


def reindex_all_jds(session: Session) -> int:
    jds = list_active_jds(session)
    for jd in jds:
        vector_store.index_jd(jd.id, jd.title, jd.role, jd.content, jd.skills)
    return len(jds)
