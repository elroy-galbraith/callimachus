---
proposal_id: proposal_ab7cbb3d
operation: merge_entities
status: pending
confidence: low
created_at: '2026-05-20T01:04:26+00:00'
model_snapshot: claude-sonnet-4-6
kept_id: kara_kondo_interview_c12_code_constitutional_violation
removed_id: kara_kondo_interview_c12_code_racial_basis
rationale: Both Codes are applied to the same passage about the injustice of incarceration
  and come from the same source text excerpt. 'Racial extraction basis' and 'Violation
  of Bill of Rights' are two aspects of the same argument KK makes in the same utterance.
  They should be merged under the broader 'Constitutional violation / racial injustice'
  construct, or at minimum grouped under a shared subtheme (which already exists as
  kara_kondo_interview_c12_subtheme_illegal_incarceration).
evidence:
- we believe our incarceration was illegal (because of American Bill of Rights) we
  have decided that the fullest cooperation of the government is very best way to
  prove our loyalty and to our country.
- We still feel that the basis on which we were evacuated (because of racial extraction)
  was unjust
---

## Merge two entities

**Keep:** [[kara_kondo_interview_c12_code_constitutional_violation]]
**Remove:** [[kara_kondo_interview_c12_code_racial_basis]]

Applying this proposal will rewrite every wikilink pointing to
`kara_kondo_interview_c12_code_racial_basis` so it points to `kara_kondo_interview_c12_code_constitutional_violation`,
then delete the file `kara_kondo_interview_c12_code_racial_basis.md`.

