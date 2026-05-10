#!/usr/bin/env python3
"""
Clean up all entities created by an agent simulation run.

Usage:
    python scripts/cleanup.py runs/run-20260426-143022.json
    python scripts/cleanup.py runs/run-20260426-143022.json --dry-run

What it deletes (in safe order):
    1. Logto users (revokes sessions, removes org memberships)
    2. Logto organizations
    3. Webtax tenants via platform API (cascades to DB rows, S3 objects)

If PLATFORM_ADMIN_TOKEN is not set, it prints instructions to run the
hard-delete script on the VPS instead.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent.parent))
from orchestrator.manifest import CreatedTenant, CreatedUser, RunManifest

load_dotenv()
console = Console()

LOGTO_ENDPOINT = os.getenv("LOGTO_ENDPOINT", "")
LOGTO_M2M_TOKEN = os.getenv("LOGTO_M2M_TOKEN", "")  # management API token
WEBTAX_API_URL = os.getenv("WEBTAX_API_URL", "")
PLATFORM_ADMIN_TOKEN = os.getenv("PLATFORM_ADMIN_TOKEN", "")
AGENT_PREFIX = os.getenv("AGENT_PREFIX", "agent")


async def get_logto_token(client: httpx.AsyncClient) -> str:
    if LOGTO_M2M_TOKEN:
        return LOGTO_M2M_TOKEN
    app_id = os.getenv("LOGTO_APP_ID", "")
    app_secret = os.getenv("LOGTO_APP_SECRET", "")
    resp = await client.post(
        f"{LOGTO_ENDPOINT}/oidc/token",
        data={
            "grant_type": "client_credentials",
            "resource": "https://default.logto.app/api",
            "scope": "all",
        },
        auth=(app_id, app_secret),
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def resolve_tenant_ids(client: httpx.AsyncClient, manifest: RunManifest, token: str) -> None:
    """Fill in unknown tenant_id / logto_org_id from the platform API by subdomain."""
    if not WEBTAX_API_URL or not PLATFORM_ADMIN_TOKEN:
        return
    for t in manifest.tenants:
        if t.tenant_id != "unknown":
            continue
        resp = await client.get(
            f"{WEBTAX_API_URL}/api/v1/platform/tenants",
            headers={"Authorization": f"Bearer {PLATFORM_ADMIN_TOKEN}"},
            params={"subdomain": t.subdomain},
        )
        if resp.is_success:
            data = resp.json()
            tenants = data.get("tenants", [])
            if tenants:
                t.tenant_id = tenants[0]["id"]
                t.logto_org_id = tenants[0].get("logto_org_id", "unknown")


async def resolve_user_ids(client: httpx.AsyncClient, manifest: RunManifest, token: str) -> None:
    """Fill in unknown logto_user_id from Logto by email."""
    for u in manifest.users:
        if u.logto_user_id != "unknown":
            continue
        resp = await client.get(
            f"{LOGTO_ENDPOINT}/api/users",
            headers={"Authorization": f"Bearer {token}"},
            params={"search": u.email},
        )
        if resp.is_success:
            users = resp.json()
            if users:
                u.logto_user_id = users[0]["id"]


async def delete_logto_user(client: httpx.AsyncClient, user: CreatedUser, token: str, dry_run: bool) -> bool:
    if user.logto_user_id == "unknown":
        console.log(f"[yellow]skip[/yellow] {user.email} — logto_user_id unknown")
        return False
    if dry_run:
        console.log(f"[dim]dry-run[/dim] DELETE logto user {user.logto_user_id} ({user.email})")
        return True
    resp = await client.delete(
        f"{LOGTO_ENDPOINT}/api/users/{user.logto_user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    ok = resp.is_success
    status = "[green]ok[/green]" if ok else f"[red]fail {resp.status_code}[/red]"
    console.log(f"{status} DELETE logto user {user.email}")
    return ok


async def delete_logto_org(client: httpx.AsyncClient, tenant: CreatedTenant, token: str, dry_run: bool) -> bool:
    if tenant.logto_org_id == "unknown":
        console.log(f"[yellow]skip[/yellow] org for {tenant.subdomain} — logto_org_id unknown")
        return False
    if dry_run:
        console.log(f"[dim]dry-run[/dim] DELETE logto org {tenant.logto_org_id} ({tenant.subdomain})")
        return True
    resp = await client.delete(
        f"{LOGTO_ENDPOINT}/api/organizations/{tenant.logto_org_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    ok = resp.is_success
    status = "[green]ok[/green]" if ok else f"[red]fail {resp.status_code}[/red]"
    console.log(f"{status} DELETE logto org {tenant.subdomain}")
    return ok


async def delete_webtax_tenant(client: httpx.AsyncClient, tenant: CreatedTenant, dry_run: bool) -> bool:
    if not WEBTAX_API_URL or not PLATFORM_ADMIN_TOKEN:
        console.log(
            f"[yellow]manual[/yellow] No PLATFORM_ADMIN_TOKEN — to delete tenant '{tenant.subdomain}' "
            f"(id={tenant.tenant_id}), SSH into the VPS and run:\n"
            f"  cd /opt/webtax && go run scripts/hard-delete-tenant/main.go {tenant.tenant_id}"
        )
        return False
    if tenant.tenant_id == "unknown":
        console.log(f"[yellow]skip[/yellow] {tenant.subdomain} — tenant_id unknown")
        return False
    if dry_run:
        console.log(f"[dim]dry-run[/dim] DELETE webtax tenant {tenant.tenant_id} ({tenant.subdomain})")
        return True
    resp = await client.delete(
        f"{WEBTAX_API_URL}/api/v1/platform/tenants/{tenant.tenant_id}",
        headers={"Authorization": f"Bearer {PLATFORM_ADMIN_TOKEN}"},
    )
    ok = resp.is_success
    status = "[green]ok[/green]" if ok else f"[red]fail {resp.status_code}[/red]"
    console.log(f"{status} DELETE webtax tenant {tenant.subdomain}")
    return ok


def print_manifest_summary(manifest: RunManifest) -> None:
    console.rule(f"[bold]Run {manifest.run_id} — {manifest.scenario}")
    t = Table()
    t.add_column("Type")
    t.add_column("Identifier")
    t.add_column("Persona")
    for tenant in manifest.tenants:
        t.add_row("tenant", tenant.subdomain, tenant.persona)
    for user in manifest.users:
        t.add_row(user.role, user.email, user.persona)
    console.print(t)


async def run(manifest_path: str, dry_run: bool) -> None:
    manifest = RunManifest.load(manifest_path)
    print_manifest_summary(manifest)

    if not LOGTO_ENDPOINT:
        console.print("[red]LOGTO_ENDPOINT not set — cannot delete Logto entities[/red]")
        return

    async with httpx.AsyncClient(timeout=30) as client:
        token = await get_logto_token(client)
        await resolve_tenant_ids(client, manifest, token)
        await resolve_user_ids(client, manifest, token)

        console.rule("Deleting users")
        for user in manifest.users:
            await delete_logto_user(client, user, token, dry_run)

        console.rule("Deleting organizations + tenants")
        for tenant in manifest.tenants:
            await delete_logto_org(client, tenant, token, dry_run)
            await delete_webtax_tenant(client, tenant, dry_run)

    console.rule("[green]Done" if not dry_run else "[dim]Dry run complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up a webtax-agents simulation run")
    parser.add_argument("manifest", help="Path to the run manifest JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be deleted without deleting")
    args = parser.parse_args()
    asyncio.run(run(args.manifest, args.dry_run))


if __name__ == "__main__":
    main()
