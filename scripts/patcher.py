#!/usr/bin/env python3
"""
Applies onboarding-derived updates to a v1 account memo to produce v2.

Strategy:
- List fields (emergencies, services, constraints) are merged (union), not replaced.
- Dict fields are merged field-by-field; scalar conflicts are logged and resolved to v2 value.
- Untouched v1 fields are preserved as-is.
"""

import copy
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

MERGE_FIELDS = [
    "emergency_definition",
    "services_supported",
    "integration_constraints",
]

REPLACE_FIELDS = [
    "business_hours",
    "emergency_routing_rules",
    "non_emergency_routing_rules",
    "call_transfer_rules",
    "office_address",
]


def _merge_lists(v1_list: list, v2_list: list) -> list:
    """Union of two lists, deduplicating case-insensitively for strings."""
    merged = list(v1_list) if v1_list else []
    for item in (v2_list or []):
        if isinstance(item, str):
            if not any(item.lower() == existing.lower() for existing in merged):
                merged.append(item)
        elif item not in merged:
            merged.append(item)
    return merged


def _merge_dicts(v1_dict: dict, v2_dict: dict, path: str = "") -> tuple:
    """
    Merge two dicts. v2 scalars override v1; lists are unioned.
    Returns (merged_dict, conflicts_list).
    """
    merged = copy.deepcopy(v1_dict) if v1_dict else {}
    conflicts = []

    for key, new_val in (v2_dict or {}).items():
        old_val = merged.get(key)
        field_path = f"{path}.{key}" if path else key

        if new_val is None:
            continue  # don't overwrite v1 data with None

        if old_val is None:
            merged[key] = new_val
            logger.debug(f"  PATCH {field_path}: (null) → {new_val}")
        elif isinstance(old_val, list) and isinstance(new_val, list):
            merged[key] = _merge_lists(old_val, new_val)
            added = [x for x in new_val if x not in old_val]
            if added:
                logger.debug(f"  MERGE LIST {field_path}: added {added}")
        elif isinstance(old_val, dict) and isinstance(new_val, dict):
            sub_merged, sub_conflicts = _merge_dicts(old_val, new_val, field_path)
            merged[key] = sub_merged
            conflicts.extend(sub_conflicts)
        elif old_val != new_val:
            conflicts.append({
                "field": field_path,
                "v1_value": old_val,
                "v2_value": new_val,
                "source": "onboarding_call",
            })
            merged[key] = new_val
            logger.info(f"  CONFLICT RESOLVED {field_path}: '{old_val}' → '{new_val}'")

    return merged, conflicts


def apply_patch(v1_memo: dict, onboarding_result: dict) -> dict:
    """
    Apply onboarding updates to a v1 memo and return the v2 memo.

    Args:
        v1_memo: original v1 account memo
        onboarding_result: output of extractor.extract_onboarding_updates()

    Returns:
        Patched v2 memo with _patch_log and _conflicts embedded
    """
    account_id = v1_memo.get("account_id", "UNKNOWN")
    logger.info(f"Applying onboarding patch to {account_id}")

    v2 = copy.deepcopy(v1_memo)
    v2["version"] = "v2"
    v2["updated_at"] = datetime.now(timezone.utc).isoformat()
    v2["source"] = "onboarding_call"

    delta = onboarding_result.get("delta", {})
    all_conflicts = []
    patch_log = []

    for field in MERGE_FIELDS:
        if field in delta:
            old_val = v1_memo.get(field) or []
            new_val = delta[field] or []
            merged = _merge_lists(old_val, new_val)
            added = [x for x in merged if x not in old_val]
            if added:
                v2[field] = merged
                patch_log.append({
                    "field": field,
                    "action": "merged",
                    "added": added,
                    "source": "onboarding_call",
                    "reason": "New items added during onboarding",
                })
                logger.info(f"  MERGED {field}: added {len(added)} items")

    for field in REPLACE_FIELDS:
        if field in delta and delta[field]:
            old_val = v1_memo.get(field)
            new_val = delta[field]

            if isinstance(old_val, dict) and isinstance(new_val, dict):
                merged_val, conflicts = _merge_dicts(old_val, new_val, field)
                v2[field] = merged_val
                all_conflicts.extend(conflicts)
                changed_keys = [c["field"] for c in conflicts]
                if changed_keys:
                    patch_log.append({
                        "field": field,
                        "action": "updated",
                        "changed_subfields": changed_keys,
                        "source": "onboarding_call",
                        "reason": "Fields updated during onboarding",
                    })
            elif old_val != new_val:
                all_conflicts.append({
                    "field": field,
                    "v1_value": old_val,
                    "v2_value": new_val,
                    "source": "onboarding_call",
                })
                v2[field] = new_val
                patch_log.append({
                    "field": field,
                    "action": "replaced",
                    "v1_value": old_val,
                    "v2_value": new_val,
                    "source": "onboarding_call",
                    "reason": "Entire field replaced during onboarding",
                })

    # Recompute office hours summary if hours changed
    if "business_hours" in delta and delta["business_hours"]:
        bh = v2.get("business_hours") or {}
        bh_days = ", ".join(bh.get("days") or [])
        bh_start = bh.get("start") or "opening time"
        bh_end = bh.get("end") or "closing time"
        bh_tz = (bh.get("timezone") or "").split("/")[-1]
        v2["office_hours_flow_summary"] = (
            f"During business hours ({bh_days} {bh_start}–{bh_end} {bh_tz}), "
            f"calls are answered and routed to the main office or scheduling desk. "
            f"If transfer fails, a message is taken and callback is promised."
        )
        patch_log.append({
            "field": "office_hours_flow_summary",
            "action": "regenerated",
            "reason": "Regenerated due to business hours change",
        })

    v2["notes"] = (
        f"{v1_memo.get('notes') or ''} "
        f"Updated to v2 from onboarding call on {datetime.now(timezone.utc).strftime('%Y-%m-%d')}."
    ).strip()

    from extractor import _compute_confidence, _identify_unknowns
    v2["extraction_confidence"] = _compute_confidence(v2)
    unknowns = _identify_unknowns(v2)
    v2["questions_or_unknowns"] = unknowns if unknowns else None

    v2["_patch_log"] = patch_log
    v2["_conflicts"] = all_conflicts

    logger.info(
        f"Patch complete for {account_id}: "
        f"fields_changed={len(patch_log)}, conflicts={len(all_conflicts)}"
    )
    return v2


if __name__ == "__main__":
    import json, sys
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    if len(sys.argv) < 3:
        print("Usage: python patcher.py <v1_memo.json> <onboarding_result.json>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        v1 = json.load(f)
    with open(sys.argv[2]) as f:
        onb = json.load(f)
    v2 = apply_patch(v1, onb)
    print(json.dumps(v2, indent=2))
