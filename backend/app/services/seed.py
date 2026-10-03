"""Idempotent initial personal data; never overwrite the user's later edits."""

from datetime import date

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models import ApplicationRules, ResumeProfile, UserProfile
from app.schemas.domain import Rules

RESUMES = [
    {
        "profile_type": "technical",
        "name": "Technical Resume",
        "description": "Engineering, backend/full-stack, AI/LLM and RAG systems; Redseer SDE internship, IIT Kharagpur backend work, freelance engineering and end-to-end ownership. Select using the full job description, not keywords alone.",
        "drive_url": "https://drive.google.com/file/d/1FGcXBaAuuKD0zs4DBfKnBOxScwIPO2E0/view?usp=sharing",
    },
    {
        "profile_type": "product",
        "name": "Product Resume",
        "description": "Product discovery, stakeholders, requirements and shipped outcomes; Redseer product ownership, IIT KGP field research and freelance client/product ownership. Select using responsibilities and context.",
        "drive_url": "https://drive.google.com/file/d/1mIbtbr-Im76j0Mj38FMFFxPScDzr3UvN/view?usp=sharing",
    },
]


def seed(session: Session) -> None:
    for resume in RESUMES:
        session.execute(
            insert(ResumeProfile).values(**resume).on_conflict_do_nothing(index_elements=["profile_type"])
        )
    session.execute(
        insert(ApplicationRules).values(id=1, settings=Rules().model_dump()).on_conflict_do_nothing()
    )
    session.execute(
        insert(UserProfile)
        .values(
            id=1,
            full_name="Archit Singh Baghel",
            email="arsiba999@gmail.com",
            phone="+91-9343284959",
            date_of_birth=date(2003, 8, 25),
            gender="Male",
            location="Bengaluru, India",
            current_company="Redseer Strategy Consultants",
            current_role="Software Development Engineer Intern",
            current_stipend=25000,
            stipend_currency="INR",
            notice_period=12,
            portfolio_url="https://arc-web-olive-ten.vercel.app",
            github_url="https://github.com/ArchitSB",
            linkedin_url="https://linkedin.com/in/archit-singh-baghel-54b841263",
        )
        .on_conflict_do_nothing()
    )
    session.commit()


if __name__ == "__main__":
    with Session(get_engine()) as session:
        seed(session)
    print("Resume profiles, user profile and application rules seeded (existing values preserved).")
