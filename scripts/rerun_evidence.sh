#!/bin/sh
# Regenerate every evidence file (so git_commit is the committed hash). Does NOT re-run the one-shot test scores
# (task_a_test.json, task_b_test.json). Order matters: cv-a, cv-b before final models are read by predict.
set -e
python scripts/evaluate.py
python scripts/train.py cv-a
python scripts/train.py cv-b
python scripts/failure_cases.py
python scripts/drift.py
python scripts/fragility.py
python scripts/conformal.py
python scripts/decision.py
python scripts/predict.py
python scripts/demo.py
python scripts/insights.py
