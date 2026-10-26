# Snapshots

Snapshots are **optional and off by default**. Choose once when preparing the
project's `.latex-ai.json`: `"snapshots": false` uses the normal Git workflow;
`"snapshots": true` opts into an additional backup of eligible working files,
including uncommitted, untracked, and ignored files. Git integration alone does
not save uncommitted work, but ordinary edits and upgrades require neither a
snapshot nor a new commit. A Git-managed project normally leaves snapshots off.

Disabled projects omit snapshot commands from `make help` and `make guide`.
The fixed Makefile still contains their entry points; invoking one reports that
snapshots are disabled before touching any store. Setting the flag to false
does not delete existing stores. Re-enable it deliberately to list or use them.
The installer reports the choice but creates no stores or timers. Timers below
are an additional manual opt-in for a project that has enabled snapshots.

The opt-in gate reads only this flag, so recovery can work with missing TeX roots;
`make help` and `make guide` then still list the snapshot commands beside the
configuration problem. Missing or malformed configuration cannot opt in.
Turning the flag off does not stop timers you loaded: unload them first
(`launchctl bootout`, [below](#timers-on-a-mac-launchd)), or each run logs that
snapshots are disabled. The backend and storage layout
are shared across projects; this setting introduces no installation profiles.

A snapshot is a copy of every file of the project, kept outside it, so that a bad edit, a bad update or an agent's mistake can be undone, whether or not the project is in Git.
For an opted-in project, `make snapshot` takes one by hand when wanted.
`SNAPSHOT_NOTE="before the rewrite of section 3" make snapshot` gives it a label (put the assignment before `make`, as here, if the label has a `$` in it: after `make`, Make reads `$` itself).
`make snapshots` lists the snapshots and prints the command that restores from one.

A snapshot never changes the project: its own Git repository, if it has one, is not touched, and nothing is written into the project folder. Nothing is sent anywhere.

## Three stores

Each store is a Git repository of its own, so what goes into one can never push anything out of another.

| Store | Filled by | A snapshot is taken | Kept |
|---|---|---|---|
| `manual` | you, with `make snapshot` | when files differ from your last manual snapshot | all of them; the workbench never deletes one |
| `weekly` | a timer that asks every day ([below](#timers-on-a-mac-launchd)) | the first time in a calendar week (Monday to Sunday, by the computer's own clock and time zone) that files differ from the last weekly snapshot | the newest 6 |
| `frequent` | a timer that asks every 30 minutes | each time the timer asks, if files differ from the last frequent snapshot | the newest 60 |

The two timers run `python3 .latex-ai/workbench.py snapshot --tier frequent` and `--tier weekly`; `make snapshot` is the manual one (`--tier manual`, the default). A snapshot that would be identical to the
newest of its store is not taken, and the run says so, so a timer that fires while you are away costs almost nothing and uses none of the 60.

Every snapshot has a number, `#1`, `#2`, ... in its store, which only grows (a dropped snapshot's number is not reused). The clock decides when a snapshot is taken (whether this week already has its weekly one) and never
what is deleted: only the count does. A clock that jumps forward or back can cause one snapshot too many or too few, and each snapshot taken drops at most one old one; so a clock that flips back and forth between a wrong date and the right one, run after run, can still replace the six weekly snapshots, one at a time.

## What the workbench deletes

Only the oldest snapshots of the `weekly` and `frequent` stores, one at a time, when a new one makes the store hold more than it keeps: it deletes that snapshot's reference and the files only it held. It never deletes a folder,
and it refuses, with a message and without touching anything, a repository that is a link, a folder without the marker file the workbench wrote in it, and a store that was not made for this project.
The output says which snapshot it dropped. In `manual` it deletes nothing; to drop one yourself (the numbers are written with eight digits):

```sh
git --git-dir=$HOME/.snapshots/NAME-HASH/manual update-ref -d refs/snapshots/00000003
git --git-dir=$HOME/.snapshots/NAME-HASH/manual prune --expire=now
```

A reference you add yourself (say `git update-ref refs/keep/before-rewrite <id>`) keeps its snapshot's files from being pruned, and a name under `refs/snapshots/` that is not eight digits is left alone. If you run `git gc` on a store, its files are packed, and the files of snapshots dropped afterwards are no longer freed (they only take space); the stores need no `gc`.

## What is in a snapshot

Every file and link of the project, except:

- Git's own folders (`.git`), and `.latex-ai/artifacts/` and `.latex-ai/backups/`, which are the running workbench's state and the installer's backups (the vendored runtime itself is kept);
- the compiler's files (`.aux`, `.log`, `.out`, `.toc`, `.fls`, `.fdb_latexmk`, `.bbl`, `.blg`, `.bcf`, `.run.xml`, `.synctex`, `.synctex.gz`, lists such as `.lof`, `.lot`, `.loa`, `.lol`, `.loe`, `.thm`, index and glossary files,
  slide auxiliaries `.nav`, `.snm`, `.vrb`, and `.dvi`/`.xdv`) that lie beside a `.tex` file of the same name (a `train.log`, a `solver.out` or a `refs.bbl`
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

In `~/.snapshots/NAME-HASH/`, where `NAME` is the project folder's name and `HASH` is eight hexadecimal digits of a hash of its full path (two projects with the same name do not share a folder); inside it, a folder for each store.
`LATEX_AI_SNAPSHOT_DIR` names another folder instead of `~/.snapshots`; it cannot be inside the project. To free the space of one project, delete its folder yourself.
`~/.snapshots` also holds a `.latex-ai/` with the lock files: one snapshot of a project is taken at a time (a second one for the same project, the timers of one project starting together for example, waits up to a minute for the first, and says so if it is still running); other projects do not wait for it.
The file inventory is collected after taking that lock, so files created while waiting are included.
Folders called `fine-*` and `daily-*` in a project's folder belong to the release before this one (4.7.0); they are not read or touched, and can be deleted by hand.

## Restoring

`make snapshots` ends with commands like these, written out for the newest snapshot (for another, use its id and the repository of its store, the folder of that name in `NAME-HASH`):

```sh
git --git-dir=$HOME/.snapshots/NAME-HASH/frequent --work-tree=/path/to/project diff ID --stat      # what changed since it
git --git-dir=$HOME/.snapshots/NAME-HASH/frequent --work-tree=/path/to/project checkout ID -- FILE # one file back
git --git-dir=$HOME/.snapshots/NAME-HASH/frequent --work-tree=/path/to/project checkout ID -- .    # every file it has
```

Restoring writes files into the project and nothing else. `checkout ID -- .` overwrites what you have edited since, so run `make snapshot` first if those edits matter. A file made after the snapshot stays where it is:
delete it by hand if it is not wanted. A project with its own Git sees the restored files as ordinary changes. The snapshots are plain Git repositories, so `git --git-dir=... show`, `ls-tree` and `for-each-ref` work on them.

## Timers on a Mac (launchd)

**Untested.** This was written where launchd could not be run. The two files below are checked to be valid property lists, and the command each runs is checked to work and to fill the right store; how launchd
treats them on your Mac is not. Run the command by hand first, then load the agents, then look at the log.

The agents run while you are logged in and the Mac is awake (a locked screen does not stop them). If it sleeps through a start, launchd runs the job once when it wakes (several missed starts become one); if it was switched off, nothing runs until the next start, and
`RunAtLoad` makes the job run when you log in, so the first run after switching on is not a day late. The weekly agent starts every day and the program decides whether the week already has its snapshot,
so a week with no changes gives none and the first day of a week with changes gives one.

1. **Find a Python 3.10 or newer** and its full path (`command -v python3` in the terminal where `make check` works). `/usr/bin/python3` is only right if it is new enough. Replace it in both files, and put the
   folder of your `git` in `PATH` if it is not in the default one (launchd starts jobs with a short `PATH`).
2. **Make the two files** in `~/Library/LaunchAgents/`, replacing `YOU`, `PATH/TO/PROJECT` and `PROJECT` (one pair for each project):

`local.latex-ai.snapshot.frequent.PROJECT.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>local.latex-ai.snapshot.frequent.PROJECT</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/Users/YOU/PATH/TO/PROJECT/.latex-ai/workbench.py</string>
    <string>snapshot</string>
    <string>--tier</string>
    <string>frequent</string>
    <string>--project</string>
    <string>/Users/YOU/PATH/TO/PROJECT</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>StartInterval</key><integer>1800</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/Users/YOU/Library/Logs/snapshot-PROJECT.log</string>
  <key>StandardErrorPath</key><string>/Users/YOU/Library/Logs/snapshot-PROJECT.log</string>
</dict>
</plist>
```

`local.latex-ai.snapshot.weekly.PROJECT.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>local.latex-ai.snapshot.weekly.PROJECT</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/Users/YOU/PATH/TO/PROJECT/.latex-ai/workbench.py</string>
    <string>snapshot</string>
    <string>--tier</string>
    <string>weekly</string>
    <string>--project</string>
    <string>/Users/YOU/PATH/TO/PROJECT</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/Users/YOU/Library/Logs/snapshot-PROJECT.log</string>
  <key>StandardErrorPath</key><string>/Users/YOU/Library/Logs/snapshot-PROJECT.log</string>
</dict>
</plist>
```

3. **Load them**, and look: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.latex-ai.snapshot.frequent.PROJECT.plist` (and the weekly one), then `make snapshots` in the project, and the log. To stop one:
   `launchctl bootout gui/$(id -u)/local.latex-ai.snapshot.frequent.PROJECT`.

macOS protects some folders (`~/Documents`, `~/Desktop`, `~/Downloads`, iCloud Drive, external drives) from background jobs unless the program has been given access (System Settings, Privacy and Security,
Full Disk Access, for the Python you named). A snapshot that cannot read a folder stops with an error naming it, in the log, and does not leave it out; keep the project elsewhere or grant the access.

## Needs

Git on the `PATH` (the snapshots are Git repositories). The repositories use an identity of their own and none of your Git settings, hooks or templates.
A project without the Makefile targets can use the distribution directly after
opting in through its configuration: `python3 /path/to/workbench/runtime.py snapshot --project /path/to/project`.
