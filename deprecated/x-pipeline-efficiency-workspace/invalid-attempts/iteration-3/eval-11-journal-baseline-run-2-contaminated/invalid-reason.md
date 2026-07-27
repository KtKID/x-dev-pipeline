# Invalid attempt: journal baseline run 2

Status: excluded from grading, token aggregation, and promotion decisions.

The formal executor reused a pre-existing reviewer from another evaluation tree after fresh reviewer capacity was unavailable. That reviewer retained voice-chain context and then reviewed the journal-index-recovery workspace, violating fresh-context and run-isolation requirements.

Evidence:

- contaminated executor: `/root/journal_baseline_r2`
- contaminated executor session: `019f8ced-b6f3-7921-8ea3-87f53e2067c0`
- legitimate fresh child: `/root/journal_baseline_r2/qa_r1_intent`
- legitimate child session: `019f8cf7-a9b5-7031-8713-bbd38f221e92`
- reused external child: `/root/voice_chain_baseline/voice_q2_correctness`
- reused external session: `019f8ac2-1ea0-7613-ade4-6176d10d7411`

Remediation: retain this reason and metadata as contamination evidence, require every reviewer to be a fresh child inside the executor task subtree, and rerun journal baseline run 2 from a clean workspace. The contaminated workspace is excluded from the formal commit.
