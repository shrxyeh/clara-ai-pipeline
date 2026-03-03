# Clara AI — Automated Onboarding Pipeline

Processes demo and onboarding call transcripts to produce versioned Retell Agent configurations and structured account memos. Rule-based extraction — no LLM APIs, no external services.

**[Live Dashboard →](https://shrxyeh.github.io/clara-ai-pipeline/dashboard/)**

---

## How It Works

```
  ┌──────────────────────────────────────────────────────────────────┐
  │  PIPELINE A  ·  Demo Call → v1                                   │
  │                                                                  │
  │  dataset/demo/*.txt  ──►  extract  ──►  generate spec  ──►  v1  │
  └──────────────────────────────────────┬───────────────────────────┘
                                         │
                                         ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │  PIPELINE B  ·  Onboarding Call → v2                             │
  │                                                                  │
  │  dataset/onboarding/*.txt  ──►  extract delta  ──►  patch v1    │
  │                                ──►  generate spec  ──►  v2      │
  │                                ──►  changelog                    │
  └──────────────────────────────────────────────────────────────────┘

  outputs/accounts/ACC-NNN/
  ├── v1/  →  account_memo.json,  retell_agent_spec.json
  └── v2/  →  account_memo.json,  retell_agent_spec.json,  changes.md
```

| Script | Role |
|---|---|
| `extractor.py` | Transcript → structured account memo (regex + keyword rules) |
| `spec_generator.py` | Memo → Retell Agent Spec + system prompt |
| `patcher.py` | Merge onboarding updates into v1 memo → v2 |
| `diff_engine.py` | Field-level changelog (MD + JSON) |
| `tracker.py` | Task tracking via `changelog/tasks.json` |
| `run_batch.py` | Entry point — runs all pipelines |

---

## Quickstart

```bash
pip install jsonschema       # optional schema validation
pip install openai-whisper   # optional, only for audio inputs
```

```bash
python scripts/run_batch.py                    # run all 10 accounts
python scripts/run_batch.py --pipeline a       # demo → v1 only
python scripts/run_batch.py --pipeline b       # onboarding → v2 only
python scripts/run_batch.py --account ACC-001  # single account
python scripts/run_batch.py --force            # re-run even if outputs exist
```

Idempotent — running twice skips already-processed accounts.

---

## Using Real Data

Replace the `.txt` files in `dataset/demo/` and `dataset/onboarding/`. Each file needs an `ACCOUNT: ACC-NNN` header line.

For audio files: drop `.m4a` / `.mp3` / `.wav` files in the same folders — Whisper will transcribe them on the next run.

---

## Retell Import

The `retell_agent_spec.json` contains everything needed for manual import:

1. **Agents → Create New Agent** at [app.retellai.com](https://app.retellai.com)
2. Paste `system_prompt` into the LLM/Prompt field
3. Set voice from `voice_style.voice_id`
4. Add variables from `key_variables`
5. Configure call transfer from `call_transfer_protocol`
6. Create internal tools from `tool_invocation_placeholders` — never expose tool names to callers
7. Verify `prompt_hygiene_checklist` shows all `true` before going live

> Programmatic agent creation requires a paid Retell plan. Manual import is the free path.

---

## n8n (Optional)

```bash
cd workflows/
export REPO_ROOT=$(cd .. && pwd)
docker compose up -d
# http://localhost:5678  (admin / clara_ai_2024)
```

Import `pipeline_a_demo_to_v1.json` and `pipeline_b_onboarding_to_v2.json`. See [`workflows/n8n_setup.md`](workflows/n8n_setup.md).

---

## Dashboard

```bash
python -m http.server 8080
# http://localhost:8080/dashboard/
```

---

## Notes

- All transcripts in `dataset/` are synthetic mock data.
- Extraction is regex-based and works well on structured transcripts. For freeform conversations, an LLM extraction step would improve accuracy.
- Phone extraction covers standard US formats. International or vanity numbers may be missed.
