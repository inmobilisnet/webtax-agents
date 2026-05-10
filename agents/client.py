from __future__ import annotations

import asyncio
import os
import random
from pathlib import Path

from browser_use import BrowserSession

from agents.base import BaseAgent, Persona
from orchestrator.manifest import RunManifest
from reporter.reporter import Reporter
from utils.fake_documents import generate_source_documents
from utils.naming import agent_email

RESPONSIVENESS_DELAYS = {
    "immediate": (1, 5),
    "same_day": (10, 60),
    "slow": (60, 300),
    "drops_off": (300, 900),
}


class ClientAgent(BaseAgent):
    def __init__(
        self,
        persona: Persona,
        session: BrowserSession,
        reporter: Reporter,
        manifest: RunManifest,
        tenant_url: str,
        entry: str = "invited",  # invited | self_signup
        invite_url: str | None = None,
        model: str = "claude-haiku-4-5-20251001",
    ):
        super().__init__(persona, session, reporter, model)
        self.manifest = manifest
        self.tenant_url = tenant_url
        self.entry = entry
        self.invite_url = invite_url
        self.email = agent_email(persona.name)
        self.documents: list[Path] = []

    async def _delay(self) -> None:
        lo, hi = RESPONSIVENESS_DELAYS[self.persona.responsiveness]
        speed = os.getenv("SIMULATION_SPEED", "normal")
        divisor = {"fast": 30, "normal": 10, "slow": 1}[speed]
        await asyncio.sleep(random.uniform(lo, hi) / divisor)

    async def _sign_up_via_invite(self) -> bool:
        if not self.invite_url:
            return False
        result = await self.run_task(
            f"Open this invite link: {self.invite_url}. "
            f"Complete account setup using email '{self.email}' and a made-up password. "
            "Finish signing up and land on the dashboard."
        )
        if result:
            self.manifest.add_user(
                logto_user_id="unknown",
                email=self.email,
                role="client",
                persona=self.persona.name,
            )
        return bool(result)

    async def _sign_up_self(self) -> bool:
        result = await self.run_task(
            f"Go to {self.tenant_url}. "
            "Find the sign-up link and create a new client account. "
            f"Use email '{self.email}' and a made-up password. "
            "Complete the registration and land on the dashboard."
        )
        if result:
            self.manifest.add_user(
                logto_user_id="unknown",
                email=self.email,
                role="client",
                persona=self.persona.name,
            )
        return bool(result)

    async def _upload_documents(self) -> None:
        self.documents = generate_source_documents(self.persona)
        upload_count = len(self.documents)
        if self.persona.thoroughness == "low":
            upload_count = max(1, upload_count - random.randint(1, 2))

        for doc in self.documents[:upload_count]:
            await self._delay()
            await self.run_task(
                f"Upload the file at '{doc}' to the documents section. "
                "Find the upload area, select the file, and confirm it uploaded successfully."
            )

    async def _check_and_reply_to_messages(self) -> None:
        await self._delay()
        await self.run_task(
            "Check your messages or inbox. If there are any unread messages from your accountant, "
            "read them and write a reply consistent with your communication style and backstory. "
            "If there are no messages, do nothing."
        )

    async def _download_return(self) -> None:
        await self._delay()
        await self.run_task(
            "Check if your completed tax return is available for download. "
            "If it is, download it. If not, do nothing."
        )

    async def _pay_invoice(self) -> None:
        await self._delay()
        await self.run_task(
            "Check if there is an outstanding invoice or payment due. "
            "If so, complete the payment using test card 4242 4242 4242 4242, "
            "any future expiry, CVC 123. If there is no invoice, do nothing."
        )

    async def run(self) -> None:
        if self.entry == "invited":
            ok = await self._sign_up_via_invite()
        else:
            ok = await self._sign_up_self()

        if not ok:
            return

        await self._upload_documents()
        await self._check_and_reply_to_messages()
        await self._download_return()
        await self._pay_invoice()
