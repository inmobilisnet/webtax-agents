from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agents.base import Persona


@dataclass
class BugReport:
    persona: Persona
    task: str
    error: str
    traceback: str
    screenshot: bytes | None
    action_trace: list[dict[str, Any]]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def title(self) -> str:
        return f"[agent] {self.persona.role}/{self.persona.name}: {self.error[:80]}"

    def body(self) -> str:
        trace_text = json.dumps(self.action_trace, indent=2)
        return (
            f"## Persona\n"
            f"- **Name:** {self.persona.name}\n"
            f"- **Role:** {self.persona.role}\n"
            f"- **Responsiveness:** {self.persona.responsiveness}\n"
            f"- **Thoroughness:** {self.persona.thoroughness}\n\n"
            f"## Task\n{self.task}\n\n"
            f"## Error\n```\n{self.error}\n```\n\n"
            f"## Traceback\n```\n{self.traceback}\n```\n\n"
            f"## Action Trace\n```json\n{trace_text}\n```"
        )


class Reporter(ABC):
    @abstractmethod
    async def report(self, bug: BugReport) -> None: ...


class LocalReporter(Reporter):
    """Writes bug reports to ./bug-reports/ as JSON + screenshot."""

    def __init__(self, output_dir: str = "bug-reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    async def report(self, bug: BugReport) -> None:
        slug = f"{bug.timestamp.strftime('%Y%m%d-%H%M%S')}-{bug.persona.name.replace(' ', '_')}"
        report_path = self.output_dir / f"{slug}.json"
        report_path.write_text(json.dumps({
            "title": bug.title(),
            "body": bug.body(),
            "timestamp": bug.timestamp.isoformat(),
        }, indent=2))

        if bug.screenshot:
            screenshot_path = self.output_dir / f"{slug}.png"
            screenshot_path.write_bytes(bug.screenshot)
