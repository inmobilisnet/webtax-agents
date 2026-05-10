from __future__ import annotations

import os
import re
from datetime import datetime


def _prefix() -> str:
    return os.getenv("AGENT_PREFIX", "agent")


def _email_domain() -> str:
    return os.getenv("AGENT_EMAIL_DOMAIN", "webtax-agent.test")


def _run_tag() -> str:
    """Short timestamp tag, stable within a process lifetime."""
    if not hasattr(_run_tag, "_cached"):
        _run_tag._cached = datetime.utcnow().strftime("%m%d-%H%M")
    return _run_tag._cached


def agent_subdomain(persona_name: str) -> str:
    """e.g. 'agent-gary-0426-1430'"""
    slug = re.sub(r"[^a-z0-9]", "-", persona_name.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return f"{_prefix()}-{slug}-{_run_tag()}"


def agent_firm_name(persona_name: str) -> str:
    """e.g. '[agent] Growing Firm Gary'"""
    return f"[{_prefix()}] {persona_name}"


def agent_email(persona_name: str) -> str:
    """e.g. 'agent.diana.0426-1430@webtax-agent.test'"""
    slug = re.sub(r"[^a-z0-9]", ".", persona_name.lower()).strip(".")
    slug = re.sub(r"\.+", ".", slug)
    return f"{_prefix()}.{slug}.{_run_tag()}@{_email_domain()}"
