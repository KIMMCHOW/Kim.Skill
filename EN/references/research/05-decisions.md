# 05 Decisions And Action Pattern

Source: local aggregate analysis of `Data/wechat-export-full/all-messages.by-chat.jsonl`.

## 2026-07-01 Update

The updated data covers 2023-10-13 through 2026-07-01, with 485,253 messages sent by KIM. Of those, 355,877 self-authored text messages entered the analysis. There are 8,891 new self-authored text messages after the previous cutoff.

## Decision Signals

Main action/judgment signals in the full window:

- Direct command/action push: 11,540 hits
- Risk/position/invalidation framing: 3,184 hits
- Iteration/rerun/update language: 1,882 hits
- Tooling-based self-distillation: 1,351 hits
- Raw-layer checking: 726 hits
- Local privacy/desensitization/raw-chat boundaries: 205 hits

After the previous cutoff, self-distillation, Codex/GitHub, server, file-path, and Data-directory signals increase. The key behavior in this phase is not "analyze myself again"; it is connecting raw chat export, README, remote repository, skill, Nuwa workflow, and local Data directory into a reusable pipeline.

## Repeated Action Pattern

1. Define the desired output and exact storage/location semantics.
2. Prefer a runnable tool over a verbal explanation.
3. If the result is suspicious, rerun from a more reliable lower-level path.
4. Keep raw data local and private when possible.
5. Convert repeated behavior into a reusable skill, script, README, repository, or workflow.
6. Reason about uncertainty through risk, odds, position, and invalidation.
7. Apply engineering discipline to self-understanding: export first, aggregate, distill, then validate.

## Decision Heuristics Inferred

- If a task can become a tool, tool it.
- If a result is smaller than expected, distrust the wrapper and verify at the primitive level.
- If a vague self-pattern repeats, distill it.
- If something may become public or synced, separate the private raw layer from the publishable summary layer first.
- If a social/emotional signal is confusing, look for observable interaction rhythm before storytelling.
- If there is downside exposure, define stop conditions before intensity increases.
- If a project starts to have long-term value, name it, create the directory, attach the remote, and write the README.

## Synthesis

KIM's decision style is "instrumented intuition": strong instinct, but with a compulsion to check logs, counts, paths, and failure modes.

The updated data strengthens one interpretation: KIM does not only tool external tasks; he also tools himself. Chat records, relationship reviews, trading judgment, and Codex workflows are pushed into the same self-operating system. The upside is reuse and self-calibration. The risk is turning lived experience into metrics too early.
