"""
draft_post.py

Reads scored_commits.json (output of score_commits.py), takes the
post-worthy commits, and drafts a LinkedIn post for each — in your
voice, using STYLE_EXAMPLES as few-shot references.

Usage:
    python draft_post.py scored_commits.json --out drafts.json
    python draft_post.py scored_commits.json --repo-url https://github.com/muskaaanraj/Chat_with_web

Auth (free — get a key at https://console.groq.com/keys):
    Add GROQ_API_KEY=gsk_xxxx to your .env file
"""

import argparse
import json
import sys

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

MODEL = "openai/gpt-oss-20b"

# --- Add more of your past posts here as you go — more examples = better style match ---
STYLE_EXAMPLES = [
    """I have always been a person who prefers movies over books. So when there's a conversation about books, I never have anything to recommend. Instead of just feeling left out of those chats, I decided to build something about it — a "Semantic Book Recommendation System."

Here's how it works: you type in what you're in the mood for ("a story about revenge" or "something uplifting"), and instead of just matching keywords, it actually understands the meaning behind your request and recommends books that fit — even filtering by category and emotional tone (happy, sad, suspenseful, etc.).

What went into it:
 → Vector search using LangChain + HuggingFace embeddings to understand semantic meaning, not just keywords
 → A text classification model to tag books by category
 → Sentiment/emotion analysis to score books by emotional tone
 → An interactive Gradio dashboard to tie it all together

Honestly, the most fun part wasn't the "AI" — it was watching it recommend books that actually made sense for a mood, not just a genre. I still haven't read most of them. But now at least I have something to say the next time someone asks "any good book recommendations?"

Check out the code of the project here: [link]

#RAG #LangChain #GenerativeAI #LLM #Python #MachineLearning #SemanticSearch #BuildInPublic""",
    """Ever found yourself scrolling through a long article just to pull a single paragraph out, then copy-paste it into a note app to ask a follow-up question? I did, and I thought, "Why not ask the page itself?"

So I built a Chrome extension that turns any tab into a chat window, powered by LangChain and a Groq LLM. Just click the icon, type your question, and the extension pulls the relevant text from the page, sends it to the model, and returns an answer—all in the same tab.

What went into it:
 → Chrome extension manifest, popup.html, popup.css, and popup.js for the UI
 → A lightweight Flask app (app.py) that proxies requests to LangChain
 → LangChain wrappers to chunk page text and generate prompts
 → Groq LLM integration for fast, cost-effective inference
 → requirements.txt to keep the environment reproducible

Honestly, the most fun part was watching the model actually understand context from a random news article. I still have to tweak the tokenizer for very long pages, but it's a working prototype that feels surprisingly useful.

Check out the commit that ships the extension here: [link]

#ChromeExtension #LangChain #Groq #LLM #Python #AI #BuildInPublic""",
]

DRAFT_PROMPT = """You are ghostwriting a LinkedIn post for a software engineer, in \
their own voice. Study the style examples below closely — tone, structure, \
sentence rhythm, how they open with a small personal/relatable hook, how they \
list technical components with arrow bullets ("→"), how they end with an \
honest or slightly self-deprecating aside before the link and hashtags.

--- STYLE EXAMPLES (this person's past posts) ---
{style_examples}
--- END STYLE EXAMPLES ---

Now write a NEW LinkedIn post about this project update. Match the voice and \
structure above closely, but do not reuse specific phrases from the examples \
verbatim — write fresh content for this project.

Project: {project_name}
What was built (commit message): {commit_message}
Suggested angle: {angle}
Technical details to weave in naturally (don't list every file, pick what's interesting): {tech_summary}
Repo link: {repo_url}

Write ONLY the post text (including relevant hashtags at the end, 6-8 of them, \
matching the style of the examples). No preamble, no explanation, no markdown \
fences — just the post as it should be pasted into LinkedIn."""


def summarize_tech(commit: dict) -> str:
    """Pull a short, human-readable list of what changed technically."""
    files = commit.get("files", [])
    names = [f["filename"] for f in files]
    return ", ".join(names[:8]) + (" and more" if len(names) > 8 else "")


def draft_post(client: Groq, commit: dict, project_name: str, repo_url: str, retries: int = 2) -> str:
    prompt = DRAFT_PROMPT.format(
        style_examples="\n\n---\n\n".join(STYLE_EXAMPLES),
        project_name=project_name,
        commit_message=commit["message"],
        angle=commit.get("angle") or "share this project update",
        tech_summary=summarize_tech(commit),
        repo_url=repo_url,
    )

    for attempt in range(retries + 1):
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=700,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
        )

        text = (response.choices[0].message.content or "").strip()
        # strip stray markdown fences some models add despite instructions
        text = text.replace("```markdown", "").replace("```", "").strip()

        if text:
            return text

        if attempt < retries:
            continue

    return (
        "[Draft generation returned empty — this can happen with gpt-oss-20b "
        "occasionally. Try re-running the pipeline for this commit.]"
    )


def main():
    parser = argparse.ArgumentParser(description="Draft LinkedIn posts from post-worthy commits")
    parser.add_argument("input", help="path to scored_commits.json from score_commits.py")
    parser.add_argument("--out", default="drafts.json")
    parser.add_argument("--project-name", default=None, help="override project name shown in the prompt")
    parser.add_argument("--repo-url", default=None, help="repo URL to include in the post")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        commits = json.load(f)

    worthy = [c for c in commits if c.get("post_worthy")]
    if not worthy:
        print("No post-worthy commits found in input file.", file=sys.stderr)
        return

    client = Groq()

    drafts = []
    for c in worthy:
        repo_url = args.repo_url or c.get("url", "")
        project_name = args.project_name or "this project"
        print(f"Drafting post for {c['sha']}  {c['message'].splitlines()[0][:60]}...", file=sys.stderr)

        try:
            text = draft_post(client, c, project_name, repo_url)
        except Exception as e:
            print(f"  ! error drafting for {c['sha']}: {e}", file=sys.stderr)
            continue

        drafts.append({"sha": c["sha"], "commit_message": c["message"], "draft": text})
        print("  done.\n", file=sys.stderr)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(drafts, f, indent=2)

    print(f"\nSaved {len(drafts)} draft(s) to {args.out}", file=sys.stderr)
    for d in drafts:
        print("\n" + "=" * 60)
        print(d["draft"])
        print("=" * 60)


if __name__ == "__main__":
    main()