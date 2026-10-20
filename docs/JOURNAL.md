# Learning Journal

Rules: record only what actually happened. Planned work lives in PLAN.md. Failed tests and disproven hypotheses are kept, not rewritten.

## Day 0: Project selection (2026-10-20)
**Done:** surveyed 32 ideas; shortlisted five; chose Plumbline (benchmark-tool ground-truth auditor).
**Why chosen:** documented gap (NVIDIA says client-side tools define metrics inconsistently; a GuideLLM issue reports a ~6% throughput difference vs `vllm bench serve`, one user report), exact answer key possible, needs no GPU.
**Alternatives considered:** prefix-aware CPU router (better demo, lower originality), predicted-length scheduler, cold-start manager, determinism auditor.
**Questions I should be able to answer:** What is coordinated omission? Why does an answer key make a benchmark audit credible?
**Needs revision:** none yet.
