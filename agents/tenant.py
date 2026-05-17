from __future__ import annotations

from browser_use import BrowserSession

from agents.base import BaseAgent, Persona
from orchestrator.manifest import RunManifest
from reporter.reporter import Reporter
from utils import mailpit
from utils.naming import agent_email, agent_firm_name, agent_subdomain


class TenantAgent(BaseAgent):
    def __init__(
        self,
        persona: Persona,
        session: BrowserSession,
        reporter: Reporter,
        manifest: RunManifest,
        main_url: str,
        model: str = "claude-haiku-4-5-20251001",
    ):
        super().__init__(persona, session, reporter, model)
        self.manifest = manifest
        self.main_url = main_url
        self.subdomain = agent_subdomain(persona.name)
        self.firm_name = agent_firm_name(persona.name)
        self.email = agent_email(persona.name)

    async def _sign_up(self) -> bool:
        result = await self.run_task(
            f"Go to {self.main_url}. "
            "Find the sign-up or 'start a free trial' option for accounting firms. "
            f"Register using these exact details:\n"
            f"  - Firm name: {self.firm_name}\n"
            f"  - Subdomain: {self.subdomain}\n"
            f"  - Email: {self.email}\n"
            "Use a strong made-up password. Complete the registration and land on the admin dashboard. "
            "Return the tenant ID or subdomain confirmed on screen."
        )
        if result:
            # Manifest will be fully populated by cleanup tooling via API query on the prefix;
            # record what we know from the agent's perspective.
            self.manifest.add_tenant(
                tenant_id="unknown",  # resolved at cleanup time via subdomain lookup
                subdomain=self.subdomain,
                logto_org_id="unknown",
                persona=self.persona.name,
            )
            self.manifest.add_user(
                logto_user_id="unknown",
                email=self.email,
                role="tenant_admin",
                persona=self.persona.name,
            )
        return bool(result)

    async def _configure_branding(self) -> bool:
        if self.persona.extra.get("skip_branding"):
            return True
        return bool(await self.run_task(
            "Find the branding or settings section. "
            f"Set the firm name to '{self.firm_name}'. Save the changes."
        ))

    async def _invite_accountant(self, accountant_email: str) -> str | None:
        result = await self.run_task(
            f"Invite a new accountant with email '{accountant_email}'. "
            "Complete the invite flow and confirm the invite was sent."
        )
        if not result:
            return None
        self.manifest.add_user(
            logto_user_id="unknown",
            email=accountant_email,
            role="accountant",
            persona="invited-accountant",
        )
        try:
            html = await mailpit.wait_for_email(
                to_address=accountant_email,
                subject_contains="invite",
            )
            return mailpit.extract_url(html)
        except TimeoutError:
            return None

    async def invite_client(self, client_email: str, client_persona: str) -> str | None:
        result = await self.run_task(
            f"Invite a new client with email '{client_email}'. "
            "Complete the invite flow and confirm the invite was sent."
        )
        if not result:
            return None
        self.manifest.add_user(
            logto_user_id="unknown",
            email=client_email,
            role="client",
            persona=client_persona,
        )
        try:
            html = await mailpit.wait_for_email(
                to_address=client_email,
                subject_contains="invite",
            )
            return mailpit.extract_url(html)
        except TimeoutError:
            return None

    async def _check_dashboard(self) -> None:
        await self.run_task(
            "Review the admin dashboard. Note how many clients and accountants are active "
            "and check for any alerts. Do not take action."
        )

    async def run(self, accountant_email: str | None = None) -> str | None:
        ok = await self._sign_up()
        if not ok:
            return None

        await self._configure_branding()

        invite_url = None
        if accountant_email:
            invite_url = await self._invite_accountant(accountant_email)

        await self._check_dashboard()
        return invite_url
