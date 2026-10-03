"""Shared API value types, independent of persistence."""

from enum import StrEnum


class ApplicationMethod(StrEnum):
    EMAIL = "email"
    PORTAL = "portal"
    PLATFORM = "platform"
    REFERRAL = "referral"
    OTHER = "other"


class ResumeType(StrEnum):
    TECHNICAL = "technical"
    PRODUCT = "product"


class ApplicationStatus(StrEnum):
    DISCOVERED = "discovered"
    SHORTLISTED = "shortlisted"
    APPROVED = "approved"
    PREPARED = "prepared"
    APPLIED = "applied"
    AWAITING_RESPONSE = "awaiting_response"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    OFFER = "offer"
    SKIPPED = "skipped"
