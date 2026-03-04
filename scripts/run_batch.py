#!/usr/bin/env python3
"""
Main batch pipeline runner for Clara AI.

Pipeline A: demo transcript → Account Memo v1 + Retell Spec v1
Pipeline B: onboarding transcript → Account Memo v2 + Retell Spec v2 + changelog

Idempotent: existing outputs are skipped unless --force is passed.

Usage:
    python scripts/run_batch.py                    # Run all 10 files
    python scripts/run_batch.py --pipeline a       # Only Pipeline A
    python scripts/run_batch.py --pipeline b       # Only Pipeline B
    python scripts/run_batch.py --account ACC-001  # Single account
    python scripts/run_batch.py --force            # Re-run even if outputs exist
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Load .env (GEMINI_API_KEY etc.) before importing pipeline modules
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # python-dotenv not installed — env vars must be set manually

sys.path.insert(0, str(Path(__file__).parent))

import extractor
import spec_generator
import patcher
import diff_engine
import tracker

REPO_ROOT = Path(__file__).parent.parent
DEMO_DIR = REPO_ROOT / "dataset" / "demo"
ONBOARDING_DIR = REPO_ROOT / "dataset" / "onboarding"
OUTPUTS_DIR = REPO_ROOT / "outputs" / "accounts"
CHANGELOG_DIR = REPO_ROOT / "changelog"


def setup_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(REPO_ROOT / "pipeline.log", mode="a"),
        ]
    )

logger = logging.getLogger("run_batch")


def load_transcript(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".txt":
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    elif suffix in (".m4a", ".mp3", ".wav", ".mp4", ".ogg", ".flac"):
        return _transcribe_audio(file_path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def _transcribe_audio(audio_path: Path) -> str:
    """Transcribe audio using local Whisper. Falls back with a clear error if not installed."""
    try:
        import whisper  # type: ignore
        logger.info(f"Transcribing audio: {audio_path.name} (this may take a moment)")
        model = whisper.load_model("base")
        result = model.transcribe(str(audio_path))
        transcript = result["text"]
        txt_path = audio_path.with_suffix(".txt")
        with open(txt_path, "w") as f:
            f.write(transcript)
        logger.info(f"Transcription saved to: {txt_path}")
        return transcript
    except ImportError:
        raise RuntimeError(
            f"Cannot transcribe {audio_path.name}: whisper not installed. "
            "Install with: pip install openai-whisper, or provide a .txt transcript."
        )


def run_pipeline_a(transcript_path: Path, force: bool = False) -> dict:
    """Demo call → Account Memo v1 + Retell Spec v1."""
    logger.info(f"--- PIPELINE A: {transcript_path.name} ---")

    text = load_transcript(transcript_path)
    memo = extractor.extract_memo(text, str(transcript_path))
    account_id = memo["account_id"]
    company_name = memo.get("company_name") or "Unknown"

    if account_id == "ACC-UNKNOWN":
        logger.warning(f"Could not extract account_id from {transcript_path.name}")

    out_dir = OUTPUTS_DIR / account_id / "v1"
    out_dir.mkdir(parents=True, exist_ok=True)
    memo_path = out_dir / "account_memo.json"
    spec_path = out_dir / "retell_agent_spec.json"

    if memo_path.exists() and spec_path.exists() and not force:
        logger.info(f"[{account_id}] v1 outputs already exist. Skipping (use --force to overwrite).")
        tracker.create_or_update_task(
            account_id, company_name, "pipeline_a", "completed",
            v1_outputs=[str(memo_path), str(spec_path)],
            notes="Skipped (already exists)"
        )
        return {"account_id": account_id, "status": "skipped", "memo_path": str(memo_path), "spec_path": str(spec_path)}

    spec = spec_generator.generate_spec(memo)

    with open(memo_path, "w") as f:
        json.dump(memo, f, indent=2)
    with open(spec_path, "w") as f:
        json.dump(spec, f, indent=2)

    logger.info(f"[{account_id}] v1 memo → {memo_path}")
    logger.info(f"[{account_id}] v1 spec → {spec_path}")

    hygiene = spec.get("prompt_hygiene_checklist", {})
    failed = [k for k, v in hygiene.items() if not v and k != "mentions_tools_to_caller"]
    if hygiene.get("mentions_tools_to_caller"):
        logger.error(f"[{account_id}] PROMPT HYGIENE FAIL: mentions tools to caller!")
    if failed:
        logger.warning(f"[{account_id}] Prompt hygiene gaps: {failed}")
    else:
        logger.info(f"[{account_id}] Prompt hygiene: PASS")

    tracker.create_or_update_task(
        account_id, company_name, "pipeline_a", "completed",
        v1_outputs=[str(memo_path), str(spec_path)],
        notes=f"v1 generated from demo call on {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    )

    logger.info(f"[{account_id}] Pipeline A complete.")
    return {
        "account_id": account_id,
        "company_name": company_name,
        "status": "success",
        "memo_path": str(memo_path),
        "spec_path": str(spec_path),
        "unknowns": memo.get("questions_or_unknowns") or [],
    }


def run_pipeline_b(transcript_path: Path, force: bool = False) -> dict:
    """Onboarding call → Account Memo v2 + Retell Spec v2 + changelog. Requires Pipeline A first."""
    logger.info(f"--- PIPELINE B: {transcript_path.name} ---")

    text = load_transcript(transcript_path)
    onboarding_result = extractor.extract_onboarding_updates(text, str(transcript_path))
    account_id = onboarding_result["full_extraction"]["account_id"]
    company_name = onboarding_result["full_extraction"].get("company_name") or "Unknown"

    if account_id == "ACC-UNKNOWN":
        logger.warning(f"Could not extract account_id from {transcript_path.name}")

    v1_dir = OUTPUTS_DIR / account_id / "v1"
    v1_memo_path = v1_dir / "account_memo.json"
    v1_spec_path = v1_dir / "retell_agent_spec.json"

    if not v1_memo_path.exists():
        logger.error(f"[{account_id}] v1 memo not found at {v1_memo_path}. Run Pipeline A first.")
        return {"account_id": account_id, "status": "failed", "error": f"v1 memo not found: {v1_memo_path}"}

    with open(v1_memo_path) as f:
        v1_memo = json.load(f)
    with open(v1_spec_path) as f:
        v1_spec = json.load(f)

    v2_dir = OUTPUTS_DIR / account_id / "v2"
    v2_dir.mkdir(parents=True, exist_ok=True)
    changelog_dir = CHANGELOG_DIR / account_id
    changelog_dir.mkdir(parents=True, exist_ok=True)

    v2_memo_path = v2_dir / "account_memo.json"
    v2_spec_path = v2_dir / "retell_agent_spec.json"
    changes_md_path = v2_dir / "changes.md"
    changes_json_path = v2_dir / "changes.json"
    changelog_json_path = changelog_dir / "changes.json"

    if v2_memo_path.exists() and v2_spec_path.exists() and not force:
        logger.info(f"[{account_id}] v2 outputs already exist. Skipping (use --force to overwrite).")
        return {"account_id": account_id, "status": "skipped", "v2_memo_path": str(v2_memo_path)}

    v2_memo = patcher.apply_patch(v1_memo, onboarding_result)
    v2_memo["company_name"] = v2_memo.get("company_name") or company_name

    v2_spec = spec_generator.generate_spec(v2_memo)
    v2_spec["updated_at"] = datetime.now(timezone.utc).isoformat()

    changes_md, changes_json = diff_engine.produce_changelog(
        account_id, v2_memo.get("company_name") or company_name,
        v1_memo, v2_memo, v1_spec, v2_spec
    )

    with open(v2_memo_path, "w") as f:
        json.dump(v2_memo, f, indent=2)
    with open(v2_spec_path, "w") as f:
        json.dump(v2_spec, f, indent=2)
    with open(changes_md_path, "w") as f:
        f.write(changes_md)
    with open(changes_json_path, "w") as f:
        json.dump(changes_json, f, indent=2)
    # Mirror JSON to top-level changelog dir (used by dashboard)
    with open(changelog_json_path, "w") as f:
        json.dump(changes_json, f, indent=2)

    logger.info(f"[{account_id}] v2 memo → {v2_memo_path}")
    logger.info(f"[{account_id}] v2 spec → {v2_spec_path}")
    logger.info(f"[{account_id}] changelog → {changes_md_path}")

    conflicts = v2_memo.get("_conflicts") or []
    patch_log = v2_memo.get("_patch_log") or []
    logger.info(f"[{account_id}] {len(patch_log)} field changes, {len(conflicts)} conflicts resolved")

    tracker.create_or_update_task(
        account_id, company_name, "pipeline_b", "completed",
        v1_outputs=[str(v1_memo_path), str(v1_spec_path)],
        v2_outputs=[str(v2_memo_path), str(v2_spec_path)],
        changelog_path=str(changes_md_path),
        notes=(
            f"v2 generated from onboarding on {datetime.now(timezone.utc).strftime('%Y-%m-%d')}. "
            f"{len(patch_log)} changes, {len(conflicts)} conflicts."
        )
    )

    logger.info(f"[{account_id}] Pipeline B complete.")
    return {
        "account_id": account_id,
        "company_name": company_name,
        "status": "success",
        "v2_memo_path": str(v2_memo_path),
        "v2_spec_path": str(v2_spec_path),
        "changes_md_path": str(changes_md_path),
        "total_changes": len(patch_log),
        "conflicts_resolved": len(conflicts),
    }


def discover_files(directory: Path, patterns: list = None) -> list:
    if not directory.exists():
        logger.warning(f"Directory not found: {directory}")
        return []
    files = []
    for pattern in (patterns or ["*.txt", "*.m4a", "*.mp3", "*.wav"]):
        files.extend(directory.glob(pattern))
    return sorted(files)


def run_all(pipeline: str = "all", account_filter: str = None, force: bool = False) -> dict:
    start_time = datetime.now(timezone.utc)
    logger.info(f"{'='*60}")
    logger.info(f"CLARA AI BATCH PIPELINE")
    logger.info(f"pipeline={pipeline} | account={account_filter or 'all'} | force={force}")
    logger.info(f"{'='*60}")

    results = {"pipeline_a": [], "pipeline_b": [], "errors": []}

    if pipeline in ("all", "a"):
        demo_files = discover_files(DEMO_DIR)
        if not demo_files:
            logger.warning(f"No demo files found in {DEMO_DIR}")
        for f in demo_files:
            if account_filter:
                text = f.read_text(encoding="utf-8", errors="ignore")
                if account_filter.upper() not in text.upper():
                    continue
            try:
                results["pipeline_a"].append(run_pipeline_a(f, force=force))
            except Exception as e:
                logger.error(f"Pipeline A failed for {f.name}: {e}", exc_info=True)
                results["errors"].append({"file": str(f), "pipeline": "a", "error": str(e)})

    if pipeline in ("all", "b"):
        onb_files = discover_files(ONBOARDING_DIR)
        if not onb_files:
            logger.warning(f"No onboarding files found in {ONBOARDING_DIR}")
        for f in onb_files:
            if account_filter:
                text = f.read_text(encoding="utf-8", errors="ignore")
                if account_filter.upper() not in text.upper():
                    continue
            try:
                results["pipeline_b"].append(run_pipeline_b(f, force=force))
            except Exception as e:
                logger.error(f"Pipeline B failed for {f.name}: {e}", exc_info=True)
                results["errors"].append({"file": str(f), "pipeline": "b", "error": str(e)})

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    a_ok = sum(1 for r in results["pipeline_a"] if r.get("status") == "success")
    a_skip = sum(1 for r in results["pipeline_a"] if r.get("status") == "skipped")
    b_ok = sum(1 for r in results["pipeline_b"] if r.get("status") == "success")
    b_skip = sum(1 for r in results["pipeline_b"] if r.get("status") == "skipped")
    errors = len(results["errors"])

    logger.info(f"\n{'='*60}")
    logger.info(f"BATCH COMPLETE in {elapsed:.1f}s")
    logger.info(f"  Pipeline A: {a_ok} success, {a_skip} skipped")
    logger.info(f"  Pipeline B: {b_ok} success, {b_skip} skipped")
    if errors:
        logger.info(f"  Errors: {errors}")
    logger.info(f"  Outputs: {OUTPUTS_DIR}")
    logger.info(f"{'='*60}\n")

    tracker.print_summary()

    summary = {
        "run_at": start_time.isoformat(),
        "elapsed_seconds": elapsed,
        "pipeline_a": results["pipeline_a"],
        "pipeline_b": results["pipeline_b"],
        "errors": results["errors"],
        "totals": {
            "a_success": a_ok, "a_skipped": a_skip,
            "b_success": b_ok, "b_skipped": b_skip,
            "errors": errors,
        }
    }

    summary_path = REPO_ROOT / "run_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Clara AI Batch Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_batch.py                    # Run all 10 files
  python scripts/run_batch.py --pipeline a       # Only Pipeline A
  python scripts/run_batch.py --pipeline b       # Only Pipeline B
  python scripts/run_batch.py --account ACC-001  # Single account
  python scripts/run_batch.py --force            # Re-run even if outputs exist
        """
    )
    parser.add_argument("--pipeline", choices=["all", "a", "b"], default="all")
    parser.add_argument("--account", default=None, help="Filter to a specific account ID (e.g. ACC-001)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()
    setup_logging(args.log_level)

    summary = run_all(pipeline=args.pipeline, account_filter=args.account, force=args.force)

    sys.exit(1 if summary["errors"] else 0)


if __name__ == "__main__":
    main()
