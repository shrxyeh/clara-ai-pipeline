# Changelog: Arctic Air HVAC Solutions (ACC-001)

**Version transition:** v1 → v2
**Generated:** 2026-03-04 19:56:13 UTC
**Source:** Onboarding call transcript

---

## Account Memo Changes

- **`business_hours`**: updated
  - **`business_hours.days`**: list updated
    - Added: `Saturday`

- **`emergency_definition`**: list updated
  - Added: `property damage`
  - Added: `screeching noise`

- **`integration_constraints`**: list updated
  - Added: `never schedule any job type called "Chimney Sweep" — we trialed it and pulled out`
  - Added: `ServiceTitan constraint — no sprinkler or fire suppression jobs`

- **`office_address`**: updated
  - **`office_address.full`**: changed
    - Before: `4820 Westview Drive, Columbus, Ohio, 43214`
    - After:  `4820 Westview Drive, Columbus, Ohio 43214`

- **`office_hours_flow_summary`**: changed
  - Before: `During business hours (Monday, Tuesday, Wednesday, Thursday, Friday 07:00–18:00 New_York), calls are answered and routed to the main office or scheduling desk. If transfer fails, a message is taken and callback is promised.`
  - After:  `During business hours (Monday, Tuesday, Wednesday, Thursday, Friday, Saturday 07:00–18:00 New_York), calls are answered and routed to the main office or scheduling desk. If transfer fails, a message is taken and callback is promised.`

- **`source`**: changed
  - Before: `demo_call`
  - After:  `onboarding_call`

---

## Retell Agent Spec Changes

- **`key_variables`**: updated
  - **`key_variables.office_address`**: changed
    - Before: `4820 Westview Drive, Columbus, Ohio, 43214`
    - After:  `4820 Westview Drive, Columbus, Ohio 43214`
  - **`key_variables.business_hours_days`**: changed
    - Before: `Monday through Friday`
    - After:  `Monday through Saturday`

---

## Conflicts Resolved

These fields had different values between the demo call and onboarding confirmation:

- **`office_address.full`**
  - Demo call said: `4820 Westview Drive, Columbus, Ohio, 43214`
  - Onboarding confirmed: `4820 Westview Drive, Columbus, Ohio 43214`
  - Action: v2 value applied

---

## Patch Summary

- `emergency_definition`: **merged** — New items added during onboarding
- `integration_constraints`: **merged** — New items added during onboarding
- `office_address`: **updated** — Fields updated during onboarding
- `office_hours_flow_summary`: **regenerated** — Regenerated due to business hours change

---

## Notes

- v1 data preserved for all unmodified fields.
- List fields (emergency_definition, services_supported, integration_constraints) are merged (union), not replaced.
- All changes sourced from onboarding call transcript.
