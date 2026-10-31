# Deploy


The front end is a static Vite build (Vercel). The API is FastAPI on your own machine, reached through a Cloudflare
Tunnel. The front end finds it through `VITE_API_BASE`, so the two can live on different domains.

1. **Backend on a PC.** In the repo: `python -m pip install -e .`, then create `.env` (see `.env.example`):

   ```
   ALLOWED_ORIGINS=https://<your-project>.vercel.app,https://<your-custom-domain>
   FRONTEND_URL=https://<your-custom-domain>
   ```

   The PC serves the API only (the default); with `FRONTEND_URL` set, `/` redirects to the console on Vercel.

   and run `python scripts/serve.py` (port 8000). `GET /api/health` returns `{ok, dataset_generated_utc,
   model_version}`. Without `ALLOWED_ORIGINS` the API only answers same-origin requests.
2. **Cloudflare Tunnel** (needs a domain on Cloudflare):

   ```bash
   cloudflared tunnel login
   cloudflared tunnel create orbitguard
   cloudflared tunnel route dns orbitguard api.<your-domain>
   cloudflared tunnel run --url http://localhost:8000 orbitguard
   ```

   For a quick try-out without a domain, `cloudflared tunnel --url http://localhost:8000` prints a temporary
   `https://<random>.trycloudflare.com` address.
3. **Vercel.** Import the GitHub repo, set **Root Directory** to `web`, add the environment variable
   `VITE_API_BASE=https://api.<your-domain>` (no trailing slash), and deploy. `web/vercel.json` already sets the build
   command, the `dist` output, the SPA rewrite and long cache headers for `/assets`. Add the custom domain under
   Project, Domains (the free Hobby plan supports this). Remember to put that domain in `ALLOWED_ORIGINS`.
4. **Offline snapshot.** `web/public/snapshot/` holds a read-only copy of the API responses (about 13 MB, committed, so
   Vercel needs no Python). If the backend is unreachable the front end switches to it, shows "Showing a saved
   snapshot (backend offline) · read-only", and retries the API every 60 s. In snapshot mode decisions are disabled,
   what-if scoring uses the tier rule in the browser, briefs are the template text, and Live shows "Live needs the
   backend". Regenerate it after any change to `artifacts/` with `python scripts/build_snapshot.py` (or
   `npm run snapshot` in `web/`) and commit the result. `VITE_API_BASE=snapshot` forces snapshot mode; an empty
   `VITE_API_BASE` on a non-localhost host does the same.
5. **Notes.** The audit log is written to `artifacts/audit.jsonl` on the PC, not on Vercel. Live mode
   (`SPACETRACK_*`) and LLM briefs (`ANTHROPIC_API_KEY`) read `.env` on the PC. If the PC or the tunnel is down, the
   landing page still loads and says the live data is offline; the console shows a retry button.

