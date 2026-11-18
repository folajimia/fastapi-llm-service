# Playwright MCP + Claude Agents: Setup & Usage Plan

A step-by-step plan for using the Playwright MCP server and its generated
Claude agents to **build**, **maintain**, and **self-heal** the Playwright
tests in `integration_test/playwright_tests/`.

Mark each step `[x]` when done. Every section is a fresh checklist, so you can
stop and resume anywhere.

---

## Table of contents

- [Part 0 — What you already have](#part-0--what-you-already-have)
- [Part 1 — Finish the setup](#part-1--finish-the-setup)
- [Part 2 — Build a new test (walkthrough)](#part-2--build-a-new-test-walkthrough)
- [Part 3 — Maintain tests (walkthrough)](#part-3--maintain-tests-walkthrough)
- [Part 4 — Self-heal a failing test (walkthrough)](#part-4--self-heal-a-failing-test-walkthrough)
- [Part 5 — Guardrails and how to enforce them](#part-5--guardrails-and-how-to-enforce-them)
- [Quick reference](#quick-reference)

---

## Part 0 — What you already have

You ran `npx playwright init-agents --loop=vscode` inside
`integration_test/playwright_tests/`, which generated:

| File(s)                                        | What it is                                                                 |
| ---------------------------------------------- | -------------------------------------------------------------------------- |
| `.vscode/mcp.json`                             | MCP server config: `playwright-test` (`npx playwright run-test-mcp-server`) |
| `.github/agents/playwright-test-planner.agent.md`   | Agent that turns a feature description into a **test plan**           |
| `.github/agents/playwright-test-generator.agent.md` | Agent that turns a test plan into a **Playwright spec**, using a live browser |
| `.github/agents/playwright-test-healer.agent.md`    | Agent that **debugs and fixes** failing tests                         |
| `specs/README.md`                              | Directory where test plans live                                            |
| `tests/seed.spec.ts`                           | Empty seed file the generator fills in                                     |

**One catch:** `--loop=vscode` targets **GitHub Copilot**. You use
**Claude Code**, so Part 1 has you run the `--loop=claude` variant, which
generates the same three agents in `.claude/agents/` where Claude Code finds
them.

---

## Part 1 — Finish the setup

**Goal:** Claude Code has (a) the `playwright-test` MCP server for browser
access and test running, (b) the three agents, and (c) the guardrails and
secret rules baked in so they apply to every session.

### Checklist

- [x] **1.1 Generate the Claude Code agents.** From the Playwright project dir:

  ```bash
  cd integration_test/playwright_tests
  npx playwright init-agents --loop=claude
  ```

  This creates `.claude/agents/playwright-test-{planner,generator,healer}.md`
  (Claude Code format, same three agents).

- [ ] **1.2 Make the MCP server visible to Claude Code.** Start `claude` from
      the **repo root** and run `/mcp`. If `playwright-test` is not listed,
      create `.mcp.json` at the **repo root**:

  ```json
  {
    "mcpServers": {
      "playwright-test": {
        "command": "npx",
        "args": ["playwright", "run-test-mcp-server"]
      }
    }
  }
  ```

  (Same server `init-agents` already configured for VS Code — we reuse it
  rather than adding a second, generic MCP server.) Approve it when prompted.

  > If Claude Code (launched at repo root) doesn't pick up agents from the
  > nested `.claude/agents/`, copy the three `.md` files to
  > `<repo-root>/.claude/agents/` and verify with `/agents`.

- [ ] **1.3 Verify the toolchain end to end.** In Claude Code:

  - `/mcp` → `playwright-test` connected.
  - `/agents` → the three playwright agents listed.
  - Smoke test: ask Claude to use `test_list` (via the agent) to list your
    specs. It should report `tests/acceptance/box_connector.spec.ts` etc.

- [ ] **1.4 Commit the generated files; keep secrets ignored.** Commit
      `.mcp.json`, the agent files, `specs/`, and `tests/seed.spec.ts`.
      They contain no secrets. `.env` stays gitignored.

- [ ] **1.5 Write the credentials rule into `CLAUDE.md`** so every future
      session inherits it (agent + interactive):

  ```markdown
  ## Test credentials
  Connector credentials and TOTP seeds live in
  integration_test/playwright_tests/.env (see .env.example for variable names).
  Never echo their values into chat, PR descriptions, logs, or commits —
  refer to them by variable name only.
  ```

- [ ] **1.6 Fix the generated healer agent (required — guardrail conflict).**
      The stock `playwright-test-healer.agent.md` tells the agent to
      "fix assertions and expected values" and to "do the most reasonable
      thing possible to pass the test". That is exactly what we must forbid
      (see Guardrail 1). Open `.claude/agents/playwright-test-healer.md` and:

  - **Delete** the bullet `Fixing assertions and expected values`.
  - **Replace** it with:
    `Updating only selectors/locators and waits/timeouts. NEVER change an
    assertion, expected value, or fixture (e.g. expectedPagesIngested). If a
    failure is not a locator/wait drift, stop and report — do not edit code.`
  - **Delete or soften** `Do not ask user questions... do the most reasonable
    thing possible to pass the test` → replace with:
    `If the root cause is unclear, or the fix would change what the test
    asserts, stop and report the diagnosis instead of editing code. Do not
    mark tests test.fixme() to make them pass — that hides failures; propose
    it only with a written justification for a human to approve.`

- [ ] **1.7 (Optional) Wire the same rules into the Jenkins self-heal path**
      later, once the interactive flow works (see Part 4, step 4.2).

---

## Part 2 — Build a new test (walkthrough)

**Scenario:** Team Ultra needs an acceptance test for a new connector, e.g.
**Dropbox**. The flow is: you (or the planner agent) write a short test plan in
`specs/`, then the **generator agent** walks the real UI in a live browser and
writes the spec in your house style.

### Checklist

- [ ] **2.1 Put the credentials in `.env`** following `.env.example` naming
      (`DROPBOX_USERNAME`, `DROPBOX_PASSWORD`), and add matching fields to
      `config/testConfig.ts` next to the `confluence` / `google` blocks.
      Update `.env.example` with the new variable *names* (never values).

- [ ] **2.2 Write the test plan** to `specs/dropbox-connector.md`. Keep it to
      steps and expectations, e.g.:

  ```markdown
  # Dropbox connector acceptance test
  Steps:
  1. Sign in as SPP account (pod 999 pool), open admin connectors page
  2. Expect zero-state (connections-zero-state), click header-create-connection-button
  3. Choose Dropbox → Connect → continue (connect-info-modal-continue-button)
  4. Complete Dropbox OAuth (credentials from env; do not log values)
  5. Save connection, wait for "Synced" status (waitForSyncStatus helper)
  6. Expect ingested pages count shown in connection row
  Expectations: connection visible in list, status reaches "Synced"
  Cleanup: remove all connections after test
  ```

- [ ] **2.3 Invoke the generator agent** (via `/agents` →
      `playwright-test-generator`, or just ask Claude to use it):

  > Use the playwright-test-generator to implement
  > specs/dropbox-connector.md as
  > tests/acceptance/dropbox_connector.spec.ts. Before generating, read
  > tests/acceptance/box_connector.spec.ts, helpers/pageHelpers.ts,
  > helpers/connectionCleanupHelper.ts and config/testConfig.ts and follow
  > their conventions (JBT account fixtures, cleanupAllConnections,
  > loadConnectorConfig, data-testid locators).

- [ ] **2.4 Walk the sensitive part deliberately.** The generator opens a live
      browser (`generator_setup_page`). When the flow reaches the password /
      2FA screen, tell it: *"fill credentials from the .env variables, don't
      echo them."* Values pass env → browser, never into the transcript — the
      same pattern as `handleAtlassianTotpVerification` in
      `helpers/oauth/atlassianOAuthHelpers.ts`.

- [ ] **2.5 Run and iterate:**

  ```bash
  cd integration_test/playwright_tests
  nvm use && yarn install
  yarn test tests/acceptance/dropbox_connector.spec.ts --headed
  ```

  If it fails, ask the healer agent (Part 4) or let the generator fix its own
  spec — it can read the error and the trace in `tmp/test-results/`.

- [ ] **2.6 PR it.** Delete `tests/seed.spec.ts` changes if the generator
      touched them; keep the new spec + test plan.

**Why this beats raw codegen:** `playwright codegen` produces locator soup
(see the abandoned `test-1.spec.ts` / `test-3.spec.ts`). The generator agent
produces a spec in your conventions because it read the neighbors first, and
it verifies each locator against the live DOM before the test ever reaches
Jenkins.

---

## Part 3 — Maintain tests (walkthrough)

**Scenario:** Atlassian redesigns their login page. The TOTP form selector
`#two-step-verification-form` in `helpers/oauth/atlassianOAuthHelpers.ts`
stops matching, and every spec using the Atlassian flow fails in the nightly.
This is your most common breakage mode: Atlassian, Google, and Notion change
their UIs without notice.

### Checklist

- [ ] **3.1 Cluster the failures before touching code.** Give Claude the JUnit
      artifact and ask it to group, not fix:

  > Read tmp/junit/report.xml (or the Jenkins JUnit artifact). Cluster the
  > failures by which helper or page each failure is rooted in. Tell me the
  > smallest set of files whose fix would turn most failures green.

  Expected answer here: *"3 of 4 failures route through
  `handleAtlassianTotpVerification` — fix the helper once."*

- [ ] **3.2 See what the vendor page looks like *now*.** Ask Claude to open the
      affected flow in the MCP browser (credentials from `.env`, per rule
      1.5) and diff against what the helpers expect:

  > Open the Atlassian login in the browser, walk to the 2FA step, and tell me
  > whether the TOTP form still matches #two-step-verification-form and the
  > submit button still matches role=button "Log in". Show me what changed.

- [ ] **3.3 Fix the shared helper once.** Claude edits
      `helpers/oauth/atlassianOAuthHelpers.ts`, not the three specs. One edit
      heals every spec that imports it — that's the payoff of the helper
      structure you already have.

- [ ] **3.4 Re-run only the affected specs:**

  ```bash
  yarn test tests/acceptance/confluence_connector.spec.ts --headed
  ```

- [ ] **3.5 Optional: scheduled drift detection.** A weekly loop that opens
      each OAuth entry point and compares against the locators in
      `helpers/oauth/*` finds vendor redesigns *before* the nightly does.
      Start manual (calendar reminder to do step 3.2); automate later only if
      the manual check feels like a chore.

**The habit to build:** never debug one failing spec in isolation. Ask "what
do these failures have in common?" first — the answer is usually a shared
helper, and that's where the fix belongs.

---

## Part 4 — Self-heal a failing test (walkthrough)

**Scenario:** Jenkins nightly shows `box_connector.spec.ts` failing with
`TimeoutError: locator.click: Timeout 60000ms exceeded` on the Box "Connect"
button — Box changed their `data-testid`.

**Definition of "self-heal":** the agent proposes a *locator/wait* fix in a PR
with evidence. It never changes what the test asserts. A human always merges.

### Decision table (what the agent does with each failure)

| Agent's diagnosis                        | Agent's action                                   | Human's role          |
| ---------------------------------------- | ------------------------------------------------ | --------------------- |
| Locator/wait drifted (vendor UI changed) | Fix locator in shared helper, open PR            | Review + merge        |
| Test timing / flake (passed on retry)    | Propose wait/assertion-timeout fix in PR         | Review + merge        |
| Product bug (app behavior actually wrong)| **No code change.** Summarize evidence, tag owner| File/confirm bug      |
| Couldn't classify                        | **No code change.** Report what it found         | Decide which row above |

"Couldn't classify" is a normal, expected outcome — treat it as a success of
the process, not a failure of the agent.

### Checklist

- [ ] **4.1 Collect the evidence.** From the Jenkins run: the JUnit XML and
      trace/video artifacts (`tmp/junit/report.xml`, `tmp/test-results/`;
      traces depend on `PLAYWRIGHT_TRACE_MODE`).

- [ ] **4.2 Invoke the healer agent** (`/agents` → `playwright-test-healer`,
      the one you hardened in step 1.6) with the failure context:

  > The nightly failed: box_connector.spec.ts, TimeoutError on the Box
  > "Connect" button click. JUnit report at tmp/junit/report.xml. Diagnose
  > the root cause. If it is a locator/wait drift, fix it in the smallest
  > possible change (shared helper preferred), verify by running the single
  > spec locally, then open a PR titled "heal(box): update connector list
  > locator after vendor UI change" with: classification, failure evidence,
  > before/after locators, and the local run result. If it is flake, a
  > product bug, or unclear — do NOT edit code; report the evidence and stop.
  > Never print credentials or TOTP values from .env — variable names only.

  (Once proven interactively, this prompt can run as `claude -p "..."` from a
  Jenkins post-failure hook — same rules, no human typing.)

- [ ] **4.3 Read the PR the way you'd review a junior's fix.** The body should
      answer three questions in under a minute:
      1. *What broke?* (failing locator + evidence)
      2. *What changed?* (the diff — a few lines, in a helper file)
      3. *Proof?* (local run output of the affected spec)

- [ ] **4.4 Check the diff against the guardrails** (Part 5, checklist 5.4)
      before merging.

- [ ] **4.5 Track the outcome** — merge, or convert to a bug ticket. Either
      way the failure got a decision from a human, which is the point.

---

## Part 5 — Guardrails and how to enforce them

Each guardrail has a *system-level* enforcement (works even when you're
tired, in a hurry, or the agent runs unattended) plus a *review-time* check.

### Guardrail 1 — Healing touches locators/waits only, never assertions

> Why: `expectedPagesIngested = "4"` is a product contract. An agent that
> edits it to make a test green turns the suite into a bug factory. The stock
> Playwright healer agent *explicitly instructs* fixing "assertions and
> expected values" — that is why setup step 1.6 is mandatory.

- [ ] **System enforcement — the agent definition.** The hardened
      `.claude/agents/playwright-test-healer.md` (step 1.6) only permits
      locator/wait edits and stops the agent otherwise. Every healing run
      inherits the rule; nothing depends on someone remembering it.
- [ ] **System enforcement — CI diff check (recommended).** A small script on
      the PR fails fast if a healing PR touches a forbidden pattern:

  ```bash
  # scripts/check-healing-pr.sh — run in CI on PRs labeled "self-heal"
  if git diff origin/master...HEAD \
      | grep -E '^[+-].*(expected[A-Z]|toBe\(|toHaveText|toEqual)' \
      | grep -v 'helpers/.*[Ll]ocator'; then
    echo "::error::Healing PRs may only change locators/waits, not assertions"
    exit 1
  fi
  ```

- [ ] **Review-time check.** Confirm the diff only changes locator strings,
      `waitFor*` calls, or timeouts — nothing after `expect(`, no constant
      values, no fixture attributes.

### Guardrail 2 — Healing goes through PRs; "couldn't classify" is a normal outcome

- [ ] **System enforcement — permissions.** The agent never pushes to `master`
      and never merges. In CI (`claude -p`), use an allowlist that permits
      `Edit`, `Bash(yarn test ...)`, and `gh pr create` — nothing that merges.
      Interactively, the standing rule is: the agent's output is *a PR*,
      never a direct commit to `master`.
- [ ] **System enforcement — the decision table.** It's in the healing prompt
      (Part 4, step 4.2) and the hardened agent file: flake / product-bug /
      unclear ⇒ **no PR**. You should see "couldn't classify" reports
      regularly — that's the agent working correctly. If it opens a PR for
      *every* failure, the rules are being ignored; fix the agent file, not
      the process.
- [ ] **Review-time check.** Every healing PR carries classification +
      evidence (checklist 4.3). A PR that says only "fixed test" gets sent
      back.

### Guardrail 3 — Secrets never appear in PRs, logs, or transcripts

- [ ] **System enforcement — where secrets live.** Values stay in
      `integration_test/playwright_tests/.env` (gitignored). The agent reads
      them only to pass them to the browser. The rule is recorded in
      `CLAUDE.md` (step 1.5), so agent and interactive sessions both inherit
      it.
- [ ] **System enforcement — what the agent never receives.** When walking an
      OAuth flow, type passwords/2FA yourself or have the agent fill from env
      *without echoing*. Never paste a TOTP secret into chat. The codebase
      already models the right pattern: secret goes
      `env → otplib → code → fill()`, unprinted.
- [ ] **Review-time check.** PR review checklist:

  ```markdown
  - [ ] No passwords, tokens, or TOTP seeds in the diff
  - [ ] No credential values in the PR body or linked logs
        (variable NAMES like CONFLUENCE_PASSWORD are fine; values are not)
  - [ ] Only changes to locators/waits, not assertions or expected values
  - [ ] Classification + evidence present in the PR body
  ```

---

## Quick reference

| Task                           | Command / prompt                                                       |
| ------------------------------ | ---------------------------------------------------------------------- |
| Regenerate agents for Claude   | `npx playwright init-agents --loop=claude` (in `integration_test/playwright_tests`) |
| Check MCP server               | `/mcp` in Claude Code                                                  |
| Check agents                   | `/agents` in Claude Code                                               |
| Run one spec                   | `yarn test tests/acceptance/box_connector.spec.ts --headed`            |
| Run everything                 | `yarn test` (JUnit at `tmp/junit/report.xml`)                          |
| Build a new connector test     | Test plan in `specs/` → `playwright-test-generator` agent (Part 2)     |
| Cluster CI failures            | Part 3, step 3.1 prompt against the JUnit artifact                     |
| Self-heal a failure            | `playwright-test-healer` agent + Part 4 prompt                         |
| Where guardrails live          | Healer agent file (1.6), `CLAUDE.md` (1.5), CI diff check (5.1)        |
