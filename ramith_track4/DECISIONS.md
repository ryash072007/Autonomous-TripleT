# DECISIONS

1. **Source data:** `data/raw/ad_nprm.xlsx` copied from Downloads; SHA-256 `3bc255f5f790b3adf41b8b70525dd1867310820801ac960fedf9b3ddc2fb1fd0`. Original untouched.
2. **UI: FastAPI + static HTML instead of Streamlit.** Streamlit needs `pyarrow`, which has no wheel for this ARM64 Python 3.13 (build failed); a binary-only install pulled streamlit 0.8, which is broken. FastAPI and uvicorn already work.
3. **LLM:** Anthropic (`claude-haiku-5-5` verified working). Used only for (a) query-parser fallback, (b) the LLM-only baseline. Never for applicability, revision status or answer facts. Ramith approved use.
4. **Dev dependencies installed:** bm25s, anthropic, uvicorn.
