# Legacy Streamlit UI

This is the original Streamlit app that shipped with the kgforge prototype.
It has been **superseded by the React + FastAPI frontend** under `../frontend/`
and `../kgforge/api/`.

The Streamlit code is kept here for reference and as a fallback during the
cutover. It is not actively maintained — any new feature work lands in the
React frontend.

## Launch

From the repo root:

```powershell
pip install -e .[legacy]
streamlit run legacy-streamlit/kgforge_ui/app.py
```

The app auto-discovers the seven pages under `kgforge_ui/pages/`. The active
project is tracked in Streamlit session state and lasts as long as the browser
tab.

## Layout

```
legacy-streamlit/
└── kgforge_ui/
    ├── app.py                  # landing page + active-project picker
    ├── helpers.py              # session-state helpers, sys.path bootstrap
    └── pages/
        ├── 1_Projects.py
        ├── 2_Dashboard.py
        ├── 3_Schema.py
        ├── 4_Query.py
        ├── 5_Settings.py
        ├── 6_Help.py
        └── 7_Proposals.py
```

## Differences vs the React frontend

- **No job orchestration.** Long-running operations (extractor, consolidator,
  NL ask) block the main thread; the UI freezes until they return. The React
  frontend uses `BackgroundTasks` + SSE so the UI stays responsive.
- **Single process.** All UI state lives in `st.session_state` — no API
  surface, no openapi.json, no codegen.
- **Process-wide API key override.** The Settings page can override
  `ANTHROPIC_API_KEY` for the entire Python process. The React frontend
  intentionally does not expose this over HTTP.
- **No graph mini-diagrams on the Proposals page across multiple workers.**
  Streamlit's `st.graphviz_chart` ships fine; the React frontend uses
  `@viz-js/viz` (WASM) for the same effect.

## Removal

This folder will be deleted once the React frontend has been in production
for a release cycle without regressions. To remove now:

```powershell
git rm -r legacy-streamlit/
# then remove the [project.optional-dependencies].legacy block from pyproject.toml
```
