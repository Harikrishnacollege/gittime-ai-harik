"""GitHub API client – fetches repo metadata, tree, commits, tags, and README."""

from __future__ import annotations

import httpx

_BASE = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str | None = None):
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(base_url=_BASE, headers=headers, timeout=30)
        self._auth_failed = False

    # ── helpers ──────────────────────────────────────────────

    async def _get_json(self, path: str, params: dict | None = None):
        r = await self._client.get(path, params=params)
        # If token is invalid, drop it and retry unauthenticated (public repos still work)
        if r.status_code == 401 and not self._auth_failed:
            self._auth_failed = True
            self._client.headers.pop("Authorization", None)
            r = await self._client.get(path, params=params)
        if r.status_code == 403:
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            msg = body.get("message", "Forbidden")
            raise Exception(f"403 Forbidden: {msg}")
        if r.status_code == 404:
            raise Exception(f"404 Not Found: {path}")
        r.raise_for_status()
        return r.json()

    # ── public methods ───────────────────────────────────────

    async def repo_info(self, owner: str, repo: str) -> dict:
        return await self._get_json(f"/repos/{owner}/{repo}")

    async def readme(self, owner: str, repo: str) -> str:
        """Return raw README text (markdown)."""
        r = await self._client.get(
            f"/repos/{owner}/{repo}/readme",
            headers={"Accept": "application/vnd.github.raw+json"},
        )
        if r.status_code == 404:
            return ""
        r.raise_for_status()
        return r.text

    async def tree(self, owner: str, repo: str, sha: str = "HEAD") -> list[dict]:
        """Return the full recursive tree (path + type)."""
        data = await self._get_json(
            f"/repos/{owner}/{repo}/git/trees/{sha}",
            params={"recursive": "1"},
        )
        return data.get("tree", [])

    async def commits(self, owner: str, repo: str, per_page: int = 100) -> list[dict]:
        return await self._get_json(
            f"/repos/{owner}/{repo}/commits",
            params={"per_page": per_page},
        )

    async def tags(self, owner: str, repo: str) -> list[dict]:
        return await self._get_json(f"/repos/{owner}/{repo}/tags")

    async def releases(self, owner: str, repo: str) -> list[dict]:
        return await self._get_json(
            f"/repos/{owner}/{repo}/releases",
            params={"per_page": 50},
        )

    async def commit_detail(self, owner: str, repo: str, sha: str) -> dict:
        return await self._get_json(f"/repos/{owner}/{repo}/commits/{sha}")

    async def file_content(self, owner: str, repo: str, path: str) -> str:
        """Return raw file content."""
        r = await self._client.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            headers={"Accept": "application/vnd.github.raw+json"},
        )
        if r.status_code == 404:
            return ""
        r.raise_for_status()
        return r.text

    async def close(self):
        await self._client.aclose()
