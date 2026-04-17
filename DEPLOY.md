# Railway Deployment

## One-time setup

### 1. Push the repo

The Dockerfile, `.dockerignore`, and `railway.json` are already committed.

```
git push origin main
```

### 2. Create the Railway project

1. Go to https://railway.com/new
2. Click **Deploy from GitHub repo** → pick `MGANDRAOS/concept-lb`
3. Railway detects the `Dockerfile` and starts building. Do NOT deploy yet — configure
   the env + volume first (instructions below). You can let the first build fail;
   the next one will succeed once the env var is set.

### 3. Add environment variables

In the project → **Variables** tab, add:

| Name | Value |
|------|-------|
| `OPENAI_API_KEY` | your OpenAI key |

Railway auto-provides `PORT` — don't set it manually.

### 4. Add a persistent volume for SQLite

In the project → **Settings** → **Volumes** → **New Volume**:

- **Mount path:** `/app/instance`
- **Size:** `1 GB` (free tier allowance)

Without this, every deploy wipes the database. With it, plans + revisions survive deploys.

### 5. Trigger a redeploy

Settings → **Deploy** → **Redeploy**. Watch the build logs. First build takes ~3 min
(Playwright image is ~1 GB).

### 6. Open the public URL

Settings → **Networking** → **Generate Domain**. You'll get a
`*.up.railway.app` URL. The wizard lives at `/wizard`, plans list at `/plans`.

## Operational notes

**Cost:** Railway's free tier gives $5 credit/month. This app uses very little CPU
at idle; generation spikes briefly when you click Regenerate. Expect $2–4/month
with moderate use.

**Cold starts:** Railway keeps the container warm while there's traffic. On idle
it may sleep, and the first request takes ~5s to boot. Not a problem for normal
use.

**Scaling:** Do NOT set `--workers > 1` in the Dockerfile. The in-memory `JOBS`
dict + SSE progress tracking assumes a single process. Use threads for concurrency.

**Logs:** Project → **Logs** shows gunicorn + Flask output live. Tracebacks from
the regenerate endpoint land here.

**Database backups:** Volume data is backed up by Railway automatically. For extra
safety, run `sqlite3 instance/concept_lb.sqlite .dump > backup.sql` occasionally
and download via `railway run cat backup.sql`.

## Updating the app

Any push to `main` triggers a new deploy. Rollback via
**Deployments** tab → pick an older build → **Redeploy**.
