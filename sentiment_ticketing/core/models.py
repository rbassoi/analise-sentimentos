from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SentimentResult:
    score: float
    label: str
    positive_matches: list[str] = field(default_factory=list)
    negative_matches: list[str] = field(default_factory=list)
    engine: str = "keyword"
    confidence: float | None = None
    model_label: str | None = None


@dataclass(frozen=True)
class Ticket:
    id: str
    subject: str = ""
    description: str = ""
    comments: list[str] = field(default_factory=list)
    status: str | None = None
    priority: str | None = None
    source: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def analysis_text(self) -> str:
        parts = [self.subject, self.description, *self.comments]
        return "\n".join(part for part in parts if part)
