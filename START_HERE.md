# Start here: put Uriel on your GitHub safely

You do **not** need a browser extension, API key, paid AI plan, or GitHub token pasted into a script.

## Easiest Windows route

1. Extract this source folder somewhere permanent, such as `Documents\GitHub\uriel`.
2. Double-click **`PUBLISH_TO_GITHUB.cmd`**.
3. Allow it to install missing official tools through Windows Package Manager if you choose.
4. Complete GitHub CLI's official browser/device sign-in.
5. The launcher will bind the repository URL, run local checks, create `YOUR-ACCOUNT/uriel`, commit the source under your GitHub noreply identity, and push `main`.
6. In the opened GitHub page, select **Actions** and confirm every job is green.

The launcher never asks you to paste a password, personal access token, browser cookie, or recovery code. A failed login, check, or push does not delete the source folder.

## No-terminal alternative

Use GitHub Desktop and follow [`docs/PUBLISH_TO_GITHUB.md`](docs/PUBLISH_TO_GITHUB.md). It is slower by a few clicks but equally valid.

## macOS or Linux

Install Git, Python 3.9+, and GitHub CLI, then run:

```console
./scripts/publish_github.sh uriel
```

## Recovery rule

Keep the original ZIP until the public repository and its Actions page are visible. The release package should also include a Git bundle and SHA-256 checksums, giving you independent recovery paths even if a browser, model session, or upload fails.
