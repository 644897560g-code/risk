# One-off Scripts

This directory contains historical data-processing, debugging, and artifact-generation scripts.
They are not imported by the current backend or FeatureOrchestrator runtime.

Typical contents:
- app-list extraction and analysis scripts
- historical LLM app-classification batch scripts
- FDC/data-structure inspection helpers
- report/design artifact generators from earlier development phases

Run these from the repository root, for example:

```bash
PYTHONPATH=. python scripts/one_off/analyze_all_apps.py
```

Before reusing one of these scripts, check whether the current runtime has replaced it with:
- `backend/` API routes and services
- `agents/feature_orchestrator.py`
- `agents/feature_development_agent.py`
- `agents/feature_mass_producer.py`
- `data/batch_classify_new_apps.py`

