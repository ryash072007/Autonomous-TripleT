#!/bin/sh
# Regenerate every evidence file so git_commit is the committed hash. Works on a fresh clone (Git Bash: sh scripts/rerun_evidence.sh).
# Does NOT run fetch_labels / score_test_b / test_breakdown (one-shot post-freeze steps) or touch task_*_test*.json.
set -e
PY=${PYTHON:-python}
M=artifacts/models
$PY scripts/evaluate.py
$PY scripts/train.py cv-a
$PY scripts/train.py cv-b
# (a) train final models only when missing (artifacts/models is gitignored). train.py final also refuses to replace
# models that disagree with a frozen model_card.json and never rewrites a frozen card.
if [ ! -f $M/task_a.joblib ] || [ ! -f $M/task_b.joblib ]; then
  $PY scripts/train.py final
fi
$PY scripts/failure_cases.py
$PY scripts/drift.py
$PY scripts/fragility.py
$PY scripts/conformal.py
$PY scripts/decision.py
# (c) freeze only if the card is not frozen yet
if ! $PY -c "import json,sys; sys.exit(0 if json.load(open('artifacts/model_card.json')).get('frozen') else 1)"; then
  $PY scripts/freeze.py
fi
$PY scripts/predict.py
$PY scripts/demo.py
$PY scripts/insights.py
$PY scripts/official_eval.py   # needs dataset/challenge1_event_labels.xlsx; evaluation only
$PY scripts/consequence.py   # needs artifacts/population_by_altitude.json (committed); downloads SATCAT once for the breakup check
