# Uriel maintainer playbook

This is the repeatable local-to-GitHub workflow for `https://github.com/dmonsta86/uriel`.

## 1. Update the local copy safely

```powershell
$Repo = 'C:\path\to\uriel'
Set-Location $Repo
git switch main
git pull --ff-only
git status
```

Do not continue unless the working tree is clean.

## 2. Create an isolated maintenance branch

```powershell
git switch -c maintenance/SHORT-DESCRIPTION
```

Examples:

```text
maintenance/cross-platform-ci
maintenance/readme-blessing-explanation
maintenance/release-candidate-1
```

## 3. Create or refresh a local build environment

```powershell
py -3 -m venv .maintainer-venv
.\.maintainer-venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel build
python -m pip install -e .
```

The environment is local and should remain ignored by Git.

## 4. Run the fast checks while editing

```powershell
python -m compileall -q src tests scripts examples
python -m unittest discover -s tests -v
python scripts\privacy_sweep.py
```

## 5. Run the complete release check before committing

```powershell
python scripts\release_check.py --full
```

The expected ending is:

```text
RESULT: PASS
STATUS: PASS
```

A failure because `setuptools`, `wheel`, or `build` is missing means the maintainer environment is incomplete. Install the build tools; do not weaken the release check.

## 6. Review exactly what changed

```powershell
git status --short
git diff --check
git diff --stat
git diff
```

Check especially for local paths, private application notes, credentials, generated state, and stale URLs.

## 7. Commit the branch

```powershell
git add -A
git diff --cached --check
git diff --cached --stat
git commit -m "TYPE: concise description"
```

Examples:

```text
ci: harden cross-platform test execution
docs: explain the Three Gates and Blessing
fix: preserve confinement semantics on macOS
```

## 8. Push without rewriting history

```powershell
git push -u origin HEAD
```

Open a pull request or merge only after the branch CI is green. Never use `--force` on `main` for ordinary maintenance.

## 9. Inspect GitHub Actions from PowerShell

List recent runs:

```powershell
gh run list --repo dmonsta86/uriel --branch main --limit 10
```

View failed steps from a run:

```powershell
gh run view RUN_ID --repo dmonsta86/uriel --log-failed
```

Watch a run:

```powershell
gh run watch RUN_ID --repo dmonsta86/uriel --compact --exit-status
```

Rerun only failed jobs after a transient infrastructure error:

```powershell
gh run rerun RUN_ID --repo dmonsta86/uriel --failed
```

Do not rerun repeatedly when the same deterministic code error appears; fix the code or workflow first.

## 10. Merge and verify the exact public tree

```powershell
git switch main
git pull --ff-only
git status
python scripts\privacy_sweep.py
python scripts\release_check.py --full
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
```

The two hashes must match.

## 11. Tag a release candidate only after the matrix is green

```powershell
git tag -a v1.0.0-rc1 -m "Uriel 1.0.0 release candidate 1"
git push origin v1.0.0-rc1
```

Confirm the release workflow attaches the wheel, source archive, portable `.pyz`, checksums, and release-check transcript.

## 12. Recovery rules

- A failed test or script does not erase committed work.
- Before running a large transformation, commit the current good state or create a branch.
- Use `git diff` before `git restore` or `git reset`.
- Use `git restore --staged --worktree .` only when you intentionally want to discard every uncommitted change.
- Use `git reflog` to locate commits after an accidental branch move.
- Keep the original complete recovery ZIP and Git bundle outside the repository.
- Keep Git Credential Manager credentials unless they are stale, compromised, or belong to the wrong account.
