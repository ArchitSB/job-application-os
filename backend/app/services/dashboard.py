from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Application, JobLead


def dashboard(session: Session) -> dict:
    # Reporting follows the owner's calendar in India, while storage stays timezone aware.
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week = today - timedelta(days=today.weekday())
    month = today.replace(day=1)

    def count(model, *conditions):
        return session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0

    def grouped(column):
        return dict(session.execute(select(column, func.count()).group_by(column)).all())

    return {
        "total_leads": count(JobLead),
        "new_leads": count(JobLead, JobLead.status == "discovered"),
        "shortlisted_leads": count(JobLead, JobLead.status == "shortlisted"),
        "total_applications": count(Application),
        "applications_this_week": count(
            Application, Application.date_applied >= week, Application.date_applied <= now
        ),
        "applications_this_month": count(
            Application, Application.date_applied >= month, Application.date_applied <= now
        ),
        "awaiting_responses": count(Application, Application.status == "awaiting_response"),
        "interviews": count(Application, Application.status == "interview"),
        "rejections": count(Application, Application.status == "rejected"),
        "offers": count(Application, Application.status == "offer"),
        "applications_by_resume_type": grouped(Application.resume_type),
        "applications_by_source": grouped(Application.source),
        "applications_by_method": grouped(Application.application_method),
        "recent_applications": session.scalars(
            select(Application).order_by(Application.created_at.desc(), Application.id).limit(8)
        ).all(),
    }
