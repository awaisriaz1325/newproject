"""Class code review assistant (ML spec §6.1) — behind the reference-data licensing gate.

Output is always "needs expert review", never "this code is wrong". Retrieval ranks reference class
descriptions by TF-IDF cosine similarity to the employer's operations description; an assigned code
that is not among the top-k matches is surfaced as a review candidate.

Reference data: ``PlaceholderReferenceProvider`` contains short descriptions written for this
project (not copied from NCCI or any bureau manual, which may be licensed — see
docs/phase-0/02). Swap in a
licensed provider only after founder decision FD-04.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(frozen=True)
class ClassReference:
    code: str
    summary: str


class ClassificationReferenceProvider(Protocol):
    name: str
    licensed_for_production: bool

    def references(self, state: str) -> list[ClassReference]: ...


class PlaceholderReferenceProvider:
    """Self-authored, illustrative descriptions. NOT authoritative; codes are illustrative."""

    name = "placeholder-v1"
    licensed_for_production = False

    _DATA = (
        ClassReference(
            "8810", "clerical office staff desk work bookkeeping reception computers administrative"
        ),
        ClassReference(
            "8742",
            "outside sales representatives travel visiting customers selling "
            "estimating away from office",
        ),
        ClassReference(
            "5551", "roofing roofers installing repairing shingles roofs ladders tear off"
        ),
        ClassReference(
            "5645", "residential carpentry framing houses wood construction building homes"
        ),
        ClassReference("5403", "commercial carpentry framing commercial buildings wood forms"),
        ClassReference(
            "0042", "landscaping lawn care mowing planting trees gardening grounds maintenance"
        ),
        ClassReference(
            "5190", "electrical wiring electricians installing electrical systems buildings"
        ),
        ClassReference("3632", "machine shop machining metal parts lathes mills fabrication"),
        ClassReference("5183", "plumbing plumbers installing pipes water heaters drains"),
        ClassReference("7380", "drivers delivery truck driving chauffeurs hauling"),
        ClassReference("9014", "janitorial cleaning buildings custodial services"),
        ClassReference("5474", "painting interior exterior painters drywall finishing"),
    )

    def references(self, state: str) -> list[ClassReference]:
        del state
        return list(self._DATA)


@dataclass(frozen=True)
class Suggestion:
    code: str
    score: float


@dataclass(frozen=True)
class ReviewResult:
    assigned_code: str
    needs_expert_review: bool
    assigned_rank: int | None
    suggestions: list[Suggestion]
    provider: str
    disclaimer: str = (
        "Automated suggestion for expert review only. It does not mean the "
        "assigned class code is wrong."
    )


class ClassCodeAssistant:
    def __init__(self, provider: ClassificationReferenceProvider, k: int = 3) -> None:
        self.provider = provider
        self.k = k

    def rank(self, operations: str, state: str) -> list[Suggestion]:
        refs = self.provider.references(state)
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        matrix = vectorizer.fit_transform([r.summary for r in refs] + [operations])
        sims = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
        order = sorted(range(len(refs)), key=lambda i: (-sims[i], refs[i].code))
        return [Suggestion(refs[i].code, round(float(sims[i]), 4)) for i in order]

    def review(self, assigned_code: str, operations: str, state: str) -> ReviewResult:
        ranked = self.rank(operations, state)
        codes = [s.code for s in ranked]
        rank = codes.index(assigned_code) + 1 if assigned_code in codes else None
        flagged = rank is None or rank > self.k
        return ReviewResult(assigned_code, flagged, rank, ranked[: self.k], self.provider.name)


def top_k_recall(
    assistant: ClassCodeAssistant, labeled: list[tuple[str, str]], k: int, state: str = "NC"
) -> float:
    """Share of (operations text, correct code) pairs whose code appears in the top-k."""
    hits = sum(code in [s.code for s in assistant.rank(text, state)[:k]] for text, code in labeled)
    return hits / len(labeled) if labeled else 0.0
