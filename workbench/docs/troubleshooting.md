# Find the next action

Start with `make status` and `make doctor`. Help lists commands
that exist in this project, and `make guide` is a short manual for it. Do not edit the vendored runtime to hide a failure.

| Symptom | Next action |
|---|---|
| Missing compiler/checker | Install the tool reported by doctor in the project's environment. Required tools come from each declared document's settings. |
| Document is missing | Run `make document-check DOC=name`. |
| Document is stale | `make status` names what changed under the document (sources, build settings or outputs). Preview the plan and rebuild consuming documents. Verify hidden dependencies are declared. |
| Build failed | Read the first compiler error and current log reported by the command. Correct the source and rerun the document check. |
| "Build inputs changed during execution" | The build rewrote a file it reads, and the rewrite differed on the protected second compilation. The message names the files. Make the generator write only when the content differs (Make rules usually do), or keep a nondeterministic generator (timestamps, random seeds) out of the build command. |
| A file was lost or overwritten | If a snapshot was taken, `make snapshots` lists the copies and prints the Git command that restores a file from one ([snapshots](snapshots.md)); otherwise, version control. |
| Source restored but status still failed | Rebuild; restoring bytes does not certify the failed attempt. |
| Export refused | Build/check the document successfully, then run `make pdf-artifact DOC=name`. |
| Another build is active | Status lists its owner PID and live compiler groups. Wait, or inspect only your own build as described below. |
| Installed runtime belongs to another project | Run from that runtime's project root or pass its `--project` path. For another project, use that project's runtime. |
| `runtime` refuses a file | It was edited, or the record does not know it. Read `latex-ai-init diff . --diff`, restore the file from version control, or pass `--force`. Never delete the record to get past it. |
| Unsupported configuration schema | Workbench 6 accepts schema 4 only. Preserve authored files and prepare a reviewed current configuration; there is no migration flag. |
| Internal error or false success | Capture `make issue ISSUE_NOTE="observed ... expected ..."` and report it; distrust the affected verdict. |

For custom builders, check `output_dir` and that the command writes both PDF and
log. For macro-computed inputs, declare document `inputs` or shared validation
globs. Recorder dependencies use the compiler's `PWD`, including custom builders
run from the project root. An input the compiler discovers that already existed, unchanged,
before the build began (a figure graphicx found without its extension, a local package) is
certified by its hash. If the build's own rules generate files the document includes (a Make
rule that writes a table or a figure), or a source changes while it runs, the workbench
forces one more compilation while comparing their hashes. A further dependency
change fails the attempt and names the files. A symbolic link inside the project that leads out of it (a shared
figure folder) is tracked under the link's own name, with the content it leads to.
Files that only a tool other than TeX reads and that the sources do not name (a makeindex
style, a Biber data source) are not discovered: declare them in the document's `inputs`.
`\bibliographystyle` files that sit beside the document are tracked.
Lint baseline creation and checker-policy changes remain owner decisions.

## Interrupted builds

Ctrl-C or SIGTERM normally stops the runtime's compiler group and records a
failed build. SIGKILL cannot run cleanup; a compiler or the Make recipe that runs it can
outlive its owner. The build stays `running` while any recorded group is alive,
and another build is refused. Status shows an ended owner separately from its
live compiler groups; JSON documents/status include the same ownership details.

On a POSIX system inspect processes before sending signals:

```sh
make status
ps -eo user,pid,ppid,pgid,args
```

Match the owner PID and compiler PGIDs reported by status, their command lines,
and your user. If they are still doing useful work, wait. If you intend to stop
your own abandoned build, send SIGTERM to its verified group (replace `12345`
with that compiler PGID): `kill -TERM -- -12345`. Check again before considering
SIGKILL for a process that ignores termination. PIDs can be reused; never signal
a number from an old report without checking the current processes. Status uses
process birth tokens where the platform provides them; a shell signal uses only
the numeric ID. Do not delete locks (`.latex-ai/artifacts/locks/`), ownership files, journals,
or receipts while processes are alive. After all recorded processes stop, rerun the document check;
it records a new attempt and handles interrupted output recovery.

These inspection commands are POSIX guidance. macOS acceptance and Windows
process behavior still require platform testing.

Agent permissions are soft guardrails. Receipts do not replace scientific review.
