---
proposal_id: proposal_226d17cf
operation: merge_entities
status: pending
confidence: medium
created_at: '2026-05-20T01:04:26+00:00'
model_snapshot: claude-sonnet-4-6
kept_id: kara_kondo_interview_c6_subtheme_fear_uncertainty_emotional_toll
removed_id: kara_kondo_interview_c6_code_fear_uncertainty_emotional_toll
rationale: 'There is both a Code (kara_kondo_interview_c6_code_fear_uncertainty_emotional_toll,
  referenced in an excerpt''s codedAs) and a Subtheme with the same label ''Fear,
  Uncertainty, and Emotional Toll'' in chunk 6. The Code appears to be a dangling
  reference — the vault has no entity record for the Code but the Excerpt references
  it. The Subtheme covers the same construct. These should be reconciled: the Subtheme
  should absorb the Code''s function.'
evidence:
- I would cry every night, after everybody was in bed and think, 'Oh, my gosh. What's
  happening to us? Why are they doing this to us?' And it, it really was not so much
  frightening, but a very distressing time.
---

## Merge two entities

**Keep:** [[kara_kondo_interview_c6_subtheme_fear_uncertainty_emotional_toll]]
**Remove:** [[kara_kondo_interview_c6_code_fear_uncertainty_emotional_toll]]

Applying this proposal will rewrite every wikilink pointing to
`kara_kondo_interview_c6_code_fear_uncertainty_emotional_toll` so it points to `kara_kondo_interview_c6_subtheme_fear_uncertainty_emotional_toll`,
then delete the file `kara_kondo_interview_c6_code_fear_uncertainty_emotional_toll.md`.

