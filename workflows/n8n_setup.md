# n8n Setup Guide — Clara AI Orchestrator

## Prerequisites
- Docker + Docker Compose installed
- This repo cloned locally
- Python 3.10+ with packages installed (see README)

---

## Quickstart

```bash
# 1. Clone and navigate to the repo
cd ClaraAi

# 2. Set environment variable for repo root
export REPO_ROOT=$(pwd)

# 3. Start n8n
cd workflows/
docker compose up -d

# 4. Open n8n UI
# Visit: http://localhost:5678
# Login: admin / clara_ai_2024
```

---

## Import Workflows

1. Open n8n at http://localhost:5678
2. Click **"Workflows"** in the left sidebar
3. Click **"+ Add workflow"** → **"Import from file"**
4. Import `pipeline_a_demo_to_v1.json`
5. Repeat for `pipeline_b_onboarding_to_v2.json`

---

## Configure Environment Variable

In the n8n workflow nodes that use `{{ $env.REPO_ROOT }}`:

1. Go to **Settings** → **n8n Variables** (or use `.env` file)
2. Add: `REPO_ROOT = /path/to/your/ClaraAi`
3. Alternatively, edit each **Execute Command** node and replace `{{ $env.REPO_ROOT }}` with the absolute path

---

## Running Pipeline A (Demo → v1)

**Option 1 — Manually in n8n:**
1. Open "Clara AI — Pipeline A" workflow
2. Click **"Execute Workflow"**
3. n8n will scan `dataset/demo/` and process all files

**Option 2 — Via CLI (bypasses n8n, same result):**
```bash
python3 scripts/run_batch.py --pipeline a
```

**Option 3 — Schedule:**
The workflow includes a Schedule Trigger (daily at 8 AM). Enable it in the workflow settings.

---

## Running Pipeline B (Onboarding → v2)

**Option 1 — Webhook (single account):**
```bash
curl -X POST http://localhost:5678/webhook/clara-onboarding \
  -H "Content-Type: application/json" \
  -d '{"account_id": "ACC-001"}'
```

**Option 2 — Scheduled batch:**
Enable the Schedule Trigger in the Pipeline B workflow.

**Option 3 — CLI:**
```bash
python3 scripts/run_batch.py --pipeline b
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `REPO_ROOT` | Yes | Absolute path to the ClaraAi repo |
| `GITHUB_TOKEN` | No | GitHub Personal Access Token (for Issue creation) |
| `GITHUB_REPO` | No | GitHub repo in `owner/repo` format |

---

## Running the Full Batch

```bash
# Both pipelines, all 10 files
python3 scripts/run_batch.py

# Force re-run even if outputs exist
python3 scripts/run_batch.py --force

# Single account
python3 scripts/run_batch.py --account ACC-001
```

---

## Stopping n8n

```bash
cd workflows/
docker compose down
```

Data persists in the `n8n_data` Docker volume.

---

## Logs

- n8n execution logs: in the n8n UI under "Executions"
- Python pipeline logs: `ClaraAi/pipeline.log`
- Run summary: `ClaraAi/run_summary.json`
- Task tracker: `ClaraAi/changelog/tasks.json`
