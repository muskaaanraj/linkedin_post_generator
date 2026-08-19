Shipping a project and actually *posting about it* are two different habits. This tool closes that gap: point it at a repo, and it pulls recent commits, decides which ones are actually worth talking about (skips README typos and dependency bumps), and drafts a post for the ones that matter — styled after your own past LinkedIn posts, not a generic template.

## How it works

The pipeline runs in three stages, chained together by `run_pipeline.py`:

```
GitHub API (commits + diffs)
        │
        ▼
  fetch_commits.py   →  pulls recent commits and their diffs for a repo
        │
        ▼
  score_commits.py   →  Groq/Llama scores each commit: post-worthy or skip?
        │                (filters out routine work — formatting, typos, tiny tweaks)
        ▼
  draft_post.py       →  drafts a LinkedIn post for each post-worthy commit,
        │                 using past posts as style examples (few-shot)
        ▼
  streamlit_app.py    →  review UI — run the pipeline, see the scoring
                          reasoning, edit drafts, copy to LinkedIn
```

Each stage is also a standalone script you can run on its own from the command line.

## Tech stack

- **Python** — `requests` for the GitHub API, `python-dotenv` for config
- **Groq API** (`openai/gpt-oss-20b`) — free-tier LLM calls for scoring and drafting
- **Streamlit** — local review UI

## Setup

```bash
pip install requests groq python-dotenv streamlit
```

Create a `.env` file in the project root:

```
GITHUB_TOKEN=ghp_xxxxxxxx
GROQ_API_KEY=gsk_xxxxxxxx
```

- GitHub token: [github.com/settings/tokens](https://github.com/settings/tokens) — `repo` or `public_repo` scope
- Groq key (free): [console.groq.com/keys](https://console.groq.com/keys)

## Usage

**Review UI (recommended):**

```bash
streamlit run streamlit_app.py
```

Enter a repo (`owner/repo`), set how many recent commits to check, and run. Post-worthy drafts land in editable text boxes — tweak and copy to LinkedIn.

**Command line, full pipeline:**

```bash
python run_pipeline.py owner/repo --project-name "My Project" --out pipeline_results.json
```

**Command line, one stage at a time:**

```bash
python fetch_commits.py owner/repo --since 2026-08-01 --out commits.json
python score_commits.py commits.json --out scored_commits.json
python draft_post.py scored_commits.json --project-name "My Project" --out drafts.json
```

## Customizing your voice

`draft_post.py` includes a `STYLE_EXAMPLES` list near the top — paste in a few of your own past LinkedIn posts there. The more examples, the more consistently the model matches your actual tone and structure instead of writing something generic.

## Notes

- The GitHub API is rate-limited to 60 requests/hour without a token, 5,000/hour with one — set `GITHUB_TOKEN` to avoid 403s.
- `openai/gpt-oss-20b` occasionally returns an empty completion; both `score_commits.py` and `draft_post.py` retry automatically before giving up.
- Nothing here auto-posts to LinkedIn — every draft is meant to be reviewed and edited before you post it yourself.

## Possible next steps

- Multi-repo support (loop through all your repos in one run)
- Memory of past posts, so it doesn't repeat phrasing or re-post the same project twice
- One-click "copy to clipboard" once Streamlit supports it natively
