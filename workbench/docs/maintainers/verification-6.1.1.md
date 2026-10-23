# Workbench 6.1.1 verification

This release fixes the three low-severity findings that the 6.0.0 audit left open
after [6.1.0](verification-6.1.0.md). See the [release notes](releases.md).

## Evidence

- **Failing first.** Two tests were added to `tests/test_level2.py`. Against 6.1.0,
  the rename-hint test failed: the hint did not mention a rename. The status test
  errored: there was no `builder` field and no `guide.document_summary`. After the
  fix, all 13 tests in the module pass.
- **Test guard.** On a Linux container with `lualatex` but no `luaotfload`, the
  LuaLaTeX test now skips with "fontspec and luaotfload required" instead of
  failing. The XeLaTeX test has the same guard.
- **Full unit suite:** 501 tests: 496 passed and 5 were skipped. The skips are GNU
  Make 3.81, Biber, LuaLaTeX and XeLaTeX (both partial installs), and the
  root-readable folder case.
- **Compiler portability:** 48 of 48 scenarios passed.
- **Reference:** the runtime was refreshed with `make -C workbench
  upgrade-reference`. `audit-reference` reports identical runtime files, and
  `make check`, `make validate` and `git diff --check` passed.
- The pull request's checks record the hosted results.
