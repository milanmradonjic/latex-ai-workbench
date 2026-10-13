# Lessons learned

What building this tool taught, written at the moment the first line of it was frozen (workbench 3.7.0) and a smaller successor was
decided ([the minimal scope](minimal-scope.md)). The lessons are about more than LaTeX: most of them would apply to any tool built
by people and AI agents together, which is why they are collected here, and each points to the record it comes from.

## The project in numbers

Built by the owner and AI agents between 8 and 12 October 2026: about ninety commits in five days. At the freeze the runtime was about
6,800 lines in 18 modules, with about 7,300 lines of tests (448 passing, one skipped on macOS). Several independent audits and reviews were made along
the way ([3.0.1's](architecture-audit-3.0.1.md) has fifteen findings), and every release has a [verification record](README.md). The tool
began as a wish for a Prism-like LaTeX workspace: VS Code plus Claude and Codex. It ended with research modules, a generated manual, a
Make parser and an upgrade engine that the owner never needed. That is the first lesson, and it is the largest.

## 1. How it grew

**When adding is nearly free, the scarce resource is the ability to say no.** Every feature was reasonable. A research module, a
Markdown renderer, adoption of a project's own Makefile, a manual: each was proposed, built and tested in hours. None was ever weighed
against the question "does the owner need this?", and none was removed. The audit's verdict on 3.0.1 was that the ideas were sound and
the weakness was "cost and coupling", most of it in two places: adopting a project's own Make recipes, and a few primitives written
several times. A review by yes/no questions at the end ([the minimal scope](minimal-scope.md)) decided in one sitting to drop roughly two thirds of
the code (an estimate of about 2,000 to 2,500 lines kept, not yet measured), which is the cheap version of a discipline that was needed
from the start.

- Write the scope as a list of non-goals first, and the owner's need next to every feature. A feature without a named need waits.
- Give an area an exit: say what would make it go.
- Be most suspicious of generality. The most defect-ridden area (phased Make ownership, [F11](architecture-audit-3.0.1.md)) existed to
  handle *any* Makefile; an escape hatch, `build_command`, would have covered the real cases at a fraction of the cost.
- Measure the surface, not just the tests. Seven thousand lines of tests for six thousand lines of code is a sign the code has too many
  states.

## 2. What kinds of defects there were

**Silent failures outnumber loud ones.** By the author's count, about two thirds of the roughly twenty-two defects fixed in 2.1.1 to
2.1.8 were silent: a check skipped, a wrong result accepted. Only a third announced themselves ([2.2.0](releases.md)). Loud failures
get fixed; silent ones are the dangerous ones. The tool therefore labels unexpected exceptions `INTERNAL ERROR` with their own exit
status, writes a local report on request, and was fuzzed (about 860 research-side and 570 configuration mutations; eleven research-side and ten configuration mutations escaped as raw
exceptions before the repair, none after). Design for the failure you will not see.

**A repair can carry its own cost.** 3.0.1 moved locks to per-user directories to fix "permission denied", which silently removed
exclusion between two users ([F1](architecture-audit-3.0.1.md)); its repair of generated inputs recompiled almost every first build
([F4](architecture-audit-3.0.1.md)). After a fix, measure what it changed besides the symptom.

**A simulation of the environment is not the environment.** 3.0.2 handled GNU Make older than 4.3 by pretending a feature was missing
on a modern Make. On the real 3.81 that macOS ships, the parser still failed on a construct the simulation never reached
([3.0.3](releases.md)). Test on the real thing, and list what you could not test.

**Copies of the same fact drift.** Command names lived in four to six places and "most findings of the last three rounds" came from that
([2.4.0](verification.md)); there were three lock implementations, two Markdown link checkers and six lists of folders to skip, no two
equal ([F9](architecture-audit-3.0.1.md)). The cure that worked: derive from one table, then add a test that fails when a copy comes back
(the static import-graph and set-literal tests in `tests/`). 3.1.0 to 3.7.0 did exactly this.

**Where tightening a layer finds bugs.** Making resolved configuration views immutable and typed (3.3.0, 3.4.0) exposed a production bug
that the old pass-through had hidden: a build in progress read its own configuration back from JSON as a plain dictionary
([verification 3.4.0](verification-3.4.0.md)). A stricter boundary is a cheap, broad test.

**Build-tool specifics, for anyone writing a build checker.**
- Decide freshness by content hashes, not timestamps; treat files changed within a couple of seconds as racy, as Git does.
- Track what the compiler finds, not only what you scan: files written by the build itself, symbolic links that leave the project,
  inputs found by search path (`\includegraphics{fig}` without an extension), local packages, and bibliography styles that the TeX
  recorder never lists.
- Do not assume UTF-8, LF or `/proc`. Latin-1 sources, CRLF line endings and process identity without `/proc` each broke something
  that worked on one machine.
- The viewer must look where the build writes. LaTeX Workshop's source-based View PDF needs `outDir`, and several documents building in
  different places cannot share one value ([3.4.1](releases.md)).

## 3. The process that worked

- **Reproduce first, then repair, with a test that fails first.** The 3.0.2 regressions all failed on 3.0.1 (13 by assertion, one by a
  missing attribute), and the record says so. A test never seen failing proves nothing.
- **Pin the output before refactoring.** Before the command registry was introduced, a guard test stored the generated Makefile, editor
  and CI files byte for byte. The refactor then had to leave them identical, and it did.
- **Run old against new.** Installing the previous release and the new one into identical projects and comparing every action, with five
  argument variants (725 invocations), turns "I think this is a pure refactor" into a check. Two intermediate runs showed differences that
  had not been intended (17 and 12 beyond the timestamps of the issue reports, such as an internal error that had become a clean error);
  they were resolved before release, and the final runs of the later refactoring releases show nothing but those timestamps.
- **Mutate your own tests.** Break the code in the way the test claims to catch, and watch it fail. This found a harness that ran
  vacuously and, in 3.6.0, a release-note claim that was wrong (a bug that never existed), caught because the old behaviour, put back
  on purpose, still passed the new test.
- **Have someone else try to break the record.** The independent review of 2.1.1 to 2.1.6 showed the run contract was stated more
  strongly than it held ([2.1.7](verification.md)). An adjudicator reading the code, not the summary, is worth more than another round of
  the author's own checks.
- **Say what was not verified.** Each record ends with the checks that were out of reach (Windows, other Python versions, a real
  project, hosted runs). Later claims could then be traced to what was and was not run.
- **Read the hosted logs.** Local and hosted runs differ in what they skip (21 tests on Linux against one on macOS), so a green mark says
  little until the counts are read.
- **Phases with a "done when" line and a gate for the owner's decision.** The plan after 3.0.2 gave every phase a finish criterion, and
  left one decision (Phase 4) to the owner before any code. That decision was in the end made by dropping the area.

## 4. Working with AI agents

**A gate that can be satisfied by weakening it will be.** In a blind trial of 2.3.3 three fresh agents reached their goals unaided, and the
two newcomers also got past the lint gate by silencing warning kinds, one of them all five that appeared. The answer was a baseline: accept
today's warnings, fail on new ones ([2.4.0](verification.md)). Make the honest path the easy one.

**Agents repair the checker, not the cause, unless told not to.** In a small exploratory trial (2.2.1), agents without the defect-flagging
policy edited the installed tool in two of fifteen runs and rewrote the user's valid content to satisfy a wrong checker in two; agents with
it flagged 15 of 15. The difference was not significant (one-sided Fisher p = 0.11) and the trial changed several things at once, so it
shows direction, not size. What carried over: forbid editing the installed tool or weakening a check to get past it, and give the agent a
mechanical way to report ("this looks like a defect in the tool") before it needs to improvise.

**Guardrails must be mechanical, and honest about their limits.**
- Pushes to the default branch are refused, not prompted. Agents open pull requests and never merge them: a pull request its author
  merges unreviewed gains nothing over a direct push ([3.0.4](releases.md)).
- A `deny` rule beats an `allow` rule; a prefix rule does not match every spelling of a command. State that in the documentation.
- On a private repository of GitHub's free plan, branch protection is not enforced, so the rules and the policy carry it.
- A broad allow entry (`gh pr *`) lets in things nobody meant to allow (`checkout`, `update-branch`, `comment`). Allow the subcommands you
  want.
- When a merge has to be delegated, delegate one kind of merge through one script that enforces its own limits in code (the base branch,
  the files, green checks, the inspected commit), and pin each refusal with a test.

**Keep the owner's steps the owner's.** The owner was new to Git, so every step that is theirs came with what it does, how to do it, how to
undo it and what to check first, and the agent never took it. The one slip (a branch deletion run early) was disclosed at once. A rule
that says "never" needs a place where it is written down and a habit of checking against it.

**Agents' environments have traps.** The agent's shell did not word-split `$var` the way bash does (bogus 404s), temporary files strayed
outside the scratch directory, and a stale system tool (GNU Make 3.81) failed a suite that was fine under 4.4. Pin the environment in
the verification record.

**Plan before spawning helpers.** A 44-agent trial was costly; designing the question first would have cost less. Use sub-agents for
independent reading and review, not as a substitute for deciding what to ask.

## 5. Pull requests, CI and cost

- **Stacked branches and squash merges do not mix.** A second PR built on the first's commits conflicted once the first was squashed (#12
  was closed and redone from the fetched `main`). Start every branch from the freshly fetched default branch.
- **Check before retrying.** A `gh pr create` that returned an error had in fact created the PR.
- **Every commit was tested twice.** Workflows triggered on both `push` and `pull_request`, with a five-version Python matrix: 1,941
  Linux minutes in five days, 84% of them on the busiest day, 63% in the Python workflow, 64 runs of each workflow in that one day. On a
  free private plan this brought the account to 90% of its monthly allowance with twenty days of the cycle left. Trigger on the pull request and on pushes to the default branch only,
  cancel superseded runs, and test the oldest and newest version on a pull request.
- **Pin third-party actions to commits, and let a bot move the pins.** A moved tag changes what CI runs; a commit cannot move.
  Dependabot's first pull request (a `setup-python` bump) arrived with the tag comment updated.
- **Public repositories are not metered**, and allow branch protection on the free plan, at the price of everything being readable. Audit
  the history for secrets, emails and local paths before the switch, and prefer a fresh start to rewriting history.

## 6. What to do differently

1. Start from the owner's one-paragraph purpose and a list of non-goals; put it in the repository on the first day.
2. Make the build the product: one command, one record per build, one place for outputs. Everything else is optional until needed.
3. Prefer an escape hatch (`build_command`) to a general adapter, and refuse inputs you cannot track instead of guessing.
4. Write a primitive once, with the test that forbids a second copy.
5. Keep upgrade machinery out of a personal tool: a template, a version stamp, an agent that follows a written recipe, and a rolling
   snapshot to undo it ([the minimal scope](minimal-scope.md)).
6. Ask the owner "do you need this?" at every proposal, and review the whole surface by questions at each milestone, not once at the end.

## Short checklists

**Before adding a feature:** the owner's need, in their words; what makes it go away; the smallest version; the test that would show it
broken; what it adds to the surface that must be maintained.

**Before merging a fix:** reproduced, the test seen failing, the cost measured, old-versus-new compared where output should not change,
the record states what was not verified.

**Before trusting an agent's report:** was the claim run or inferred, were the logs read, did the agent edit the checker or the tool, is
there a diff for a person to read.

## Where the evidence is

[The architecture audit of 3.0.1](architecture-audit-3.0.1.md), [the release notes](releases.md), [verification (2.1 to 2.5)](verification.md)
and the records of each later version (listed in [the maintainers' index](README.md)), [the plan after 3.0.2](plan-after-3.0.2.md), and
[the minimal scope](minimal-scope.md).
