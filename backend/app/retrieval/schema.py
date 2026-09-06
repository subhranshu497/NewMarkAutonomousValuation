from typing import Any

from pydantic import BaseModel, Field

NO_DATA_FOUND_MESSAGE = (
    "No data found for this query — nothing in the evidence store meets the "
    "similarity threshold. Do not answer from general knowledge."
)


class RetrievedDocument(BaseModel):
    doc_id: str
    doc_type: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_system: str
    score: float  # cosine similarity in [0, 1]; higher is more relevant
    embedding: list[float] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    query: str
    query_embedding: list[float] = Field(default_factory=list)
    matches: list[RetrievedDocument] = Field(default_factory=list)

    @property
    def found(self) -> bool:
        return len(self.matches) > 0

    @property
    def message(self) -> str | None:
        """A caller-facing message to surface verbatim when there is nothing
        to ground a response in — the anti-hallucination contract for this
        layer: no matches means "say so," never a best-effort guess."""
        return None if self.found else NO_DATA_FOUND_MESSAGE
