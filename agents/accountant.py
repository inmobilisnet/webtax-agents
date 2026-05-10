from __future__ import annotations

import asyncio
import os
import random
from pathlib import Path

from browser_use import BrowserSession

from agents.base import BaseAgent, Persona
from orchestrator.manifest import RunManifest
from reporter.reporter import Reporter
from utils.fake_documents import generate_completed_return
from utils.naming import agent_email

RESPONSIVENESS_DELAYS = {
    "immediate": (1, 5),
    "same_day": (10, 60),
    "slow": (60, 300),
    "drops_off": (300, 900),
}


class AccountantAgent(BaseAgent):
    def __init__(
        self,
        persona: Persona,
        session: BrowserSession,
        reporter: Reporter,
        manifest: RunManifest,
        app_url: str,
        invite_url: str | None = None,
        model: str = "claude-haiku-4-5-20251001",
    ):
        super().__init__(persona, session, reporter, model)
        self.manifest = manifest
        self.app_url = app_url
        self.invite_url = invite_url
        self.email = agent_email(persona.name)

    async def _delay(self) -> None:
        lo, hi = RESPONSIVENESS_DELAYS[self.persona.responsiveness]
        speed = os.getenv("SIMULATION_SPEED", "normal")
        divisor = {"fast": 30, "normal": 10, "slow": 1}[speed]
        await asyncio.sleep(random.uniform(lo, hi) / divisor)

    async def _accept_invite(self) -> bool:
        result = await self.run_task(
            f"Open this invite link: {self.invite_url}. "
            f"Complete account setup using email '{self.email}' and a made-up password. "
            "Land on the accountant dashboard."
        )
        if result:
            self.manifest.add_user(
                logto_user_id="unknown",
                email=self.email,
                role="accountant",
                persona=self.persona.name,
            )
        return bool(result)

    async def _review_clients(self) -> None:
        await self.run_task(
            "Review your client list. Note which clients have uploaded documents "
            "and which are still pending. Do not take any action yet — just observe."
        )

    async def _request_missing_documents(self) -> None:
        await self._delay()
        await self.run_task(
            "Look through your clients. For any client missing documents or not yet uploaded anything, "
            "send them a message requesting what you'd expect for a typical individual tax return "
            "(W-2, 1099s, etc.). Keep your message consistent with your communication style."
        )

    async def _reply_to_messages(self) -> None:
        await self._delay()
        await self.run_task(
            "Check your messages. Reply to any unread messages from clients. "
            "Your replies should be professional, helpful, and consistent with your persona."
        )

    async def _upload_completed_return(self) -> None:
        await self._delay()
        client_name = await self.run_task(
            "Look at your client list. Identify any client who has submitted all their documents "
            "and is ready for their return. Return just their name, or 'none' if no one is ready."
        )
        if not client_name or "none" in (client_name or "").lower():
            return

        return_pdf = generate_completed_return(client_name)
        await self.run_task(
            f"For the client '{client_name}', upload their completed tax return. "
            f"The file is at: {return_pdf}. "
            "Find the section to upload completed returns for this client and upload it."
        )

    async def _send_invoice(self) -> None:
        await self._delay()
        await self.run_task(
            "Check if any clients have received their completed return but haven't been invoiced. "
            "If so, send an invoice to the first such client for a reasonable fee ($150–$400)."
        )

    async def run(self) -> None:
        if self.invite_url:
            ok = await self._accept_invite()
            if not ok:
                return

        await self._review_clients()
        await self._request_missing_documents()
        await self._reply_to_messages()
        await self._upload_completed_return()
        await self._send_invoice()
