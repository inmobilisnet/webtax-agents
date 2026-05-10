from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    ACCOUNTANT_INVITED = "accountant_invited"
    CLIENT_INVITED = "client_invited"
    DOCUMENT_UPLOADED = "document_uploaded"
    MESSAGE_SENT = "message_sent"
    RETURN_UPLOADED = "return_uploaded"
    INVOICE_SENT = "invoice_sent"
    PAYMENT_MADE = "payment_made"
    AGENT_FAILED = "agent_failed"


@dataclass
class Event:
    type: EventType
    source: str  # persona name that emitted the event
    timestamp: datetime = field(default_factory=datetime.utcnow)
    payload: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.timestamp.isoformat()}] {self.source} → {self.type.value}"
