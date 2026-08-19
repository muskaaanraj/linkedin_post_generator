"""
score_commits.py

Reads commits.json (output of fetch_commits.py) and uses Groq (free tier,
Llama 3.1) to score each commit: is this significant enough to draft a
LinkedIn post about?

Usage:
    python score_commits.py commits.json --out scored_commits.json

Auth (free — get a key at https://console.groq.com/keys):
    export GROQ_API_KEY=gsk_xxxxxxxx
"""

import argparse
import json
import sys

from dotenv import load_dotenv
from groq import Groq

load_dotenv()  # reads .env in the project root into os.environ

MODEL = "openai/gpt-oss-20b"

SCORING_PROMPT = """You are helping a software engineer decide which of their \
GitHub commits are worth turning into a LinkedIn post about their work.

Score this commit on whether it represents meaningful, postable progress \
(a new feature, a working end-to-end pipeline, a solved hard problem, a \
shipped project) versus routine work (typo fixes, formatting, dependency \
bumps, tiny tweaks, WIP commits, merge commits).

Commit message: {message}
Files changed: {file_count}
Lines: +{additions} / -{deletions}

Diff excerpt (may be truncated):
{diff_excerpt}

Respond with ONLY valid JSON, no other text, no markdown fences:
{{
  "post_worthy": true or false,
  "score": 1-5 (5 = definitely post about this, 1 = definitely skip),
  "reason": "one sentence explaining the score",
  "angle": "if post_worthy, a one-line suggested angle for the post (e.g. \
'shipped a working RAG pipeline for X'); otherwise null"
}}"""


def build_diff_excerpt(commit: dict, max_chars: int = 3000) -> str:
    """Concatenate per-file patches into one excerpt, capped in length."""
    parts = []
    for f in commit.get("files", []):
        if f.get("patch_excerpt"):
            parts.append(f"--- {f['filename']} ({f['status']}) ---\n{f['patch_excerpt']}")
    joined = "\n\n".join(parts)
    return joined[:max_chars] if joined else "(no diff available)"


def score_commit(client: Groq, commit: dict, retries: int = 1) -> dict:
    stats = commit.get("stats", {})
    prompt = SCORING_PROMPT.format(
        message=commit["message"],
        file_count=len(commit.get("files", [])),
        additions=stats.get("additions", 0),
        deletions=stats.get("deletions", 0),
        diff_excerpt=build_diff_excerpt(commit),
    )

    for attempt in range(retries + 1):
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=400,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = (response.choices[0].message.content or "").strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        if raw and not raw.startswith("{"):
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                raw = raw[start : end + 1]

        if not raw:
            if attempt < retries:
                continue
            return {
                "post_worthy": False,
                "score": 0,
                "reason": "Model returned an empty response after retry.",
                "angle": None,
            }

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            if attempt < retries:
                continue
            return {
                "post_worthy": False,
                "score": 0,
                "reason": f"Failed to parse model response: {raw[:200]}",
                "angle": None,
            }


def main():
    parser = argparse.ArgumentParser(description="Score commits for LinkedIn post-worthiness")
    parser.add_argument("input", help="path to commits.json from fetch_commits.py")
    parser.add_argument("--out", default="scored_commits.json")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        commits = json.load(f)

    if not commits:
        print("No commits found in input file.", file=sys.stderr)
        return

    client = Groq()  # reads GROQ_API_KEY from env

    results = []
    for c in commits:
        print(f"Scoring {c['sha']}  {c['message'].splitlines()[0][:60]}...", file=sys.stderr)
        try:
            score = score_commit(client, c)
        except Exception as e:
            print(f"  ! error scoring {c['sha']}: {e}", file=sys.stderr)
            score = {"post_worthy": False, "score": 0, "reason": str(e), "angle": None}

        merged = {**c, **score}
        results.append(merged)
        flag = "✓ POST-WORTHY" if score.get("post_worthy") else "  skip"
        print(f"  {flag} (score={score.get('score')}) — {score.get('reason', '')[:80]}", file=sys.stderr)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    worthy_count = sum(1 for r in results if r.get("post_worthy"))
    print(f"\nDone. {worthy_count}/{len(results)} commits flagged as post-worthy.", file=sys.stderr)
    print(f"Saved to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()