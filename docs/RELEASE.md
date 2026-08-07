# Release procedure

## Local release check

Run the deterministic checks and build the portable archive:

```console
python scripts/release_check.py --full
```

Build wheel and source distributions without modifying the working tree:

```console
python scripts/build_distributions.py --clean
python scripts/build_portable.py
python scripts/make_checksums.py
```

Install the wheel into a fresh virtual environment and smoke-test it:

```console
python -m venv .release-venv
.release-venv/bin/python -m pip install --no-deps --no-index dist/uriel_research-1.0.0-py3-none-any.whl
.release-venv/bin/python -m uriel --version
```

PowerShell uses `.release-venv\Scripts\python.exe` instead.

## Publish a release candidate

Before tagging a release candidate:

1. confirm the working tree is clean and `main` matches `origin/main`;
2. run `python scripts/release_check.py --full`;
3. confirm the public GitHub Actions matrix is green;
4. run the privacy sweep again on the exact public tree.

Then create and push the annotated tag:

```console
git tag -a v1.0.0-rc1 -m "Uriel 1.0.0 release candidate 1"
git push origin v1.0.0-rc1
```

The release workflow builds and attaches the wheel, source distribution, portable `.pyz`, `SHA256SUMS.txt`, and the persisted `release-check.txt` verification transcript.

## Before a stable tag

1. Update `src/uriel/version.py`, `pyproject.toml`, `CHANGELOG.md`, and `CITATION.cff` together.
2. Confirm the valid fixture passes the submission profile, issues a Blessing, and verifies independently.
3. Confirm incomplete and tampered fixtures refuse constructively.
4. Confirm Linux, Windows, and macOS jobs passed for every advertised Python version.
5. Review open false-positive, security, and portability issues.
6. Use a signed Git tag where the maintainer's setup supports it.
7. Do not publish to PyPI until the distribution name, ownership, trusted publisher, and repository URLs are finalized.

## Resume after an interrupted local full check

The release checker writes `release-check.txt` after every command and uses a process lock. If interruption occurred after current distributions were built, resume with:

```console
python scripts/release_check.py --full --reuse-artifacts
```

Reuse is accepted only when `dist/BUILD_INPUT_SHA256` still matches the current source tree. Tests and the privacy sweep run again before portable, fresh-install, entry-point, dependency, and packaged-schema checks continue.

## Interruption safety

When Uriel receives SIGINT, SIGTERM, SIGHUP, or Windows SIGBREAK while an external check is active, it stops that child process tree and leaves `STATUS: INTERRUPTED` in `release-check.txt`. An abrupt power loss or forced OS kill cannot run cleanup code, but the last atomic checkpoint remains and the operating system releases the lock; inspect the report, then rerun the same command.
