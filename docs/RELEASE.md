# Release procedure

A release is evidence about one exact commit. Do not tag first and hope the checks become green afterward.

## 1. Verify the canonical candidate

```console
git switch main
git status
git worktree list
```

The canonical 215 product line is this `main` worktree. Do not create a second
canonical copy or move the existing `v1.0.0-rc2` tag. If a remote update is
needed, inspect the local relation and obtain operator approval before fetching
or pulling. Do not continue from a dirty or unexpected worktree.

## 2. Run the complete local release check

Create or refresh a build environment and install build-only tooling:

```console
python -m venv .maintainer-venv
python -m pip --python .maintainer-venv install --upgrade pip "setuptools>=77" wheel build
```

On platforms whose `pip` does not support `--python`, activate the environment or invoke its Python directly.

Run the deterministic suite:

```console
python scripts/release_check.py --full --command-timeout 600
```

The check compiles the source, runs the standard-library tests and privacy sweep, builds the wheel, source distribution, and portable archive, creates checksums, installs the wheel into a fresh environment, checks both entry points and dependencies, and verifies packaged schemas.

Expected ending:

```text
STATUS: PASS
RESULT: PASS
```

A failure caused by missing `setuptools`, `wheel`, or `build` means the maintainer environment is incomplete. Install the build tools; do not weaken the release check.

## 3. Inspect the exact change

```console
git status --short
git diff --check
git diff --stat
git diff
```

Check for local paths, private application notes, credentials, generated `.uriel` state, stale repository URLs, and claims that exceed the evidence.

## 4. Commit the candidate and use the approved review route

```console
git add -A
git diff --cached --check
git commit -m "release: prepare exact reviewed candidate"
```

An operator may push the exact reviewed commit through the approved public
review route. Open a pull request or use the repository's authorized main-line
release route and wait for every mandatory compatibility and package job. A
local pass proves only the local environment. The public matrix is the
compatibility record for the proposed commit.

## 5. Merge and verify the public tree

After the pull request is green and merged:

```console
git switch main
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
python scripts/privacy_sweep.py
python scripts/release_check.py --full --command-timeout 600
```

The two commit hashes must match and the working tree must be clean.

## 6. Create the release-candidate tag

```console
git tag -a vX.Y.Z-rcN -m "Uriel release candidate"
git push origin vX.Y.Z-rcN
```

Use the exact reviewed candidate version. Tagging and pushing are
operator-approved external actions; never move or overwrite an existing tag.

The release workflow should build and attach:

- the wheel;
- source distribution;
- portable `.pyz`;
- `SHA256SUMS.txt`;
- persisted `release-check.txt` verification transcript.

Inspect the GitHub Release and download the attached files once to verify that the expected artifacts are present.

## Before a stable tag

1. Update `src/uriel/version.py`, `pyproject.toml`, `CHANGELOG.md`, and `CITATION.cff` together.
2. Confirm the valid fixture passes the submission profile, issues a Blessing, and verifies independently.
3. Confirm incomplete and tampered fixtures refuse constructively.
4. Confirm every advertised compatibility job passes on the exact proposed commit.
5. Review open false-positive, false-negative, security, accessibility, and portability issues.
6. Use a signed Git tag where the maintainer's setup supports it.
7. Do not publish to PyPI until the distribution name, ownership, trusted publisher, and repository URLs are finalized.
8. Do not promote an RC to stable merely because packaging works; seek real external use and document known audit limitations.

## Resume after an interrupted local full check

The release checker writes `release-check.txt` after every command and uses a process lock. If interruption occurred after current distributions were built, resume with:

```console
python scripts/release_check.py --full --reuse-artifacts --command-timeout 600
```

Reuse is accepted only when `dist/BUILD_INPUT_SHA256` still matches the current source tree. Tests and the privacy sweep run again before portable, fresh-install, entry-point, dependency, and packaged-schema checks continue.

## Interruption safety

When Uriel receives SIGINT, SIGTERM, SIGHUP, or Windows SIGBREAK while an external check is active, it stops that child process tree and leaves `STATUS: INTERRUPTED` in `release-check.txt`. An abrupt power loss or forced OS kill cannot run cleanup code, but the last atomic checkpoint remains and the operating system releases the lock. Inspect the report, then rerun the same command.
