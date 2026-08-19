"""
fetch_commits.py

Pulls recent commits (with diffs) from a GitHub repo, for feeding into
the "significance scoring" + "draft generation" steps later.

Usage:
    python fetch_commits.py <owner>/<repo> --since 2026-08-01 --out commits.json

Auth (optional but recommended — raises rate limit from 60/hr to 5000/hr):
    export GITHUB_TOKEN=ghp_xxxxxxxx
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import requests

GITHUB_API = "https://api.github.com"


def get_headers():
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_commits(repo: str, since: str | None, per_page: int = 30):
    """Fetch commit list (metadata only) from the default branch."""
    url = f"{GITHUB_API}/repos/{repo}/commits"
    params = {"per_page": per_page}
    if since:
        # GitHub expects ISO 8601
        since_dt = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        params["since"] = since_dt.isoformat()

    resp = requests.get(url, headers=get_headers(), params=params)
    resp.raise_for_status()
    return resp.json()


def fetch_commit_detail(repo: str, sha: str):
    """Fetch a single commit's full detail, including file diffs (patches)."""
    url = f"{GITHUB_API}/repos/{repo}/commits/{sha}"
    resp = requests.get(url, headers=get_headers())
    resp.raise_for_status()
    return resp.json()


def summarize_commit(detail: dict) -> dict:
    """Trim a full commit-detail response down to what the scoring/draft
    steps actually need, and keep diffs small enough for an LLM prompt."""
    files = detail.get("files", [])
    file_summaries = []
    for f in files:
        patch = f.get("patch", "")  # not all files have a patch (e.g. binaries)
        file_summaries.append(
            {
                "filename": f.get("filename"),
                "status": f.get("status"),
                "additions": f.get("additions"),
                "deletions": f.get("deletions"),
                # cap patch length so one huge file doesn't blow the prompt budget
                "patch_excerpt": patch[:2000] if patch else None,
            }
        )

    return {
        "sha": detail["sha"][:7],
        "message": detail["commit"]["message"],
        "author": detail["commit"]["author"]["name"],
        "date": detail["commit"]["author"]["date"],
        "url": detail["html_url"],
        "stats": detail.get("stats", {}),
        "files": file_summaries,
    }


def main():
    parser = argparse.ArgumentParser(description="Pull recent commits from a GitHub repo")
    parser.add_argument("repo", help="muskaaanraj/Chat_with_web")
    parser.add_argument("--since", help="YYYY-MM-DD, only commits after this date")
    parser.add_argument("--limit", type=int, default=30, help="max commits to pull")
    parser.add_argument("--out", default="commits.json", help="output JSON file")
    args = parser.parse_args()

    print(f"Fetching commit list for {args.repo}...", file=sys.stderr)
    try:
        commits = fetch_commits(args.repo, args.since, per_page=args.limit)
    except requests.HTTPError as e:
        print(f"Error fetching commits: {e}", file=sys.stderr)
        sys.exit(1)

    if not commits:
        print("No commits found for that range.", file=sys.stderr)
        return

    print(f"Found {len(commits)} commits. Fetching diffs...", file=sys.stderr)
    results = []
    for c in commits:
        sha = c["sha"]
        try:
            detail = fetch_commit_detail(args.repo, sha)
            results.append(summarize_commit(detail))
            print(f"  + {sha[:7]}  {c['commit']['message'].splitlines()[0][:60]}", file=sys.stderr)
        except requests.HTTPError as e:
            print(f"  ! failed to fetch {sha[:7]}: {e}", file=sys.stderr)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved {len(results)} commits to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()