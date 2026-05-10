from __future__ import annotations

import base64
import os

import httpx

from reporter.reporter import BugReport, Reporter

LINEAR_API = "https://api.linear.app/graphql"


class LinearReporter(Reporter):
    """Creates Linear issues for agent-detected bugs."""

    def __init__(self):
        self.api_key = os.getenv("LINEAR_API_KEY", "")
        self.team_id = os.getenv("LINEAR_TEAM_ID", "")
        self.label_id = os.getenv("LINEAR_BUG_LABEL_ID")  # optional

    def _headers(self) -> dict[str, str]:
        return {"Authorization": self.api_key, "Content-Type": "application/json"}

    async def _upload_screenshot(self, client: httpx.AsyncClient, screenshot: bytes) -> str | None:
        """Upload screenshot to Linear file storage and return the URL."""
        try:
            mutation = """
            mutation CreateFileUpload($contentType: String!, $filename: String!, $size: Int!) {
              fileUpload(contentType: $contentType, filename: $filename, size: $size) {
                uploadFile { uploadUrl url headers { key value } }
              }
            }
            """
            resp = await client.post(LINEAR_API, headers=self._headers(), json={
                "query": mutation,
                "variables": {
                    "contentType": "image/png",
                    "filename": "screenshot.png",
                    "size": len(screenshot),
                },
            })
            data = resp.json()
            upload = data["data"]["fileUpload"]["uploadFile"]
            upload_headers = {h["key"]: h["value"] for h in upload["headers"]}
            await client.put(upload["uploadUrl"], content=screenshot, headers=upload_headers)
            return upload["url"]
        except Exception:
            return None

    async def report(self, bug: BugReport) -> None:
        if not self.api_key or not self.team_id:
            from reporter.reporter import LocalReporter
            await LocalReporter().report(bug)
            return

        async with httpx.AsyncClient(timeout=30) as client:
            screenshot_url = None
            if bug.screenshot:
                screenshot_url = await self._upload_screenshot(client, bug.screenshot)

            body = bug.body()
            if screenshot_url:
                body += f"\n\n## Screenshot\n![screenshot]({screenshot_url})"

            label_ids = [self.label_id] if self.label_id else []

            mutation = """
            mutation CreateIssue($input: IssueCreateInput!) {
              issueCreate(input: $input) {
                success
                issue { id identifier url }
              }
            }
            """
            variables = {
                "input": {
                    "teamId": self.team_id,
                    "title": bug.title(),
                    "description": body,
                    "priority": 2,  # medium
                    **({"labelIds": label_ids} if label_ids else {}),
                }
            }
            resp = await client.post(LINEAR_API, headers=self._headers(), json={
                "query": mutation,
                "variables": variables,
            })
            result = resp.json()
            issue = result.get("data", {}).get("issueCreate", {}).get("issue")
            if issue:
                from rich.console import Console
                Console().log(f"[yellow]Linear issue created:[/yellow] {issue['url']}")
            else:
                from reporter.reporter import LocalReporter
                await LocalReporter().report(bug)
