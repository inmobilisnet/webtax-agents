from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import yaml
from browser_use import BrowserSession
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from agents.accountant import AccountantAgent
from agents.base import Persona
from agents.client import ClientAgent
from agents.tenant import TenantAgent
from orchestrator.events import Event, EventType
from orchestrator.manifest import RunManifest
from reporter.linear import LinearReporter
from reporter.reporter import Reporter

load_dotenv()
console = Console()

PERSONAS_DIR = Path(__file__).parent.parent / "personas"


def load_persona(role: str, name: str) -> Persona:
    path = PERSONAS_DIR / role / f"{name}.yaml"
    return Persona.load(path)


def _make_session(browser_type: str) -> BrowserSession:
    # browser-use >= 0.1.x — BrowserProfile controls the underlying Playwright browser.
    # Set AGENT_HEADLESS=0 to open visible browser windows (useful for local debugging).
    headless = os.getenv("AGENT_HEADLESS", "1") != "0"
    try:
        from browser_use.browser.profile import BrowserProfile
        return BrowserSession(browser_profile=BrowserProfile(
            browser_type=browser_type,
            headless=headless,
        ))
    except (ImportError, TypeError):
        return BrowserSession()


class Orchestrator:
    def __init__(self, scenario: dict[str, Any]):
        self.scenario = scenario
        self.events: list[Event] = []
        self.model = os.getenv("AGENT_MODEL", "claude-haiku-4-5-20251001")
        self.reporter: Reporter = LinearReporter()
        self.base_url = os.getenv("BASE_URL", "http://taxbros1.localhost:3000")
        self.main_url = os.getenv("MAIN_URL", "http://localhost:3000")
        self.manifest = RunManifest(scenario=scenario.get("name", "unnamed"))

    def emit(self, event: Event) -> None:
        self.events.append(event)
        console.log(str(event))

    async def run_tenant_phase(self, session: BrowserSession) -> None:
        cfg = self.scenario.get("tenant")
        if not cfg:
            return
        persona = load_persona("tenants", cfg["persona"])
        agent = TenantAgent(persona, session, self.reporter, self.manifest, self.main_url, self.model)
        await agent.run()
        self.emit(Event(EventType.ACCOUNTANT_INVITED, persona.name))

    async def run_accountant_phase(self, session: BrowserSession, invite_url: str | None = None) -> None:
        cfg = self.scenario.get("accountant")
        if not cfg:
            return
        persona = load_persona("accountants", cfg["persona"])
        app_url = self.base_url
        agent = AccountantAgent(persona, session, self.reporter, self.manifest, app_url, invite_url, self.model)
        await agent.run()
        self.emit(Event(EventType.RETURN_UPLOADED, persona.name))

    async def run_client_phase(self, session: BrowserSession, client_cfg: dict[str, Any]) -> None:
        persona = load_persona("clients", client_cfg["persona"])
        agent = ClientAgent(
            persona=persona,
            session=session,
            reporter=self.reporter,
            manifest=self.manifest,
            tenant_url=self.base_url,
            entry=client_cfg.get("entry", "invited"),
            invite_url=client_cfg.get("invite_url"),
            model=self.model,
        )
        await agent.run()
        self.emit(Event(EventType.PAYMENT_MADE, persona.name))

    async def run(self) -> None:
        console.rule(f"[bold green]Scenario: {self.scenario.get('name', 'unnamed')}")

        # Each role gets an isolated browser session (separate cookie/auth store).
        # webkit = Safari (tenant/org_admin), msedge = Edge (accountant), chromium = Chrome (clients).
        async with (
            _make_session("webkit") as tenant_session,
            _make_session("msedge") as accountant_session,
            _make_session("chromium") as client_session,
        ):
            await self.run_tenant_phase(tenant_session)

            client_tasks = [
                self.run_client_phase(client_session, cfg)
                for cfg in self.scenario.get("clients", [])
            ]

            await asyncio.gather(
                self.run_accountant_phase(accountant_session),
                *client_tasks,
            )

        saved = self.manifest.save()
        console.print(f"[green]Manifest saved:[/green] {saved}")
        self._print_summary()

    def _print_summary(self) -> None:
        table = Table(title="Simulation Summary")
        table.add_column("Time")
        table.add_column("Actor")
        table.add_column("Event")
        for e in self.events:
            table.add_row(e.timestamp.strftime("%H:%M:%S"), e.source, e.type.value)
        console.print(table)


def main() -> None:
    import sys
    scenario_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("scenarios/full_flow.yaml")
    with open(scenario_path) as f:
        scenario = yaml.safe_load(f)
    asyncio.run(Orchestrator(scenario).run())


if __name__ == "__main__":
    main()
