# Repository working instructions

## Start and communication

- Read `README.md`, `docs/codex-handoff.md`, and the files relevant to the current
  task. The handoff is a dated snapshot; current code and current GitHub issues
  take precedence over stale progress notes.
- Communicate with Mustafa in Turkish. Explain the concrete change, its purpose,
  verification, and any remaining limitation briefly. He is a third-year
  computer-engineering student and should be able to explain the resulting code.
- Begin with `git status` and the current branch. Preserve existing user changes.
  Inspect before switching branches, pulling, or applying changes.
- Continue routine reads, focused edits, and offline verification within the
  authorized task. Git writes and external actions follow the user's actual
  authorization; do not introduce repeated confirmations for already approved work.

## Product and architecture

- Keep deterministic calculations in Python. The LLM selects a bounded plan or
  supplies the existing guarded narration contract; it does not invent numbers,
  execute code/SQL, select arbitrary paths, or redefine the allowed analyses.
- Reuse `app/lakehouse/gold.py`, the Housing services/evidence/chart modules, and
  `app/services/inflation_analysis.py`. Do not create a second calculation source.
- Preserve existing HTTP contracts unless the task explicitly changes them.
  Generic web/anomaly/causality tools and a general agent registry are not runtime
  features merely because they appear in `docs/tool-contracts.md`.
- Keep changes small and scoped. New dependencies/frameworks require a concrete
  need; the existing services and FastAPI are sufficient for the current tasks.

## Environment and verification

- Use Python 3.12 and the repository's existing `.venv` when available.
- Single offline verification, using the same interpreter from any working
  directory:
  - Windows PowerShell: `.\.venv\Scripts\python.exe -m scripts.verify_project`
  - Linux: `.venv/bin/python -m scripts.verify_project`
  It runs the test suite, both offline stub evaluations and `git diff --check` in
  order, stops at the first failure, and keeps per-run logs under
  `out/verification/`.
- Run focused behavior tests while editing and the complete verification command
  once on the final code. Do not add tests that only repeat implementation
  details. Documentation-only changes need link/example checks and the required
  CI; do not repeat the full package unnecessarily.
- The 17 October baseline had 708 passing Linux tests. This is historical evidence,
  not a hard-coded expected count or a substitute for running relevant checks.
- Report what was actually run. Stub evaluations check harness behavior; a few
  live cases do not establish a general model-accuracy or performance metric.

## Data and model access

- Work offline with synthetic fixtures by default. Do not make live EVDS/LLM
  calls, download real datasets, or incur charges without user authorization.
- Do not print or commit `.env`, API keys, authentication tokens, or raw provider
  error bodies. Codex sign-in and the application's Gemini/EVDS credentials are
  separate concerns; do not change the app provider to configure the editor.
- Preserve physical raw/receipt/CSV hash checks, safe paths, source references,
  quality notes, and input/output/staging/backup separation. Never repair a test
  by weakening integrity checks or rewriting shared fixture hashes.
- Weekly publication coverage remains `unverified` without an official calendar.
  Synthetic fixture success does not complete real-data acceptance in #39/#40.

## Git and delivery

- Use a focused feature branch; do not overwrite other contributors' work,
  force-push shared history, or bypass required CI.
- For an authorized PR/merge, inspect the current head, diff, checks and review
  state. Treat test results as belonging to the exact source tree that ran them.
- On 21 October 2026 Mustafa granted standing approval to merge non-problematic
  PRs without asking again. This requires independent inspection of the current
  PR head and diff, appropriate scope, successful required CI, and no unresolved
  blocking review. The model implementing a change must not merge its own PR based
  only on its own checks: OpenCode prepares the PR and stops, while independent
  review and merging of suitable PRs happen in a separate ChatGPT/Codex review
  session. Editor model access is separate from application LLM access.
- Match personal contribution claims to actual diffs. Afra owns EVDS delivery,
  Osman owns BDDK/demo acceptance, Mustafa owns the question harness/release work.
  Preserve historical credit, including the initial tool-contract contribution.
- Keep issue progress and the handoff accurate when completing a task. If GitHub
  access is unavailable, say so and provide the local result; do not claim an issue,
  PR, merge, or release was published.

## Task continuation and approval boundaries

1. Complete the current task, review the diff, and run the relevant checks.
2. When checks pass, commit and push the scoped changes, then create or update the
   PR. Routine coding, testing, and fixes do not require repeated confirmation.
   The implementing model stops after opening the PR; independent review decides
   whether it is merged.
3. Briefly report the completed work, actual test results, and remaining gaps.
4. Update `docs/codex-handoff.md` with completed work, the active branch, test
   status, and the next step. Recommend a new session for the next independent
   task and keep the handoff short.
5. Prioritize existing acceptance criteria and the working demo. Do not invent
   features or expand the product scope to keep busy.
6. Do not take over Osman's or Afra's tasks or branches without instruction.
7. Check dependencies before starting. An unmerged PR is not part of `main`; wait
   on dependent work and use a separate branch from current `main` for independent
   work instead.
8. Live or paid application API calls, data deletion, force push, release, and
   publication still require Mustafa's approval; commit/push/PR authorization does
   not authorize them. The implementing model does not merge its own PR. Mandatory
   sandbox permissions still apply.
9. Stop for a genuine blocker, an unresolved product decision, or necessary access
   that is unavailable. State the concrete missing input or permission.
10. Distinguish local, PR, and merged work in every report; do not present pending
    acceptance as complete.
