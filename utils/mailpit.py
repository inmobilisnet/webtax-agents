"""Mailpit API client for QA email interception.

Used by agents to retrieve invite links and notification emails from Mailpit
instead of screen-scraping. Mailpit runs at mail.qa-webtax.tax in the QA env.
"""

import asyncio
import re
import urllib.error
import urllib.parse
import urllib.request
import json


DEFAULT_MAILPIT_URL = "https://mail.qa-webtax.tax"
_POLL_INTERVAL = 5  # seconds between poll attempts


async def wait_for_email(
    to_address: str,
    subject_contains: str,
    base_url: str = DEFAULT_MAILPIT_URL,
    timeout: int = 120,
) -> str:
    """Poll Mailpit until a matching email arrives. Returns the HTML body.

    Args:
        to_address:       Recipient email address to filter on.
        subject_contains: Case-insensitive substring to match in the subject.
        base_url:         Mailpit base URL (no trailing slash).
        timeout:          Maximum seconds to wait before raising TimeoutError.

    Returns:
        Full HTML body of the first matching message.

    Raises:
        TimeoutError: No matching email within `timeout` seconds.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    attempts = max(1, timeout // _POLL_INTERVAL)

    for _ in range(attempts):
        messages = _list_messages(base_url, to_address)
        for msg in messages:
            if subject_contains.lower() in msg.get("Subject", "").lower():
                return _get_html_body(base_url, msg["ID"])
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        await asyncio.sleep(min(_POLL_INTERVAL, remaining))

    raise TimeoutError(
        f"No email to {to_address!r} with subject containing {subject_contains!r} "
        f"within {timeout}s"
    )


def extract_url(html: str, pattern: str = r'https://[^\s"\'<>]+') -> str:
    """Extract the first URL matching `pattern` from an HTML string."""
    urls = re.findall(pattern, html)
    return urls[0] if urls else ""


def extract_urls(html: str, pattern: str = r'https://[^\s"\'<>]+') -> list[str]:
    """Extract all URLs matching `pattern` from an HTML string."""
    return re.findall(pattern, html)


# ── Internal ──────────────────────────────────────────────────────────────────

def _api_get(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _list_messages(base_url: str, to_address: str) -> list[dict]:
    encoded = urllib.parse.quote(f"to:{to_address}")
    url = f"{base_url}/api/v1/messages?query={encoded}&limit=50"
    try:
        data = _api_get(url)
        return data.get("messages") or []
    except (urllib.error.URLError, KeyError):
        return []


def _get_html_body(base_url: str, message_id: str) -> str:
    url = f"{base_url}/api/v1/message/{urllib.parse.quote(message_id)}"
    data = _api_get(url)
    return data.get("HTML", data.get("Text", ""))
