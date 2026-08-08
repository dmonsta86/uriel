# Release checklist

- [x] Runtime source is de-branded to `.uriel` and `uriel.*` schemas.
- [x] No runtime dependency is declared.
- [x] Portable zipapp build exists.
- [x] GitHub CI workflow is configured for Linux, Windows, and macOS on Python 3.9–3.14, with an Apple Silicon smoke job.
- [x] Tag-triggered release workflow builds wheel, sdist, portable archive, checksums, and the release-check transcript.
- [x] GitHub Desktop and browser-authenticated CLI publishing routes are documented.
- [ ] Verify the remote repository's visibility and maintainer ownership from the exact public account.
- [ ] Confirm no private grant, funding, account, or application drafts are tracked.
- [x] Confirm the repository URL is present in `pyproject.toml` and `CITATION.cff`.
- [ ] Confirm every public CI job passes.
- [x] Build the wheel/sdist locally and install the wheel into a clean virtual environment for CLI and packaged-schema smoke tests.
- [x] Confirm the valid example passes submission audit, issues a Blessing, and verifies independently.
- [x] Confirm incomplete and tampered examples refuse constructively and preserve reminders.
- [ ] Enable Private vulnerability reporting.
- [ ] Create a new release-candidate tag for the exact reviewed commit and inspect its generated GitHub release assets. Do not move the existing `v1.0.0-rc2` tag.
- [ ] Invite at least one independent threat-model review and one research-domain pilot.
- [ ] Publish only after a final privacy sweep of the exact Git tag.

## Interruption safety

When Uriel receives SIGINT, SIGTERM, SIGHUP, or Windows SIGBREAK while an external check is active, it stops that child process tree and leaves `STATUS: INTERRUPTED` in `release-check.txt`. An abrupt power loss or forced OS kill cannot run cleanup code, but the last atomic checkpoint remains and the operating system releases the lock; inspect the report, then rerun the same command.
