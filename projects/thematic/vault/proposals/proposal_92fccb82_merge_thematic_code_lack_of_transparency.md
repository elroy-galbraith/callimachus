---
proposal_id: proposal_92fccb82
operation: merge_entities
status: pending
confidence: medium
created_at: '2026-05-18T22:20:53+00:00'
model_snapshot: claude-sonnet-4-6
kept_id: thematic_code_lack_of_transparency
removed_id: thematic_code_feeling_shut_out
rationale: 'The Code ''Feeling shut out'' (thematic_code_feeling_shut_out) and the
  Code ''Lack of transparency'' (thematic_code_lack_of_transparency) both capture
  the same atomic construct: a participant''s subjective sense of being excluded from
  information about their own data. The definitional texts differ only in phrasing
  (''language of exclusion or being kept in the dark'' vs. ''not told how their data
  is being used''), and the excerpts coded with each are semantically indistinguishable.
  Keeping ''Lack of transparency'' is preferred because it has a matching Subtheme
  entity and is used across more excerpts.'
evidence:
- It just feels like decisions about my information happen behind closed doors. Nobody
  sits me down to explain it.
- I just felt completely shut out — like nobody was telling me what was actually going
  on with my data.
---

## Merge two entities

**Keep:** [[thematic_code_lack_of_transparency]]
**Remove:** [[thematic_code_feeling_shut_out]]

Applying this proposal will rewrite every wikilink pointing to
`thematic_code_feeling_shut_out` so it points to `thematic_code_lack_of_transparency`,
then delete the file `thematic_code_feeling_shut_out.md`.

