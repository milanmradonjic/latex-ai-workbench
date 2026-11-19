# Workbench 6.4.1 verification

The Gemini integration audit found four regressions. The follow-up checks
cover the distribution and its installed runtime.

| Finding | Regression check |
|---|---|
| Gemini CLI rejected the default-branch pattern | Run the pinned v0.69.0 policy validator on every shipped pattern. Keep the existing rule matching and reference parity tests. |
| The template displaced the user's policy paths | Check that generated settings omit `policyPaths` and report the obsolete Workbench setting during policy validation. |
| Projects that predate the Gemini integration failed after a runtime refresh | Validate policy in a project without the Gemini files and with independently configured Gemini settings. |
| A malformed or missing Gemini policy passed validation | Reject both when the project has adopted the Workbench Gemini files. |

The four audit findings were reproduced before the fix. The Node check uses the
upstream helper from the v0.69.0 commit, downloaded with a SHA-256 check in CI.
It checks rule acceptance without starting a model session or executing shell
tool calls. Antigravity uses its own permission system.

Python 3.10 uses Tomli 2.0.1. Its unmodified pure-Python files and MIT license
come from the published PyPI wheel with SHA-256
`939de3e7a6161af0c887ef91b7d41a53e7c5a1ca976325f429cb46ea9bc30ecc`.

Locally, 430 unit tests passed with three environment-dependent skips, all
51 compiler portability scenarios passed, and the reference runtime and
manuscript checks passed. Disposable upgrades from the Workbench 6.4.0
trees before and after the Gemini integration passed. The latter detected
the old setting before the project files were refreshed. A run with the
standard-library parser disabled also verified the installed Tomli fallback.
