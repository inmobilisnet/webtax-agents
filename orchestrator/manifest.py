from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class CreatedTenant:
    tenant_id: str
    subdomain: str
    logto_org_id: str
    persona: str


@dataclass
class CreatedUser:
    logto_user_id: str
    email: str
    role: str   # client | accountant | tenant_admin
    persona: str
    tenant_id: str | None = None


@dataclass
class RunManifest:
    run_id: str = field(default_factory=lambda: datetime.utcnow().strftime("%Y%m%d-%H%M%S"))
    scenario: str = ""
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    tenants: list[CreatedTenant] = field(default_factory=list)
    users: list[CreatedUser] = field(default_factory=list)

    def add_tenant(self, tenant_id: str, subdomain: str, logto_org_id: str, persona: str) -> None:
        self.tenants.append(CreatedTenant(tenant_id, subdomain, logto_org_id, persona))

    def add_user(self, logto_user_id: str, email: str, role: str, persona: str, tenant_id: str | None = None) -> None:
        self.users.append(CreatedUser(logto_user_id, email, role, persona, tenant_id))

    def save(self, directory: str = "runs") -> Path:
        path = Path(directory)
        path.mkdir(exist_ok=True)
        out = path / f"run-{self.run_id}.json"
        out.write_text(json.dumps(asdict(self), indent=2))
        return out

    @classmethod
    def load(cls, path: str | Path) -> RunManifest:
        data = json.loads(Path(path).read_text())
        m = cls(
            run_id=data["run_id"],
            scenario=data["scenario"],
            started_at=data["started_at"],
        )
        m.tenants = [CreatedTenant(**t) for t in data["tenants"]]
        m.users = [CreatedUser(**u) for u in data["users"]]
        return m
