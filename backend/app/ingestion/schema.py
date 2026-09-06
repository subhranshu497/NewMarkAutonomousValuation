from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class IngestDocument(BaseModel):
    """Canonical, embeddable representation of one retrievable record,
    regardless of which heterogeneous source format it was normalized from."""

    doc_id: str
    doc_type: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_system: str
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IngestionError(Exception):
    """Raised for a single malformed or non-uniform record. The pipeline
    catches this per-record so one bad row doesn't fail the whole batch."""

    def __init__(self, raw_record: dict[str, Any], reason: str):
        self.raw_record = raw_record
        self.reason = reason
        super().__init__(reason)


class IngestionReport(BaseModel):
    source: str
    total_records: int
    ingested: int
    skipped: int
    skipped_reasons: list[str] = Field(default_factory=list)
