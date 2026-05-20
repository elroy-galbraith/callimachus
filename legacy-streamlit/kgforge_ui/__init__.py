"""Streamlit UI for kgforge.

Entry point: kgforge/ui/app.py. Run with:

    streamlit run kgforge/ui/app.py

Multipage layout (Streamlit's pages/ convention):
    1_Projects   — list, create, open a project
    2_Dashboard  — upload, extract, review/approve
    3_Schema     — view the active pack's classes/properties/prompt
    4_Query      — competency questions + NL ask
    5_Settings   — Anthropic API key, model overrides

State: st.session_state["project_name"] holds the active project; pages
that need it call ui_helpers.require_project() at the top.
"""
