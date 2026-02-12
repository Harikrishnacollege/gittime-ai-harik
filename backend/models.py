"""Pydantic models & LangGraph state for the GitTime AI API."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel


# ── API request / response models ────────────────────────────


class RepoRequest(BaseModel):
    repo_url: str  # e.g. "https://github.com/owner/repo"


class VersionEntry(BaseModel):
    version: str          # tag name or short SHA
    date: str             # ISO date
    description: str      # AI-generated summary of changes for this feature


class Feature(BaseModel):
    id: str
    name: str
    description: str
    files: list[str]             # key files involved
    versions: list[VersionEntry] # linear timeline


class AnalysisResponse(BaseModel):
    repo: str
    features: list[Feature]


# ── LangGraph agent state ───────────────────────────────────


class RepoContext(TypedDict, total=False):
    """Raw data fetched from GitHub."""
    readme: str
    tree_paths: list[str]
    commits_summary: str
    releases_summary: str
    all_commits_raw: list[dict]
    releases_raw: list[dict]
    tags_raw: list[dict]


class AnalyzeState(TypedDict, total=False):
    """State flowing through the analyze-repo graph."""
    owner: str
    repo: str
    context: RepoContext
    features: list[dict]       # raw dicts before Pydantic conversion
    error: str


class TimelineState(TypedDict, total=False):
    """State flowing through the feature-timeline graph."""
    owner: str
    repo: str
    feature: dict              # Feature as dict
    commits_for_feature: str
    releases_summary: str
    versions: list[dict]       # VersionEntry dicts
    error: str


# ── Agent 3 – Feature Evolution state ────────────────────────


class FileChange(BaseModel):
    filename: str
    status: str                # added, modified, removed, renamed
    additions: int             # lines added
    deletions: int             # lines deleted
    patch: str                 # truncated diff snippet


class CommitEvolution(BaseModel):
    sha: str
    date: str
    message: str
    author: str
    files_changed: list[FileChange]
    evolution_summary: str     # AI-generated: how this commit advanced the feature


class EvolutionState(TypedDict, total=False):
    """State flowing through the feature-evolution graph."""
    owner: str
    repo: str
    feature: dict              # { name, description, files }
    raw_commits: list[dict]    # commit detail dicts with file changes
    evolution: list[dict]      # CommitEvolution dicts
    error: str
