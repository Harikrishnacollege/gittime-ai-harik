"""LangGraph-based AI agent for feature extraction & version timelines."""

from __future__ import annotations

import hashlib
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph

from github_client import GitHubClient
from models import AnalyzeState, EvolutionState, Feature, RepoContext, TimelineState, VersionEntry


def _feature_id(name: str) -> str:
    return hashlib.md5(name.lower().encode()).hexdigest()[:10]


def _parse_json(text: str):
    """Extract JSON from an LLM response that might include markdown fences."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


def _commits_summary(commits: list[dict]) -> str:
    lines: list[str] = []
    for c in commits:
        sha = c["sha"][:7]
        msg = c["commit"]["message"].split("\n")[0]
        date = c["commit"]["committer"]["date"][:10]
        lines.append(f"{date}  {sha}  {msg}")
    return "\n".join(lines)


def _releases_summary(releases: list[dict], tags: list[dict]) -> str:
    lines: list[str] = []
    if releases:
        for r in releases:
            name = r.get("tag_name", r.get("name", ""))
            date = (r.get("published_at") or r.get("created_at", ""))[:10]
            body = (r.get("body") or "")[:200]
            lines.append(f"{date}  {name}  {body}")
    elif tags:
        for t in tags:
            lines.append(f"tag: {t['name']}  sha: {t['commit']['sha'][:7]}")
    return "\n".join(lines) if lines else "No releases or tags found."


# ═══════════════════════════════════════════════════════════════
#  PROMPTS
# ═══════════════════════════════════════════════════════════════

IDENTIFY_FEATURES_SYSTEM = """\
You are an expert software architect performing a deep, granular analysis of a \
GitHub repository. Given the README, file tree, recent commits, and tags/releases, \
identify SPECIFIC, CONCRETE features – NOT broad categories.

CRITICAL – Be SPECIFIC, not general:
- BAD (too broad):  "Authentication" or "API Endpoints" or "Data Management"
- GOOD (specific):  "OAuth2 Google Login", "JWT Token Refresh", "Paginated User Search API", \
"Drag-and-Drop File Upload", "Dark Mode Toggle", "WebSocket Live Notifications"

Rules:
1. Each feature must be a SINGLE, specific capability that a user or developer can \
point to and say "this is one concrete thing the software does".
2. Derive features from ACTUAL code – look at file names, function names, route \
paths, component names, and commit messages for clues.
3. Break broad areas into their individual sub-features. For example, instead of \
"User Management", list "User Registration with Email Verification", \
"Profile Avatar Upload", "Role-Based Access Control", etc.
4. The UNION of all features should cover the ENTIRE project.
5. Give 8-25 features depending on project complexity. More features is better \
than fewer, as long as each one is genuinely distinct.
6. For each feature provide:
   • name  – specific title (2-7 words), descriptive enough to stand alone
   • description – one paragraph explaining EXACTLY what it does, what technology \
or pattern it uses, and how a user interacts with it
   • files – list of key file paths relevant to that feature (up to 10)

Respond ONLY with a JSON array. Example:
[
  {
    "name": "Google OAuth2 Login",
    "description": "Allows users to sign in using their Google account via OAuth2 flow. Uses passport-google-oauth20 strategy, stores refresh tokens in the database, and redirects to the dashboard on success.",
    "files": ["src/auth/google.ts", "src/auth/passport.ts", "src/routes/auth.ts"]
  },
  {
    "name": "CSV Data Export",
    "description": "Generates downloadable CSV files from filtered dashboard data. Uses json2csv library to transform query results and streams the file to the client with proper Content-Disposition headers.",
    "files": ["src/export/csv.ts", "src/routes/export.ts"]
  }
]
"""

VERSION_TIMELINE_SYSTEM = """\
You are a release-notes analyst. Given a feature description, its key files, and a \
chronological list of commits/releases that touched those files, produce a LINEAR \
version timeline for this feature.

For each meaningful version milestone, provide:
  • version – the tag name, or a short commit SHA if no tag exists
  • date – ISO date (YYYY-MM-DD)
  • description – 1-2 sentence summary of what changed for THIS feature in that version

Return ONLY a JSON array sorted oldest → newest. Example:
[
  {"version": "v0.1.0", "date": "2023-01-15", "description": "Initial authentication flow with email/password."},
  {"version": "v0.2.0", "date": "2023-03-10", "description": "Added OAuth2 support for Google and GitHub."}
]
"""


# ═══════════════════════════════════════════════════════════════
#  GRAPH 1 – Analyze Repo  (fetch_context → identify_features)
# ═══════════════════════════════════════════════════════════════


def build_analyze_graph(llm: ChatGroq, gh: GitHubClient) -> StateGraph:
    """Return a compiled LangGraph that analyses a repo and outputs features."""

    # ── Node: fetch_context ──────────────────────────────────

    async def fetch_context(state: AnalyzeState) -> AnalyzeState:
        owner, repo = state["owner"], state["repo"]

        try:
            info = await gh.repo_info(owner, repo)
        except Exception as exc:
            # Surface the real error (403 rate-limit, 404 not found, etc.)
            msg = str(exc)
            if "403" in msg:
                return {**state, "error": f"GitHub API rate limit exceeded. Set GITHUB_TOKEN in your .env file. ({msg})"}
            elif "404" in msg:
                return {**state, "error": f"Repository '{owner}/{repo}' not found. Check the URL and make sure it's a public repo."}
            return {**state, "error": f"Could not access repository: {msg}"}

        readme = await gh.readme(owner, repo)
        default_branch = info.get("default_branch", "main")

        try:
            tree = await gh.tree(owner, repo, sha=default_branch)
        except Exception:
            tree = []

        tree_paths = [n["path"] for n in tree if n["type"] == "blob"]
        commits = await gh.commits(owner, repo, per_page=100)
        tags = await gh.tags(owner, repo)
        releases = await gh.releases(owner, repo)

        ctx: RepoContext = {
            "readme": readme,
            "tree_paths": tree_paths,
            "commits_summary": _commits_summary(commits),
            "releases_summary": _releases_summary(releases, tags),
            "all_commits_raw": commits,
            "releases_raw": releases,
            "tags_raw": tags,
        }

        return {**state, "context": ctx}

    # ── Node: identify_features ──────────────────────────────

    async def identify_features(state: AnalyzeState) -> AnalyzeState:
        if state.get("error"):
            return state

        ctx = state["context"]
        user_prompt = (
            "## README\n"
            f"{ctx['readme'][:8000]}\n\n"
            "## File tree\n"
            f"{chr(10).join(ctx['tree_paths'][:500])}\n\n"
            "## Recent commits (read these carefully for specific features)\n"
            f"{ctx['commits_summary'][:6000]}\n\n"
            "## Releases / tags\n"
            f"{ctx['releases_summary'][:2000]}\n"
        )

        messages = [
            SystemMessage(content=IDENTIFY_FEATURES_SYSTEM),
            HumanMessage(content=user_prompt),
        ]

        response = await llm.ainvoke(messages)
        raw_text = response.content

        try:
            items = _parse_json(raw_text)
        except json.JSONDecodeError:
            return {**state, "error": "Failed to parse AI response", "features": []}

        features = []
        for item in items:
            features.append(
                {
                    "id": _feature_id(item["name"]),
                    "name": item["name"],
                    "description": item["description"],
                    "files": item.get("files", []),
                    "versions": [],
                }
            )

        return {**state, "features": features}

    # ── Conditional edge: check for errors ───────────────────

    def should_continue(state: AnalyzeState) -> str:
        if state.get("error"):
            return END
        return "identify_features"

    # ── Build graph ──────────────────────────────────────────

    graph = StateGraph(AnalyzeState)

    graph.add_node("fetch_context", fetch_context)
    graph.add_node("identify_features", identify_features)

    graph.set_entry_point("fetch_context")
    graph.add_conditional_edges("fetch_context", should_continue)
    graph.add_edge("identify_features", END)

    return graph.compile()


# ═══════════════════════════════════════════════════════════════
#  GRAPH 2 – Feature Timeline  (gather_commits → build_timeline)
# ═══════════════════════════════════════════════════════════════


def build_timeline_graph(llm: ChatGroq, gh: GitHubClient) -> StateGraph:
    """Return a compiled LangGraph that builds a version timeline for one feature."""

    # ── Node: gather_commits ─────────────────────────────────

    async def gather_commits(state: TimelineState) -> TimelineState:
        owner, repo = state["owner"], state["repo"]
        feature = state["feature"]

        all_commits = await gh.commits(owner, repo, per_page=100)
        relevant_lines: list[str] = []

        for c in all_commits:
            try:
                detail = await gh.commit_detail(owner, repo, c["sha"])
            except Exception:
                continue
            changed_files = [f["filename"] for f in detail.get("files", [])]
            if any(
                any(feat_file in cf for cf in changed_files)
                for feat_file in feature.get("files", [])
            ):
                sha = c["sha"][:7]
                msg = c["commit"]["message"].split("\n")[0]
                date = c["commit"]["committer"]["date"][:10]
                relevant_lines.append(f"{date}  {sha}  {msg}")

        if not relevant_lines:
            relevant_lines = [
                f"{c['commit']['committer']['date'][:10]}  {c['sha'][:7]}  {c['commit']['message'].split(chr(10))[0]}"
                for c in all_commits[:30]
            ]

        # Oldest first
        relevant_lines.reverse()

        tags = await gh.tags(owner, repo)
        releases = await gh.releases(owner, repo)
        r_summary = _releases_summary(releases, tags)

        return {
            **state,
            "commits_for_feature": "\n".join(relevant_lines),
            "releases_summary": r_summary,
        }

    # ── Node: build_timeline ─────────────────────────────────

    async def build_timeline(state: TimelineState) -> TimelineState:
        feature = state["feature"]

        user_prompt = (
            f"## Feature: {feature['name']}\n"
            f"{feature['description']}\n\n"
            f"Key files: {', '.join(feature.get('files', []))}\n\n"
            "## Commits touching these files (oldest → newest)\n"
            f"{state['commits_for_feature'][:6000]}\n\n"
            "## Releases / tags\n"
            f"{state['releases_summary'][:2000]}\n"
        )

        messages = [
            SystemMessage(content=VERSION_TIMELINE_SYSTEM),
            HumanMessage(content=user_prompt),
        ]

        response = await llm.ainvoke(messages)
        raw_text = response.content

        try:
            items = _parse_json(raw_text)
        except json.JSONDecodeError:
            return {**state, "versions": [], "error": "Failed to parse timeline"}

        return {**state, "versions": items}

    # ── Build graph ──────────────────────────────────────────

    graph = StateGraph(TimelineState)

    graph.add_node("gather_commits", gather_commits)
    graph.add_node("build_timeline", build_timeline)

    graph.set_entry_point("gather_commits")
    graph.add_edge("gather_commits", "build_timeline")
    graph.add_edge("build_timeline", END)

    return graph.compile()


# ═══════════════════════════════════════════════════════════════
#  GRAPH 3 – Feature Evolution  (fetch_commit_details → analyze_evolution)
#
#  Takes the structured output of Agent 1 as context and explains
#  how a feature evolved commit-by-commit with file-level changes.
# ═══════════════════════════════════════════════════════════════

EVOLUTION_SYSTEM = """\
You are a senior code reviewer. You receive:
1. A feature's structured context:  name, description, and key files.
2. A batch of commits (with diffs/patches) that touched those files.

For EACH commit, write a concise "evolution_summary" (2-4 sentences) that explains:
  • What changed in the code (referencing specific files).
  • How this commit advanced or evolved the feature.
  • Whether it was a new capability, bug-fix, refactor, or performance improvement.

Return ONLY a JSON array in the SAME order as the input commits. Example:
[
  {
    "sha": "abc1234",
    "evolution_summary": "Added the login form component in src/auth/Login.tsx ..."
  }
]
"""


def build_evolution_graph(llm: ChatGroq, gh: GitHubClient) -> StateGraph:
    """Return a compiled LangGraph that explains feature evolution per commit."""

    # ── Node: fetch_commit_details ───────────────────────────

    async def fetch_commit_details(state: EvolutionState) -> EvolutionState:
        owner, repo = state["owner"], state["repo"]
        feature = state["feature"]
        feature_files = feature.get("files", [])

        all_commits = await gh.commits(owner, repo, per_page=100)
        relevant: list[dict] = []

        for c in all_commits:
            try:
                detail = await gh.commit_detail(owner, repo, c["sha"])
            except Exception:
                continue

            changed = detail.get("files", [])
            changed_names = [f["filename"] for f in changed]

            # Keep commits that touch any of the feature's files
            if any(
                any(feat_file in cf for cf in changed_names)
                for feat_file in feature_files
            ):
                # Only keep files relevant to this feature + truncate patches
                relevant_files = []
                total_additions = 0
                total_deletions = 0
                for f in changed:
                    if any(feat_file in f["filename"] for feat_file in feature_files):
                        adds = f.get("additions", 0)
                        dels = f.get("deletions", 0)
                        total_additions += adds
                        total_deletions += dels
                        relevant_files.append({
                            "filename": f["filename"],
                            "status": f.get("status", "modified"),
                            "additions": adds,
                            "deletions": dels,
                            "patch": (f.get("patch") or "")[:500],
                        })

                relevant.append({
                    "sha": c["sha"][:7],
                    "date": c["commit"]["committer"]["date"][:10],
                    "message": c["commit"]["message"].split("\n")[0],
                    "author": c["commit"]["author"]["name"],
                    "files": relevant_files,
                    "total_additions": total_additions,
                    "total_deletions": total_deletions,
                })

        if not relevant:
            return {**state, "raw_commits": [], "error": "No commits found touching this feature's files."}

        # Oldest first
        relevant.reverse()

        return {**state, "raw_commits": relevant}

    # ── Node: analyze_evolution ──────────────────────────────

    async def analyze_evolution(state: EvolutionState) -> EvolutionState:
        if state.get("error"):
            return state

        feature = state["feature"]
        raw_commits = state["raw_commits"]

        # Build a commit list for the LLM (batch to stay within context)
        commits_text_parts: list[str] = []
        for c in raw_commits[:40]:  # cap at 40 most relevant
            files_desc = "\n".join(
                f"  [{f['status']}] {f['filename']}\n    {f['patch'][:300]}"
                for f in c["files"]
            )
            commits_text_parts.append(
                f"### Commit {c['sha']}  ({c['date']})  by {c['author']}\n"
                f"Message: {c['message']}\n"
                f"Files:\n{files_desc}"
            )

        user_prompt = (
            "## Feature Context\n"
            f"**Name:** {feature['name']}\n"
            f"**Description:** {feature['description']}\n"
            f"**Key files:** {', '.join(feature.get('files', []))}\n\n"
            "## Commits (oldest → newest)\n\n"
            + "\n\n".join(commits_text_parts)
        )

        messages = [
            SystemMessage(content=EVOLUTION_SYSTEM),
            HumanMessage(content=user_prompt),
        ]

        response = await llm.ainvoke(messages)

        try:
            summaries = _parse_json(response.content)
        except json.JSONDecodeError:
            return {**state, "evolution": [], "error": "Failed to parse evolution analysis"}

        # Merge AI summaries back into the commit data
        summary_map = {s["sha"]: s["evolution_summary"] for s in summaries}

        evolution: list[dict] = []
        for c in raw_commits[:40]:
            evolution.append({
                "sha": c["sha"],
                "date": c["date"],
                "message": c["message"],
                "author": c["author"],
                "files_changed": c["files"],
                "total_additions": c.get("total_additions", 0),
                "total_deletions": c.get("total_deletions", 0),
                "evolution_summary": summary_map.get(c["sha"], "No analysis available."),
            })

        return {**state, "evolution": evolution}

    # ── Build graph ──────────────────────────────────────────

    graph = StateGraph(EvolutionState)

    graph.add_node("fetch_commit_details", fetch_commit_details)
    graph.add_node("analyze_evolution", analyze_evolution)

    graph.set_entry_point("fetch_commit_details")
    graph.add_edge("fetch_commit_details", "analyze_evolution")
    graph.add_edge("analyze_evolution", END)

    return graph.compile()


# ═══════════════════════════════════════════════════════════════
#  Convenience wrapper
# ═══════════════════════════════════════════════════════════════


class RepoAnalyzerAgent:
    """High-level wrapper that exposes the three compiled LangGraph agents."""

    def __init__(self, api_key: str, gh: GitHubClient, model: str = "llama-3.3-70b-versatile"):
        self.llm = ChatGroq(model=model, temperature=0.2, api_key=api_key)
        self.analyze_graph = build_analyze_graph(self.llm, gh)
        self.timeline_graph = build_timeline_graph(self.llm, gh)
        self.evolution_graph = build_evolution_graph(self.llm, gh)

    async def analyze_repo(self, owner: str, repo: str) -> list[Feature]:
        """Run the analyze graph and return Feature objects."""
        result = await self.analyze_graph.ainvoke(
            {"owner": owner, "repo": repo}
        )

        if result.get("error"):
            raise RuntimeError(result["error"])

        return [Feature(**f) for f in result.get("features", [])]

    async def feature_timeline(
        self, owner: str, repo: str, feature: Feature
    ) -> list[VersionEntry]:
        """Run the timeline graph and return VersionEntry objects."""
        result = await self.timeline_graph.ainvoke(
            {
                "owner": owner,
                "repo": repo,
                "feature": feature.model_dump(),
            }
        )

        if result.get("error"):
            raise RuntimeError(result["error"])

        return [VersionEntry(**v) for v in result.get("versions", [])]

    async def feature_evolution(
        self, owner: str, repo: str, feature: Feature
    ) -> list[dict]:
        """Run the evolution graph – returns commit-level feature evolution."""
        result = await self.evolution_graph.ainvoke(
            {
                "owner": owner,
                "repo": repo,
                "feature": feature.model_dump(),
            }
        )

        if result.get("error"):
            raise RuntimeError(result["error"])

        return result.get("evolution", [])
