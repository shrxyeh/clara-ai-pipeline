# Changelog: PureFlow Fire & Water Restoration (ACC-004)

**Version transition:** v1 → v2
**Generated:** 2026-03-03 15:26:29 UTC
**Source:** Onboarding call transcript

---

## Account Memo Changes

- **`call_transfer_rules`**: updated
  - **`call_transfer_rules.retries`**: changed
    - Before: `None`
    - After:  `1`
  - **`call_transfer_rules.timeout_seconds`**: changed
    - Before: `None`
    - After:  `30`

- **`emergency_definition`**: list updated
  - Added: `biohazard`

- **`emergency_routing_rules`**: updated
  - **`emergency_routing_rules.order`**: list updated
    - Added: `720-555-0290`

- **`integration_constraints`**: list updated
  - Added: `never create an estimate in Dash without a confirmed site inspection date`
  - Added: `Dash constraint — no roofing claims`

- **`services_supported`**: list updated
  - Added: `Biohazard`
  - Added: `Crime Scene Cleanup`

- **`source`**: changed
  - Before: `demo_call`
  - After:  `onboarding_call`

---

## Retell Agent Spec Changes

- **`call_transfer_protocol`**: updated
  - **`call_transfer_protocol.timeout_seconds`**: changed
    - Before: `45`
    - After:  `30`

- **`key_variables`**: updated
  - **`key_variables.services_list`**: changed
    - Before: `Sewage, Fire Damage, Water Damage, Mold Remediation, Sewage Cleanup, Restoration`
    - After:  `Sewage, Fire Damage, Water Damage, Mold Remediation, Sewage Cleanup, Restoration, Biohazard, Crime Scene Cleanup`

---

## Patch Summary

- `emergency_definition`: **merged** — New items added during onboarding
- `services_supported`: **merged** — New items added during onboarding
- `integration_constraints`: **merged** — New items added during onboarding
- `office_hours_flow_summary`: **regenerated** — Regenerated due to business hours change

---

## Notes

- v1 data preserved for all unmodified fields.
- List fields (emergency_definition, services_supported, integration_constraints) are merged (union), not replaced.
- All changes sourced from onboarding call transcript.
