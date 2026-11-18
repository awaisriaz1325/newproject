"""Extraction quality tracking from human corrections (ML spec §6.3).

Edit rate per (extractor, doc_type, field) = edits / extractions seen. A field whose edit rate rises
for an extractor signals drift (e.g. a new carrier template) and should lower its auto-ready
threshold or route documents to review.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

_INDEX = re.compile(r"\[\d+\]")


@dataclass(frozen=True)
class FieldQuality:
    extractor: str
    doc_type: str
    field: str
    extractions: int
    edits: int

    @property
    def edit_rate(self) -> float:
        return self.edits / self.extractions if self.extractions else 0.0


def edit_rates(
    extractions: list[tuple[str, str, str]],  # (extraction_id, extractor, doc_type)
    edits: list[tuple[str, str]],  # (extraction_id, field_path)
) -> list[FieldQuality]:
    meta = {eid: (extractor, doc_type) for eid, extractor, doc_type in extractions}
    seen: Counter[tuple[str, str]] = Counter(meta.values())
    counts: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for eid, path in edits:
        if eid in meta:
            extractor, doc_type = meta[eid]
            counts[(extractor, doc_type, _INDEX.sub("[]", path))].add(eid)
    return sorted(
        (FieldQuality(ex, dt, f, seen[(ex, dt)], len(ids)) for (ex, dt, f), ids in counts.items()),
        key=lambda q: -q.edit_rate,
    )
