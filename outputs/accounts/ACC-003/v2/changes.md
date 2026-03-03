# Changelog: Bolt Electric Services (ACC-003)

**Version transition:** v1 → v2
**Generated:** 2026-03-03 15:26:29 UTC
**Source:** Onboarding call transcript

---

## Account Memo Changes

- **`business_hours`**: updated
  - **`business_hours.end`**: changed
    - Before: `16:00`
    - After:  `16:30`

- **`call_transfer_rules`**: updated
  - **`call_transfer_rules.timeout_seconds`**: changed
    - Before: `None`
    - After:  `45`

- **`emergency_routing_rules`**: updated
  - **`emergency_routing_rules.order`**: list updated
    - Added: `602-555-0450`

- **`integration_constraints`**: list updated
  - Added: `never book any job labelled "residential panel upgrade" — those all need a quote first`
  - Added: `FieldEdge constraint — no residential jobs`

- **`office_hours_flow_summary`**: changed
  - Before: `During business hours (Monday, Tuesday, Wednesday, Thursday, Friday 07:00–16:00 Denver), calls are answered and routed to the main office or scheduling desk. If transfer fails, a message is taken and callback is promised.`
  - After:  `During business hours (Monday, Tuesday, Wednesday, Thursday, Friday 07:00–16:30 Denver), calls are answered and routed to the main office or scheduling desk. If transfer fails, a message is taken and callback is promised.`

- **`source`**: changed
  - Before: `demo_call`
  - After:  `onboarding_call`

---

## Retell Agent Spec Changes

- **`key_variables`**: updated
  - **`key_variables.business_hours_end`**: changed
    - Before: `16:00`
    - After:  `16:30`

---

## Conflicts Resolved

These fields had different values between the demo call and onboarding confirmation:

- **`business_hours.end`**
  - Demo call said: `16:00`
  - Onboarding confirmed: `16:30`
  - Action: v2 value applied

---

## Patch Summary

- `integration_constraints`: **merged** — New items added during onboarding
- `business_hours`: **updated** — Fields updated during onboarding
- `office_hours_flow_summary`: **regenerated** — Regenerated due to business hours change

---

## Notes

- v1 data preserved for all unmodified fields.
- List fields (emergency_definition, services_supported, integration_constraints) are merged (union), not replaced.
- All changes sourced from onboarding call transcript.
