#!/usr/bin/env python3
"""
Field-level diff engine for v1 → v2 account memo and spec.

Produces:
- changes.md: human-readable changelog
- changes.json: machine-readable diff with conflict attribution
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

SKIP_FIELDS = {
    "version", "updated_at", "created_at", "_patch_log", "_conflicts",
    "extraction_confidence", "notes",
    # Skip regenerated spec fields — these change every run, not meaningful structural diffs
    "system_prompt", "retell_import_instructions",
}


def _diff_values(old: Any, new: Any, field: str) -> Optional[dict]:
    if old == new:
        return None

    if isinstance(old, list) and isinstance(new, list):
        added = [x for x in new if x not in old]
        removed = [x for x in old if x not in new]
        if not added and not removed:
            return None
        return {"field": field, "change_type": "list_modified", "added": added, "removed": removed}

    if isinstance(old, dict) and isinstance(new, dict):
        sub_diffs = []
        for k in set(list(old.keys()) + list(new.keys())):
            if k in SKIP_FIELDS:
                continue
            sub = _diff_values(old.get(k), new.get(k), f"{field}.{k}")
            if sub:
                sub_diffs.append(sub)
        if not sub_diffs:
            return None
        return {"field": field, "change_type": "object_modified", "sub_changes": sub_diffs}

    return {"field": field, "change_type": "value_changed", "old": old, "new": new}


def compute_diff(v1: dict, v2: dict) -> list:
    diffs = []
    for key in sorted(set(list(v1.keys()) + list(v2.keys()))):
        if key in SKIP_FIELDS or key.startswith("_"):
            continue
        diff = _diff_values(v1.get(key), v2.get(key), key)
        if diff:
            diffs.append(diff)
    return diffs


def _format_diff_entry_md(diff: dict, indent: int = 0) -> str:
    prefix = "  " * indent
    field = diff["field"]
    change_type = diff["change_type"]

    if change_type == "value_changed":
        return (
            f"{prefix}- **`{field}`**: changed\n"
            f"{prefix}  - Before: `{diff['old']}`\n"
            f"{prefix}  - After:  `{diff['new']}`"
        )
    elif change_type == "list_modified":
        lines = [f"{prefix}- **`{field}`**: list updated"]
        for item in diff.get("added", []):
            lines.append(f"{prefix}  - Added: `{item}`")
        for item in diff.get("removed", []):
            lines.append(f"{prefix}  - Removed: `{item}`")
        return "\n".join(lines)
    elif change_type == "object_modified":
        lines = [f"{prefix}- **`{field}`**: updated"]
        for sub in diff.get("sub_changes", []):
            lines.append(_format_diff_entry_md(sub, indent + 1))
        return "\n".join(lines)
    return f"{prefix}- **`{field}`**: modified"


def generate_changelog_md(
    account_id: str,
    company_name: str,
    v1_memo: dict,
    v2_memo: dict,
    v1_spec: dict,
    v2_spec: dict,
    memo_diffs: list,
    spec_diffs: list,
    conflicts: list,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        f"# Changelog: {company_name} ({account_id})",
        f"",
        f"**Version transition:** v1 → v2",
        f"**Generated:** {now}",
        f"**Source:** Onboarding call transcript",
        f"",
        "---",
        "",
        "## Account Memo Changes",
        "",
    ]

    if memo_diffs:
        for diff in memo_diffs:
            lines.append(_format_diff_entry_md(diff))
            lines.append("")
    else:
        lines.append("_No changes to account memo fields._")
        lines.append("")

    lines += ["---", "", "## Retell Agent Spec Changes", ""]

    if spec_diffs:
        for diff in spec_diffs:
            lines.append(_format_diff_entry_md(diff))
            lines.append("")
    else:
        lines.append("_No structural changes to agent spec. Prompt regenerated from updated memo._")
        lines.append("")

    if conflicts:
        lines += [
            "---",
            "",
            "## Conflicts Resolved",
            "",
            "These fields had different values between the demo call and onboarding confirmation:",
            "",
        ]
        for conflict in conflicts:
            lines.append(f"- **`{conflict['field']}`**")
            lines.append(f"  - Demo call said: `{conflict.get('v1_value')}`")
            lines.append(f"  - Onboarding confirmed: `{conflict.get('v2_value')}`")
            lines.append(f"  - Action: v2 value applied")
            lines.append("")

    patch_log = v2_memo.get("_patch_log") or []
    if patch_log:
        lines += ["---", "", "## Patch Summary", ""]
        for entry in patch_log:
            lines.append(
                f"- `{entry.get('field', 'unknown')}`: **{entry.get('action', 'updated')}** — {entry.get('reason', '')}"
            )
        lines.append("")

    lines += [
        "---",
        "",
        "## Notes",
        "",
        "- v1 data preserved for all unmodified fields.",
        "- List fields (emergency_definition, services_supported, integration_constraints) are merged (union), not replaced.",
        "- All changes sourced from onboarding call transcript.",
        "",
    ]

    return "\n".join(lines)


def generate_changelog_json(
    account_id: str,
    memo_diffs: list,
    spec_diffs: list,
    conflicts: list,
    patch_log: list,
) -> dict:
    return {
        "account_id": account_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version_transition": "v1_to_v2",
        "memo_changes": memo_diffs,
        "spec_changes": spec_diffs,
        "conflicts_resolved": conflicts,
        "patch_log": patch_log,
        "total_changes": len(memo_diffs) + len(spec_diffs),
    }


def produce_changelog(
    account_id: str,
    company_name: str,
    v1_memo: dict,
    v2_memo: dict,
    v1_spec: dict,
    v2_spec: dict,
) -> tuple:
    """Produce markdown and JSON changelogs for a v1 → v2 transition."""
    logger.info(f"Generating changelog for {account_id}")

    def clean(d):
        return {k: v for k, v in d.items() if not k.startswith("_")}

    memo_diffs = compute_diff(clean(v1_memo), clean(v2_memo))
    spec_diffs = compute_diff(clean(v1_spec), clean(v2_spec))
    conflicts = v2_memo.get("_conflicts") or []
    patch_log = v2_memo.get("_patch_log") or []

    md = generate_changelog_md(
        account_id, company_name,
        v1_memo, v2_memo, v1_spec, v2_spec,
        memo_diffs, spec_diffs, conflicts
    )
    js = generate_changelog_json(account_id, memo_diffs, spec_diffs, conflicts, patch_log)

    logger.info(
        f"Changelog done for {account_id}: "
        f"memo_diffs={len(memo_diffs)}, spec_diffs={len(spec_diffs)}, conflicts={len(conflicts)}"
    )
    return md, js


if __name__ == "__main__":
    import json, sys
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    if len(sys.argv) < 5:
        print("Usage: python diff_engine.py <v1_memo.json> <v2_memo.json> <v1_spec.json> <v2_spec.json>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        v1m = json.load(f)
    with open(sys.argv[2]) as f:
        v2m = json.load(f)
    with open(sys.argv[3]) as f:
        v1s = json.load(f)
    with open(sys.argv[4]) as f:
        v2s = json.load(f)
    account_id = v1m.get("account_id", "UNKNOWN")
    company_name = v1m.get("company_name", "Unknown Company")
    md, js = produce_changelog(account_id, company_name, v1m, v2m, v1s, v2s)
    print(md)
    print("\n---JSON---")
    print(json.dumps(js, indent=2))
