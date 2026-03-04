# Changelog: PureFlow Fire & Water Restoration (ACC-004)

**Version transition:** v1 → v2
**Generated:** 2026-03-04 19:55:25 UTC
**Source:** Onboarding call transcript

---

## Account Memo Changes

- **`emergency_definition`**: list updated
  - Added: `burst pipe`
  - Added: `flooding`
  - Added: `flood`
  - Added: `active water`
  - Added: `sewage backup`
  - Added: `smoke damage`
  - Added: `mold`
  - Added: `biohazard`

- **`emergency_routing_rules`**: updated
  - **`emergency_routing_rules.order`**: list updated
    - Added: `720-555-0211`
    - Added: `720-555-0288`
    - Added: `720-555-0290`

- **`integration_constraints`**: list updated
  - Added: `never create an estimate in Dash without a confirmed site inspection date`
  - Added: `Dash constraint — no roofing claims`

- **`services_supported`**: list updated
  - Added: `Sewage`
  - Added: `Biohazard`
  - Added: `Crime Scene Cleanup`
  - Added: `Restoration`

- **`source`**: changed
  - Before: `demo_call`
  - After:  `onboarding_call`

---

## Retell Agent Spec Changes

- **`key_variables`**: updated
  - **`key_variables.services_list`**: changed
    - Before: `Water Damage, Fire Damage Cleanup, Mold Remediation, Sewage Cleanup`
    - After:  `Water Damage, Fire Damage Cleanup, Mold Remediation, Sewage Cleanup, Sewage, Biohazard, Crime Scene Cleanup, Restoration`

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
