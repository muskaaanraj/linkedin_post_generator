"""
streamlit_app.py

Local review UI for the commit -> score -> draft pipeline.
Run with:  streamlit run streamlit_app.py
"""

import streamlit as st

from run_pipeline import run_pipeline

st.set_page_config(page_title="Commit-to-Post", page_icon="📝", layout="centered")

st.title("📝 Commit → LinkedIn Post")
st.caption("Pulls recent commits, scores them for post-worthiness, and drafts a post for you to review.")

with st.form("pipeline_form"):
    repo = st.text_input("Repo (owner/repo)", placeholder="muskaaanraj/Chat_with_web")
    col1, col2 = st.columns(2)
    with col1:
        since = st.text_input("Since (YYYY-MM-DD, optional)", placeholder="2026-08-01")
    with col2:
        limit = st.number_input("Max commits to check", min_value=1, max_value=100, value=15)
    project_name = st.text_input("Project name (for the post prompt)", placeholder="Chat with this Page")
    submitted = st.form_submit_button("Run pipeline", use_container_width=True)

if submitted:
    if not repo:
        st.error("Enter a repo first.")
        st.stop()

    status_box = st.status("Running pipeline...", expanded=True)

    def on_progress(stage, message):
        status_box.write(f"**[{stage}]** {message}")

    try:
        results = run_pipeline(
            repo=repo,
            since=since or None,
            limit=limit,
            project_name=project_name or "this project",
            progress_callback=on_progress,
        )
        status_box.update(label="Pipeline complete", state="complete")
    except Exception as e:
        status_box.update(label="Pipeline failed", state="error")
        st.error(f"Error: {e}")
        st.stop()

    st.session_state["results"] = results

# --- Show results if we have them (persists across reruns via session_state) ---
if "results" in st.session_state:
    results = st.session_state["results"]
    scored = results.get("scored", [])
    drafts = results.get("drafts", [])

    st.divider()
    st.subheader(f"Scored commits ({len(scored)})")
    for c in scored:
        worthy = c.get("post_worthy")
        icon = "✅" if worthy else "⏭️"
        with st.expander(f"{icon} {c['sha'][:7]} — {c['message'].splitlines()[0][:70]} (score: {c.get('score')})"):
            st.write(c.get("reason", ""))
            if c.get("angle"):
                st.caption(f"Angle: {c['angle']}")

    st.divider()
    st.subheader(f"Drafts to review ({len(drafts)})")

    if not drafts:
        st.info("No post-worthy commits this run — nothing to draft.")

    for i, d in enumerate(drafts):
        st.markdown(f"**{d['sha'][:7]} — {d['commit_message'].splitlines()[0][:70]}**")
        edited = st.text_area(
            "Draft (edit freely before copying to LinkedIn)",
            value=d["draft"],
            height=300,
            key=f"draft_{i}",
        )
        st.caption("Select the text above and copy it — Streamlit doesn't support a native copy button yet.")
        st.divider()