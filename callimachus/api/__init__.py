"""callimachus HTTP API.

FastAPI app wrapping the engine + project + pack + approval packages, serving
a React frontend (``frontend/``). Engine code is sync; long-running operations
run via BackgroundTasks against a per-process JobRegistry (callimachus.api.jobs).

Launch:
    uvicorn callimachus.api.main:app --reload --port 8000
"""
