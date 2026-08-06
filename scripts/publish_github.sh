#!/usr/bin/env sh
set -eu

REPOSITORY="${1:-uriel}"
VISIBILITY="${URIEL_GITHUB_VISIBILITY:-public}"
DESCRIPTION="Offline-first research integrity harness, Three-Gate auditor, and SHA-256 provenance ledger"
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

fail() {
  printf '%s\n' "$*" >&2
  printf '%s\n' "No Uriel source files were deleted." >&2
  exit 1
}

command -v git >/dev/null 2>&1 || fail "git is required."
command -v gh >/dev/null 2>&1 || fail "GitHub CLI is required. Install it from the official GitHub CLI package."

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  fail "Python 3.9+ is required."
fi

case "$REPOSITORY" in
  *[!A-Za-z0-9._-]*|'') fail "Repository must contain only letters, numbers, periods, underscores, or hyphens." ;;
esac
case "$VISIBILITY" in
  public|private|internal) ;;
  *) fail "URIEL_GITHUB_VISIBILITY must be public, private, or internal." ;;
esac

if ! gh auth status >/dev/null 2>&1; then
  printf '%s\n' "GitHub will open its official browser/device-code sign-in."
  printf '%s\n' "This script never asks for a password, token, cookie, or recovery code."
  gh auth login --web --git-protocol https || fail "GitHub authentication did not complete."
fi
gh auth setup-git || fail "Git credential setup failed."

OWNER=$(gh api user --jq '.login')
USER_ID=$(gh api user --jq '.id')
[ -n "$OWNER" ] && [ -n "$USER_ID" ] || fail "Could not determine the authenticated GitHub account."
SLUG="$OWNER/$REPOSITORY"
EXPECTED_ORIGIN="https://github.com/$SLUG.git"

printf '%s\n' "Binding release metadata to https://github.com/$SLUG"
"$PYTHON" scripts/configure_repository.py --slug "$SLUG" || fail "Repository metadata configuration failed."

printf '%s\n' "Running the offline Uriel release check before any push..."
"$PYTHON" scripts/release_check.py || fail "Local release check failed."

if [ ! -d .git ]; then
  git init -b main 2>/dev/null || { git init && git branch -M main; } || fail "git init failed."
else
  git branch -M main || fail "Could not select the main branch."
fi

CURRENT_NAME=$(git config --local user.name 2>/dev/null || true)
CURRENT_EMAIL=$(git config --local user.email 2>/dev/null || true)
case "$CURRENT_NAME" in
  ''|'Uriel Bootstrap') git config --local user.name "$OWNER" || fail "Could not configure the Git author name." ;;
esac
case "$CURRENT_EMAIL" in
  ''|uriel-bootstrap@example.invalid|*@example.invalid)
    git config --local user.email "$USER_ID+$OWNER@users.noreply.github.com" || fail "Could not configure the Git author email."
    ;;
esac

normalize_remote() {
  printf '%s' "$1" \
    | sed -e 's#^git@github\.com:#https://github.com/#' \
          -e 's#^ssh://git@github\.com/#https://github.com/#' \
          -e 's#/*$##' \
          -e 's#\.git$##' \
    | tr '[:upper:]' '[:lower:]'
}

ORIGIN=""
if git remote get-url origin >/dev/null 2>&1; then
  ORIGIN=$(git remote get-url origin)
  if [ "$(normalize_remote "$ORIGIN")" != "$(normalize_remote "$EXPECTED_ORIGIN")" ]; then
    fail "The existing origin points to '$ORIGIN', not '$EXPECTED_ORIGIN'. Remove or rename that remote before publishing."
  fi
fi

git add --all || fail "git add failed."
if ! git diff --cached --quiet; then
  if git rev-parse --verify HEAD >/dev/null 2>&1; then
    git commit -m "Prepare Uriel for public GitHub release" || fail "git commit failed."
  else
    git commit -m "Initial public release candidate for Uriel 1.0.0" || fail "git commit failed."
  fi
fi

if [ -z "$ORIGIN" ]; then
  if gh repo view "$SLUG" >/dev/null 2>&1; then
    git remote add origin "$EXPECTED_ORIGIN" || fail "Could not add origin."
  else
    gh repo create "$SLUG" "--$VISIBILITY" --description "$DESCRIPTION" --source "$ROOT" --remote origin \
      || fail "GitHub repository creation failed."
  fi
fi

git push -u origin main || fail "Push failed. Review the error above."
gh repo edit "$SLUG" --enable-issues=true --enable-wiki=false >/dev/null 2>&1 || true
printf '\nPublished: https://github.com/%s\n' "$SLUG"
printf '%s\n' "Open Actions and confirm every CI job is green before tagging a release."
printf '%s\n' "Then run: git tag -a v1.0.0-rc1 -m 'Uriel 1.0.0 release candidate 1' && git push origin v1.0.0-rc1"
