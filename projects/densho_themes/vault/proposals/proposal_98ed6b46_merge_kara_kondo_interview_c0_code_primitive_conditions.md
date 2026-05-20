---
proposal_id: proposal_98ed6b46
operation: merge_entities
status: pending
confidence: medium
created_at: '2026-05-20T01:04:26+00:00'
model_snapshot: claude-sonnet-4-6
kept_id: kara_kondo_interview_c0_code_primitive_conditions
removed_id: kara_kondo_interview_c1_code_primitive_domestic_labor
rationale: 'Both Codes describe the same construct: primitive frontier domestic conditions
  (wood stoves, water pumping, no running water) faced by Japanese immigrant families.
  c0 references the mother''s shock, c1 references the children''s experience — both
  describe the same domestic material conditions in the same region and era.'
evidence:
- A wagon with farm horses... the water was a pump... heat the water on wood stoves...
  very primitive condition
- you did your washing with a washboard... you had to heat your water on the cook
  stove. And your heating was usually by stoves... And usually without running water
---

## Merge two entities

**Keep:** [[kara_kondo_interview_c0_code_primitive_conditions]]
**Remove:** [[kara_kondo_interview_c1_code_primitive_domestic_labor]]

Applying this proposal will rewrite every wikilink pointing to
`kara_kondo_interview_c1_code_primitive_domestic_labor` so it points to `kara_kondo_interview_c0_code_primitive_conditions`,
then delete the file `kara_kondo_interview_c1_code_primitive_domestic_labor.md`.

