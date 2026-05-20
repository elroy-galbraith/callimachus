---
proposal_id: proposal_6f86629b
operation: merge_entities
status: pending
confidence: high
created_at: '2026-05-20T01:04:26+00:00'
model_snapshot: claude-sonnet-4-6
kept_id: kara_kondo_interview_c13_code_segregated_seating
removed_id: kara_kondo_interview_c5_code_theater_segregation
rationale: 'Both Codes describe the same phenomenon: Japanese Americans being forced
  to sit in segregated sections (balcony) at movie theaters in Yakima/Wapato. Both
  are spoken by the same narrator (KK) about the same practice.'
evidence:
- in theaters you were segregated. You had to always go upstairs.
- When you were in Yakima that you were segregated. You couldn't sit with the whites
  in the theater...And the balcony.
---

## Merge two entities

**Keep:** [[kara_kondo_interview_c13_code_segregated_seating]]
**Remove:** [[kara_kondo_interview_c5_code_theater_segregation]]

Applying this proposal will rewrite every wikilink pointing to
`kara_kondo_interview_c5_code_theater_segregation` so it points to `kara_kondo_interview_c13_code_segregated_seating`,
then delete the file `kara_kondo_interview_c5_code_theater_segregation.md`.

