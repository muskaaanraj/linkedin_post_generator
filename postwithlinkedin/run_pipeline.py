"""
run_pipeline.py

Chains fetch_commits.py -> score_commits.py -> draft_post.py into one run.
Used both as a CLI script and imported by streamlit_app.py.

CLI usage:
    python run_pipeline.py muskaaanraj/Chat_with_web --since 2026-08-01 \\
        --project-name "Chat with this Page"

Auth: GITHUB_TOKEN and GROQ_API_KEY in your .env file.
"""

import argparse
import json
import sys

from dotenv import load_dotenv
from groq import Groq

from fetch import fetch_commits, fetch_commit_detail, summarize_commit
from score_commits import score_commit
from draft_post import draft_post

load_dotenv()


def run_pipeline(
    repo: str,
    since: str | None = None,
    limit: int = 30,
    project_name: str = "this project",
    repo_url_override: str | None = None,
    progress_callback=None,
):
    """
    Runs fetch -> score -> draft for a repo and returns a dict with all
    intermediate results, so a UI can show progress/partial results.

    progress_callback(stage: str, message: str) is called at each step if provided,
    so a UI (like Streamlit) can show live status.
    """
    def report(stage, message):
        if progress_callback:
            progress_callback(stage, message)

    client = Groq()

    # --- Stage 1: fetch ---
    report("fetch", f"Fetching commit list for {repo}...")
    raw_commits = fetch_commits(repo, since, per_page=limit)
    if not raw_commits:
        report("fetch", "No commits found for that range.")
        return {"commits": [], "scored": [], "drafts": []}

    commits = []
    for c in raw_commits:
        sha = c["sha"]
        try:
            detail = fetch_commit_detail(repo, sha)
            commits.append(summarize_commit(detail))
            report("fetch", f"Fetched {sha[:7]}: {c['commit']['message'].splitlines()[0][:60]}")
        except Exception as e:
            report("fetch", f"Failed to fetch {sha[:7]}: {e}")

    # --- Stage 2: score ---
    report("score", f"Scoring {len(commits)} commit(s)...")
    scored = []
    for c in commits:
        try:
            result = score_commit(client, c)
        except Exception as e:
            result = {"post_worthy": False, "score": 0, "reason": str(e), "angle": None}
        merged = {**c, **result}
        scored.append(merged)
        flag = "post-worthy" if result.get("post_worthy") else "skip"
        report("score", f"{c['sha'][:7]} -> {flag} (score={result.get('score')})")

    # --- Stage 3: draft ---
    worthy = [c for c in scored if c.get("post_worthy")]
    report("draft", f"Drafting posts for {len(worthy)} post-worthy commit(s)...")
    drafts = []
    for c in worthy:
        repo_url = repo_url_override or c.get("url", "")
        try:
            text = draft_post(client, c, project_name, repo_url)
            drafts.append({"sha": c["sha"], "commit_message": c["message"], "draft": text})
            report("draft", f"Drafted post for {c['sha'][:7]}")
        except Exception as e:
            report("draft", f"Failed to draft for {c['sha'][:7]}: {e}")

    return {"commits": commits, "scored": scored, "drafts": drafts}


def main():
    parser = argparse.ArgumentParser(description="Run the full commit -> score -> draft pipeline")
    parser.add_argument("repo", help="owner/repo")
    parser.add_argument("--since", help="YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--project-name", default="this project")
    parser.add_argument("--repo-url", default=None)
    parser.add_argument("--out", default="pipeline_results.json")
    args = parser.parse_args()

    def cli_progress(stage, message):
        print(f"[{stage}] {message}", file=sys.stderr)

    results = run_pipeline(
        repo=args.repo,
        since=args.since,
        limit=args.limit,
        project_name=args.project_name,
        repo_url_override=args.repo_url,
        progress_callback=cli_progress,
    )

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved full results to {args.out}", file=sys.stderr)
    print(f"{len(results['drafts'])} draft(s) generated.\n", file=sys.stderr)
    for d in results["drafts"]:
        print("=" * 60)
        print(d["draft"])
        print("=" * 60)


if __name__ == "__main__":
    main()