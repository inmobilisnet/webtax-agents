from __future__ import annotations

import asyncio
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from browser_use import Agent, BrowserSession
from langchain_anthropic import ChatAnthropic
from rich.console import Console

from reporter.reporter import BugReport, Reporter

console = Console()


@dataclass
class Persona:
    name: str
    role: str  # client | accountant | tenant
    backstory: str
    responsiveness: str  # immediate | same_day | slow | drops_off
    thoroughness: str    # high | medium | low
    communication_style: str  # formal | casual | terse | verbose
    tech_savviness: str  # high | medium | low
    quirks: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> Persona:
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(
            name=data["name"],
            role=data["role"],
            backstory=data["backstory"],
            responsiveness=data["responsiveness"],
            thoroughness=data["thoroughness"],
            communication_style=data["communication_style"],
            tech_savviness=data["tech_savviness"],
            quirks=data.get("quirks", []),
            extra=data.get("extra", {}),
        )

    def system_prompt(self) -> str:
        quirk_text = "\n".join(f"- {q}" for q in self.quirks) if self.quirks else "None"
        return f"""You are simulating a real person interacting with a tax preparation web application.

## Your persona
Name: {self.name}
Role: {self.role}
Backstory: {self.backstory}

## Behavioural traits
- Responsiveness: {self.responsiveness} — {"You act immediately without hesitation." if self.responsiveness == "immediate" else "You sometimes take your time or get distracted." if self.responsiveness == "slow" else "You respond within a reasonable timeframe."}
- Thoroughness: {self.thoroughness} — {"You are careful and complete every step correctly." if self.thoroughness == "high" else "You sometimes skip steps or upload the wrong file by accident." if self.thoroughness == "low" else "You are reasonably careful but not perfect."}
- Communication: {self.communication_style} — Use this style when writing messages.
- Tech savviness: {self.tech_savviness} — {"You navigate confidently." if self.tech_savviness == "high" else "You sometimes struggle to find buttons or get confused by the UI." if self.tech_savviness == "low" else "You manage fine but occasionally need a moment to figure things out."}

## Quirks
{quirk_text}

## Important
- Act like a real person, not a test script.
- If you can't find something, look around the page before giving up.
- If you make a mistake consistent with your persona, that is fine — don't correct it unless a real person would notice.
- Never break character.
"""


class BaseAgent(ABC):
    def __init__(
        self,
        persona: Persona,
        session: BrowserSession,
        reporter: Reporter,
        model: str = "claude-haiku-4-5-20251001",
    ):
        self.persona = persona
        self.session = session
        self.reporter = reporter
        self.model = model
        self._action_trace: list[dict] = []

    def _build_llm(self) -> ChatAnthropic:
        return ChatAnthropic(
            model=self.model,
            max_tokens=4096,
        )

    async def run_task(self, task: str) -> str | None:
        """Run a single task through Browser Use, capturing trace and reporting failures."""
        full_task = f"{self.persona.system_prompt()}\n\n## Your task\n{task}"
        agent = Agent(
            task=full_task,
            llm=self._build_llm(),
            browser_session=self.session,
        )
        try:
            console.log(f"[bold]{self.persona.name}[/bold] → {task[:80]}…")
            history = await agent.run()
            final = history.final_result()
            self._action_trace.append({
                "task": task,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "ok",
                "result": str(final),
            })
            return str(final) if final is not None else ""
        except Exception as exc:
            tb = traceback.format_exc()
            self._action_trace.append({
                "task": task,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error",
                "error": str(exc),
            })
            screenshot = await self.session.take_screenshot()
            await self.reporter.report(BugReport(
                persona=self.persona,
                task=task,
                error=str(exc),
                traceback=tb,
                screenshot=screenshot,
                action_trace=list(self._action_trace),
            ))
            console.log(f"[red]Bug reported[/red] for {self.persona.name}: {exc}")
            return None

    @abstractmethod
    async def run(self) -> None:
        """Execute the full persona lifecycle."""
        ...
