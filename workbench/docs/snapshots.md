# Snapshots

`make snapshot` keeps a copy of every file of the project outside it, so that a bad edit, a bad update or an agent's mistake can be undone, whether or not the project is in Git.
It is meant to be run before something risky: an update ([updating](upgrading.md)), a migration ([migrating](migrating.md)), a large edit, or an agent let loose on the files.
`SNAPSHOT_NOTE="before the rewrite of section 3" make snapshot` gives the copy a label (put the assignment before `make`, as here, if the label has a `$` in it: after `make`, Make reads `$` itself). `make snapshots` lists the copies and prints the command that restores from one.

A snapshot never changes the project: its own Git repository, if it has one, is not touched, and nothing is written into the project folder. Nothing is sent anywhere.

## What is kept, and for how long

| Tier | A snapshot goes in | It is kept |
|---|---|---|
| fine | every `make snapshot` that finds a change | one to two weeks |
| daily | the first snapshot of each day (a day is a UTC day) | one to two months |

Each tier is two Git repositories used by turns, one for the current week or month and one for the one before. When a week or month is over, the repository of the period before it is deleted and used afresh.
That is the only deleting the workbench does outside the project, and it deletes only a folder it made itself (one with its own marker file inside); a link, a folder without the marker, or
a repository whose age it cannot read is refused with a message and left as it is. When it deletes one, the output says which, with the date of its newest snapshot. If the computer's clock jumps
forward by more than two periods, the older repositories count as expired and go; a clock that jumps back loses nothing (a repository from the future is never deleted).

A snapshot of files that have not changed since the last one is not made, and says so.

## What is in a snapshot

Every file and link of the project, except:

- Git's own folders (`.git`), and `.latex-ai/artifacts/` and `.latex-ai/backups/`, which are the running workbench's state and the installer's backups (the vendored runtime itself is kept);
- the compiler's files (`.aux`, `.log`, `.out`, `.toc`, `.fls`, `.fdb_latexmk`, `.bbl`, `.blg`, `.bcf`, `.run.xml`, `.synctex.gz`) that lie beside a `.tex` file of the same name (a `train.log`, a `solver.out` or a `refs.bbl`
  with no such source is data, and kept), and the output folder of a document that builds into a folder of its own (its `output_dir`, or the `defaults.output_dir` it inherits);
  a PDF beside the sources is kept, since it may be a figure;
- environments and caches: `.venv`, any folder with a `pyvenv.cfg` or a `conda-meta`, `node_modules`, `site-packages`, `dist-packages`, `__pycache__`;
- a file over 25 MB. It is named in the output, never skipped silently;
- a `.git` file (a submodule's marker), and sockets and pipes, which are not files.

The project's `.gitignore` does not apply: a note, a data file or a draft you never committed is what you would miss. It also means a secret in the folder is in the copy, so the snapshot folders
are private to your user (mode 700). Bytes are kept exactly: the project's `.gitattributes`, your `core.autocrlf` and your Git filters do not apply, at the snapshot or at a restore, and your hooks do not run.
A link is kept as a link and not followed. A folder that cannot be read stops the snapshot, with its name, rather than being left out; a file that disappears while the folder is being read (a compiler's
temporary file) is not an error.

## Where

In `~/.snapshots/NAME-HASH/`, where `NAME` is the project folder's name and `HASH` is eight letters of a hash of its full path (two projects with the same name do not share a folder).
`LATEX_AI_SNAPSHOT_DIR` names another folder instead of `~/.snapshots`; it cannot be inside the project. To free the space of one project, delete its folder yourself.
The folder also holds a `.latex-ai/` with a lock file: one snapshot is taken at a time (a second waits a few seconds for the first, and says so if it is still running).

## Restoring

`make snapshots` ends with commands like these, written out for the newest snapshot (for an older one, use its id and its repository, the folder of that name in the store):

```sh
git --git-dir=$HOME/.snapshots/NAME-HASH/fine-1 --work-tree=/path/to/project diff ID --stat      # what changed since it
git --git-dir=$HOME/.snapshots/NAME-HASH/fine-1 --work-tree=/path/to/project checkout ID -- FILE # one file back
git --git-dir=$HOME/.snapshots/NAME-HASH/fine-1 --work-tree=/path/to/project checkout ID -- .    # every file it has
```

Restoring writes files into the project and nothing else. `checkout ID -- .` overwrites what you have edited since, so run `make snapshot` first if those edits matter. A file made after the snapshot stays where it is: delete it by hand if it is not wanted. A project with its own Git sees the restored
files as ordinary changes. The snapshots are plain Git repositories, so `git --git-dir=... log`, `show` and `ls-tree` work on them as on any other.

## Needs

Git on the `PATH` (the snapshots are Git repositories). The repositories use an identity of their own and none of your Git settings, hooks or templates.
A project without the 4.7 Makefile targets can still be snapshotted by the new release before it is updated: `python3 /path/to/workbench/runtime.py snapshot --project /path/to/project`.
