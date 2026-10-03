"""Real PostgreSQL API tests, with every mutation contained in an outer rollback."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_engine, get_session
from app.main import create_app
from app.models import Application, ApplicationEvent
from app.services.seed import seed

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1"),
]


@pytest.fixture
def client():
    with get_engine().connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
        seed(session)
        app = create_app()
        app.dependency_overrides[get_session] = lambda: session
        with TestClient(app) as client:
            client.db = session
            yield client
        session.close()
        transaction.rollback()


def company(client, name=None):
    response = client.post("/companies", json={"name": name or f"Example {uuid4().hex}"})
    assert response.status_code == 201, response.text
    return response.json()


def application(client, company_id, **values):
    payload = {
        "company_id": company_id,
        "role_title": "Backend Engineer",
        "application_method": "email",
        "resume_type": "technical",
        **values,
    }
    response = client.post("/applications", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_company_normalization_and_no_forced_merge(client):
    first = company(client, "OpenAI Inc.")
    second = company(client, "openai")
    assert first["normalized_name"] == second["normalized_name"] == "openai"
    assert first["id"] != second["id"]
    assert client.get(f"/companies/{first['id']}").status_code == 200
    assert client.get("/companies?search=openai").json()["total"] >= 2


def test_lead_application_conversion_and_audit(client):
    c = company(client)
    lead = client.post(
        "/leads",
        json={
            "company_id": c["id"],
            "role_title": "AI Engineer",
            "source": "telegram",
            "description": "Build systems",
            "job_url": "https://jobs.example.com/ai-123",
        },
    ).json()
    assert lead["recommended_resume_type"] is None
    assert (
        client.patch(
            f"/leads/{lead['id']}",
            json={"status": "shortlisted", "recommended_resume_type": "technical", "fit_score": 82},
        ).status_code
        == 200
    )
    app = application(client, c["id"], role_title="AI Engineer", job_lead_id=lead["id"])
    assert app["source"] == "telegram"
    assert app["job_url"] == lead["job_url"]
    assert client.get(f"/leads/{lead['id']}").json()["status"] == "converted"
    assert client.get(f"/applications/{app['id']}").status_code == 200
    events = client.get(f"/applications/{app['id']}/events").json()["items"]
    assert {e["event_type"] for e in events} == {"application_created", "lead_converted"}
    assert client.get(f"/leads/{lead['id']}/events").json()["total"] == 4
    duplicate = client.post(
        "/applications",
        json={
            "company_id": c["id"],
            "job_lead_id": lead["id"],
            "role_title": "AI Engineer",
            "resume_type": "technical",
            "application_method": "portal",
        },
    )
    assert duplicate.status_code == 409


@pytest.mark.parametrize(
    "existing,candidate,duplicate",
    [
        (
            {"job_url": "https://jobs.example.com/123?utm_source=linkedin"},
            {"job_url": "https://jobs.example.com/123"},
            True,
        ),
        ({}, {"role_title": "backend   engineer"}, True),
        ({}, {"role_title": "Senior Backend Engineer"}, False),
        ({"job_url": "https://jobs.example.com/123"}, {"job_url": "https://jobs.example.com/456"}, False),
        (
            {"contact_email": "hr@example.com"},
            {"contact_email": "hr@example.com", "role_title": "Product Manager"},
            False,
        ),
        (
            {"external_job_id": "abc", "source": "linkedin"},
            {"external_job_id": "abc", "source": "linkedin"},
            True,
        ),
        ({"external_job_id": "abc"}, {"external_job_id": "def"}, False),
    ],
)
def test_duplicate_cases(client, existing, candidate, duplicate):
    c = company(client)
    app = application(client, c["id"], **existing)
    response = client.post(
        "/applications/check-duplicate",
        json={"company_id": c["id"], "role_title": "Backend Engineer", **candidate},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["is_duplicate"] is duplicate
    assert result["reason"]
    if duplicate:
        assert result["matched_application_id"] == app["id"]
    response = client.post(
        "/applications",
        json={
            "company_id": c["id"],
            "role_title": "Backend Engineer",
            "resume_type": "technical",
            "application_method": "portal",
            **candidate,
        },
    )
    assert response.status_code == (409 if duplicate else 201), response.text


def test_ambiguous_duplicate_user_override_and_strong_block(client):
    c = company(client)
    application(client, c["id"])
    second = application(
        client, c["id"], duplicate_override_reason="Separate confirmed opening in another team"
    )
    assert client.get(f"/applications/{second['id']}/events").json()["items"][0]["metadata"][
        "duplicate_override_reason"
    ]
    third = application(
        client, c["id"], role_title="Product Manager", job_url="https://jobs.example.com/strong"
    )
    response = client.post(
        "/applications",
        json={
            "company_id": c["id"],
            "role_title": "Product Manager",
            "job_url": third["job_url"],
            "resume_type": "product",
            "application_method": "email",
            "duplicate_override_reason": "Trying to override a definite duplicate",
        },
    )
    assert response.status_code == 409


def test_update_rechecks_duplicate_and_writes_audit(client):
    c = company(client)
    a = application(client, c["id"], job_url="https://jobs.example.com/1")
    b = application(client, c["id"], job_url="https://jobs.example.com/2")
    assert client.patch(f"/applications/{b['id']}", json={"job_url": a["job_url"]}).status_code == 409
    response = client.patch(
        f"/applications/{b['id']}", json={"status": "applied", "notes": "Applied personally"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["applied_at"] is not None
    assert client.get(f"/applications/{b['id']}/events").json()["total"] == 2


def test_resume_contact_event_and_dashboard(client):
    profiles = client.get("/resumes").json()
    assert {p["profile_type"] for p in profiles} == {"technical", "product"}
    c = company(client)
    assert (
        client.post(
            "/contacts", json={"company_id": c["id"], "name": "Hiring Manager", "email": "hiring@example.com"}
        ).status_code
        == 201
    )
    app = application(
        client, c["id"], status="awaiting_response", source="referral", application_method="referral"
    )
    response = client.post(
        f"/applications/{app['id']}/events",
        json={"event_type": "recruiter_replied", "metadata": {"note": "Requested interview slots"}},
        headers={"X-Actor": "hermes"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["actor"] == "hermes"
    assert response.json()["metadata"]["note"]
    summary = client.get("/dashboard/summary")
    assert summary.status_code == 200, summary.text
    assert summary.json()["awaiting_responses"] >= 1
    assert summary.json()["applications_this_week"] >= 1
    assert summary.json()["applications_by_method"]["referral"] >= 1
    assert client.get("/contacts?search=hiring").json()["total"] >= 1


def test_email_draft_review_approval_and_manual_sent_record(client):
    app = application(client, company(client)["id"])
    payload = {
        "application_id": app["id"],
        "recipient_email": "hr@example.com",
        "subject": "Application for Backend Engineer | Archit Singh Baghel",
        "body": "Hi, I am Archit. I would like to discuss this role.",
        "resume_type": "technical",
    }
    response = client.post("/email-drafts", json=payload)
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft["status"] == "draft" and draft["sent_at"] is None
    path = f"/email-drafts/{draft['id']}"
    assert client.patch(path, json={"status": "sent"}).status_code == 409
    assert client.patch(path, json={"status": "reviewed"}).status_code == 200
    assert client.patch(path, json={"status": "approved"}, headers={"X-Actor": "hermes"}).status_code == 409
    assert client.patch(path, json={"status": "approved"}).json()["approved_at"]
    edited = client.patch(path, json={"body": "A revised, specific application."})
    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "draft" and edited.json()["approved_at"] is None
    assert client.patch(path, json={"status": "reviewed"}).status_code == 200
    assert client.patch(path, json={"status": "approved"}).status_code == 200
    sent = client.patch(path, json={"status": "sent"})
    assert sent.status_code == 200, sent.text
    assert sent.json()["sent_at"]
    assert client.get(f"/applications/{app['id']}").json()["status"] == "applied"
    assert client.patch(path, json={"body": "Alter history"}).status_code == 409


def test_filtering_pagination_and_null_validation(client):
    c = company(client)
    for index in range(3):
        application(client, c["id"], role_title=f"Engineer {index}", source="unstop", resume_type="product")
    path = f"/applications?search={c['name']}&source=unstop&resume_type=product&page_size=2"
    page = client.get(path).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert len(client.get(path + "&page=2").json()["items"]) == 1
    assert client.get(path + "&date_from=2099-01-01T00:00:00Z").json()["total"] == 0
    assert client.get("/applications?page_size=1000").status_code == 422
    assert (
        client.patch(f"/applications/{page['items'][0]['id']}", json={"role_title": None}).status_code == 422
    )
    assert client.get(f"/applications/{uuid4()}").status_code == 404
    assert client.post("/companies", json={"name": "Test", "password": "not-allowed"}).status_code == 422


def test_rules_profile_and_automation_records(client):
    assert client.get("/profile").json()["full_name"] == "Archit Singh Baghel"
    assert client.patch("/rules", json={"excluded_companies": ["Blocked Inc."]}).status_code == 200
    c = company(client, "Blocked")
    response = client.post(
        "/applications",
        json={
            "company_id": c["id"],
            "role_title": "Engineer",
            "resume_type": "technical",
            "application_method": "portal",
        },
    )
    assert response.status_code == 409
    run = client.post("/automation-runs", json={"run_type": "classification", "agent": "job_matcher"}).json()
    assert run["status"] == "pending"
    assert client.patch(f"/automation-runs/{run['id']}", json={"status": "running"}).json()["started_at"]
    assert client.patch(
        f"/automation-runs/{run['id']}", json={"status": "completed", "output_metadata": {"reviewed": 1}}
    ).json()["completed_at"]
    assert client.patch("/profile", json={"email": "not an email"}).status_code == 422


def test_atomic_no_application_on_failed_validation(client):
    before = client.db.scalar(select(func.count()).select_from(Application))
    events = client.db.scalar(select(func.count()).select_from(ApplicationEvent))
    response = client.post(
        "/applications",
        json={
            "company_id": str(uuid4()),
            "role_title": "Engineer",
            "resume_type": "technical",
            "application_method": "portal",
        },
    )
    assert response.status_code == 404
    assert client.db.scalar(select(func.count()).select_from(Application)) == before
    assert client.db.scalar(select(func.count()).select_from(ApplicationEvent)) == events


def test_human_approval_rule_and_draft_resume_consistency(client):
    c = company(client)
    payload = {
        "company_id": c["id"],
        "role_title": "Engineer",
        "resume_type": "technical",
        "application_method": "email",
        "status": "prepared",
    }
    assert client.post("/applications", json=payload, headers={"X-Actor": "hermes"}).status_code == 409
    assert client.patch("/rules", json={"user_approval_required": False}).status_code == 200
    response = client.post("/applications", json=payload, headers={"X-Actor": "hermes"})
    assert response.status_code == 201, response.text
    app = response.json()
    assert (
        client.post(
            "/email-drafts",
            json={
                "application_id": app["id"],
                "recipient_email": "hr@example.com",
                "subject": "Hello",
                "body": "Draft text",
                "resume_type": "technical",
            },
        ).status_code
        == 201
    )
    assert client.patch(f"/applications/{app['id']}", json={"resume_type": "product"}).status_code == 409


def test_reviewed_duplicate_can_be_updated_without_repeated_override(client):
    c = company(client)
    application(client, c["id"])
    second = application(
        client, c["id"], duplicate_override_reason="This is a confirmed opening in another team"
    )
    assert (
        client.patch(f"/applications/{second['id']}", json={"notes": "Follow up next week"}).status_code
        == 200
    )


def test_resume_path_confinement(client):
    resume = client.get("/resumes").json()[0]
    path = f"/resumes/{resume['id']}"
    assert client.patch(path, json={"local_path": "../outside.pdf"}).status_code == 422
    assert client.patch(path, json={"local_path": "/etc/passwd"}).status_code == 422
    assert client.patch(path, json={"local_path": "resumes/missing.pdf"}).status_code == 422
    assert client.patch(path, json={"description": "Reviewed profile description"}).status_code == 200


def test_audit_events_are_immutable_in_database(client):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    app = application(client, company(client)["id"])
    with pytest.raises(DBAPIError):
        with client.db.begin_nested():
            client.db.execute(
                text("UPDATE application_events SET actor = :actor WHERE application_id = :id"),
                {"actor": "changed", "id": app["id"]},
            )
    assert client.get(f"/applications/{app['id']}/events").json()["items"][0]["actor"] == "user"


def test_distinct_lead_company_rejected_and_age_rule(client):
    a, b = company(client), company(client)
    lead = client.post(
        "/leads", json={"company_id": a["id"], "role_title": "Engineer", "posted_at": "2020-01-01T00:00:00Z"}
    ).json()
    payload = {
        "company_id": b["id"],
        "job_lead_id": lead["id"],
        "role_title": "Engineer",
        "resume_type": "technical",
        "application_method": "portal",
    }
    assert client.post("/applications", json=payload).status_code == 422
    payload["company_id"] = a["id"]
    assert client.post("/applications", json=payload).status_code == 409
