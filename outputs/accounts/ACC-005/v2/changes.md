# Changelog: Greentech Mechanical Contractors (ACC-005)

**Version transition:** v1 → v2
**Generated:** 2026-03-03 15:26:29 UTC
**Source:** Onboarding call transcript

---

## Account Memo Changes

- **`emergency_definition`**: list updated
  - Added: `chemical hazard`

- **`emergency_routing_rules`**: updated
  - **`emergency_routing_rules.primary_phone`**: changed
    - Before: `206-555-0677`
    - After:  `206-555-0600`

- **`integration_constraints`**: list updated
  - Added: `never create a service job for a site not already in our ServiceTrade customer list`
  - Added: `ServiceTrade constraints — no residential, PM jobs need contract number`

- **`office_address`**: updated
  - **`office_address.full`**: changed
    - Before: `3700 Airport Way South, Seattle, WA 98108`
    - After:  `3700 Airport Way South, Seattle WA 98108`

- **`source`**: changed
  - Before: `demo_call`
  - After:  `onboarding_call`

---

## Retell Agent Spec Changes

- **`key_variables`**: updated
  - **`key_variables.office_address`**: changed
    - Before: `3700 Airport Way South, Seattle, WA 98108`
    - After:  `3700 Airport Way South, Seattle WA 98108`
  - **`key_variables.emergency_routing_primary`**: changed
    - Before: `206-555-0677`
    - After:  `206-555-0600`

---

## Conflicts Resolved

These fields had different values between the demo call and onboarding confirmation:

- **`emergency_routing_rules.primary_phone`**
  - Demo call said: `206-555-0677`
  - Onboarding confirmed: `206-555-0600`
  - Action: v2 value applied

- **`office_address.full`**
  - Demo call said: `3700 Airport Way South, Seattle, WA 98108`
  - Onboarding confirmed: `3700 Airport Way South, Seattle WA 98108`
  - Action: v2 value applied

---

## Patch Summary

- `emergency_definition`: **merged** — New items added during onboarding
- `integration_constraints`: **merged** — New items added during onboarding
- `emergency_routing_rules`: **updated** — Fields updated during onboarding
- `office_address`: **updated** — Fields updated during onboarding
- `office_hours_flow_summary`: **regenerated** — Regenerated due to business hours change

---

## Notes

- v1 data preserved for all unmodified fields.
- List fields (emergency_definition, services_supported, integration_constraints) are merged (union), not replaced.
- All changes sourced from onboarding call transcript.
