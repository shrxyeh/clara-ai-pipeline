# Changelog: Clearflow Plumbing & Drain (ACC-002)

**Version transition:** v1 → v2
**Generated:** 2026-03-03 15:26:29 UTC
**Source:** Onboarding call transcript

---

## Account Memo Changes

- **`call_transfer_rules`**: updated
  - **`call_transfer_rules.retries`**: changed
    - Before: `None`
    - After:  `1`

- **`emergency_definition`**: list updated
  - Added: `water heater explosion`

- **`emergency_routing_rules`**: updated
  - **`emergency_routing_rules.order`**: list updated
    - Added: `512-555-0322`

- **`integration_constraints`**: list updated
  - Added: `ServiceTrade constraints — no gas line jobs, no weekend bookings via ServiceTrade`

- **`source`**: changed
  - Before: `demo_call`
  - After:  `onboarding_call`

---

## Retell Agent Spec Changes

_No structural changes to agent spec. Prompt regenerated from updated memo._

---

## Patch Summary

- `emergency_definition`: **merged** — New items added during onboarding
- `integration_constraints`: **merged** — New items added during onboarding
- `office_hours_flow_summary`: **regenerated** — Regenerated due to business hours change

---

## Notes

- v1 data preserved for all unmodified fields.
- List fields (emergency_definition, services_supported, integration_constraints) are merged (union), not replaced.
- All changes sourced from onboarding call transcript.
