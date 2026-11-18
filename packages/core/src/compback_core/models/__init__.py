"""ORM models. Importing this package registers every table on ``Base.metadata``."""

from compback_core.models.base import Base
from compback_core.models.documents import Document, DocumentPage, Extraction, ExtractionEdit
from compback_core.models.platform import Job, JurisdictionPolicy
from compback_core.models.tenancy import (
    AccessGrant,
    AdvisorClientLink,
    AuditLog,
    Consent,
    EmailOutbox,
    EmailToken,
    Membership,
    Organization,
    RateLimitCounter,
    Session,
    User,
)

__all__ = [
    "AccessGrant",
    "AdvisorClientLink",
    "AuditLog",
    "Base",
    "Consent",
    "Document",
    "DocumentPage",
    "EmailOutbox",
    "EmailToken",
    "Extraction",
    "ExtractionEdit",
    "Job",
    "JurisdictionPolicy",
    "Membership",
    "Organization",
    "RateLimitCounter",
    "Session",
    "User",
]
