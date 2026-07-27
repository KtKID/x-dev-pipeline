# Invalid attempt: global skill injection

- Session: `019f8d9c-c370-7931-be07-ffae5d0a91dc`.
- Rollout: `rollout-2026-07-23T14-14-48-019f8d9c-c370-7931-be07-ffae5d0a91dc.jsonl`.
- Raw SHA-256: `58764aee66a9970b58cc736dec4c60401094ef8de3c0d158b4e3b801da7ab16e`.
- Final observed cumulative tokens before interruption: 135,776.
- Invalidity evidence: line 14 reads `/Volumes/machub_app/proj/skill-hub/using-superpowers/SKILL.md`, outside the isolated eval workspace.
- Disposition: interrupted and excluded from quality, time and token metrics.
- Corrective action: reran with `skills.include_instructions=false` and plugins disabled; the valid run read only its isolated workspace.
