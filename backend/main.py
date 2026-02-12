"""GitTime AI – FastAPI backend powered by LangGraph."""

from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager

import logging

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("gittime")

from models import RepoRequest, AnalysisResponse, Feature
from github_client import GitHubClient
from agent import RepoAnalyzerAgent

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

gh: GitHubClient | None = None
agent: RepoAnalyzerAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global gh, agent
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("gsk_your"):
        logger.warning("⚠️  GROQ_API_KEY is not set! Create a backend/.env file.")
    if not GITHUB_TOKEN or GITHUB_TOKEN.startswith("ghp_your"):
        logger.warning("⚠️  GITHUB_TOKEN is not set — GitHub API is limited to 60 req/hr. Add it to backend/.env for higher limits.")
    gh = GitHubClient(token=GITHUB_TOKEN or None)
    agent = RepoAnalyzerAgent(api_key=GROQ_API_KEY, gh=gh)
    yield
    if gh:
        await gh.close()


app = FastAPI(title="GitTime AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── helpers ──────────────────────────────────────────────────


def _parse_repo_url(url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL or 'owner/repo' string."""
    url = url.strip().rstrip("/")
    m = re.match(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$", url)
    if m:
        return m.group(1), m.group(2)
    m = re.search(r"github\.com/([^/]+)/([^/]+)", url)
    if not m:
        raise ValueError("Invalid GitHub repository URL")
    return m.group(1), m.group(2).replace(".git", "")


# ── endpoints ────────────────────────────────────────────────


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_repo(req: RepoRequest):
    """Run the LangGraph analyze agent on a public repo."""
    assert agent

    try:
        owner, repo = _parse_repo_url(req.repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        features = await agent.analyze_repo(owner, repo)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return AnalysisResponse(repo=f"{owner}/{repo}", features=features)


@app.post("/api/feature-timeline")
async def feature_timeline(req: dict):
    """Run the LangGraph timeline agent for a single feature."""
    assert agent

    try:
        owner, repo = _parse_repo_url(req["repo"])
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    feature = Feature(**req["feature"])

    try:
        versions = await agent.feature_timeline(owner, repo, feature)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"feature_id": feature.id, "versions": [v.model_dump() for v in versions]}


@app.post("/api/feature-evolution")
async def feature_evolution(req: dict):
    """Run the LangGraph evolution agent – commit-level feature evolution using Agent 1 output."""
    assert agent

    try:
        owner, repo = _parse_repo_url(req["repo"])
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    feature = Feature(**req["feature"])

    try:
        evolution = await agent.feature_evolution(owner, repo, feature)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"feature_id": feature.id, "evolution": evolution}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
