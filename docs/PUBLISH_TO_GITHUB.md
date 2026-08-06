# Publish Uriel to GitHub without losing progress

No browser extension is required, and no one should ask you to send a password, cookie, recovery code, or personal access token. The safest low-effort routes use GitHub Desktop or GitHub CLI's official browser sign-in.

## Route A — GitHub Desktop, almost no terminal use

1. Create or sign in to a GitHub account and make the profile public if you intend to apply to Codex for Open Source.
2. Install **GitHub Desktop** from its official site.
3. Download and extract the Uriel **GitHub-ready source ZIP**. Keep the extracted folder somewhere permanent, such as `Documents\GitHub\uriel`.
4. Open GitHub Desktop and choose **File → Add local repository**. Select the extracted `uriel` folder.
5. If Desktop says it is not a Git repository, choose **create a repository here**. Use `uriel` as the repository name.
6. Commit all files with the message `Initial public release candidate for Uriel 1.0.0`.
7. Click **Publish repository**. Clear **Keep this code private**, then publish.
8. Open the repository's **Actions** tab in the browser. Do not claim the OS/Python matrix passed until all jobs are green.

This route records the first commit under the GitHub identity configured in GitHub Desktop.

## Route B — one Windows launcher

Extract the Uriel GitHub-ready source ZIP and double-click:

```text
PUBLISH_TO_GITHUB.cmd
```

If Git, GitHub CLI, or Python 3.12 is missing, the launcher offers to install the official winget packages. It then opens GitHub's official browser/device-code sign-in, binds package metadata to `YOUR-ACCOUNT/uriel`, runs the local verification suite, initializes Git if necessary, commits under the authenticated account's GitHub noreply identity, creates the repository, pushes `main`, enables Issues, and opens the result. It never collects a password, token, cookie, or recovery code.

The PowerShell command is also available directly:

```powershell
.\scripts\publish_github.ps1 -Repository uriel -Visibility public -OpenInBrowser
```

The recovery Git bundle may contain the neutral bootstrap identity used to
construct the release candidate. The publisher replaces that placeholder for
new commits with the authenticated GitHub account's noreply identity. To make
the entire public history begin under your own account, use the GitHub-ready
source ZIP rather than cloning the recovery bundle.

## Route C — macOS or Linux

Install Git and GitHub CLI, extract the source ZIP, then run:

```console
./scripts/publish_github.sh uriel
```

## After the first push

1. Confirm the full CI matrix is green.
2. Review the public tree for names, email addresses, unpublished data, private paths, credentials, and hostnames.
3. Create a release-candidate tag:

```console
git tag -a v1.0.0-rc1 -m "Uriel 1.0.0 release candidate 1"
git push origin v1.0.0-rc1
```

The release workflow builds and attaches the wheel, source distribution, portable `.pyz`, SHA-256 checksums, and the persisted release-check transcript.

4. Enable **Private vulnerability reporting** under **Settings → Security → Code security and analysis**.
5. Confirm `pyproject.toml` and `CITATION.cff` contain the actual repository URL; the CLI publisher configures these automatically.
6. Open two or three honest starter Issues: field-validation pilots, false-positive fixtures, and an independent threat-model review are good first tasks.
7. Apply to Codex for Open Source only with public, verifiable facts. A new repository should describe ecosystem importance and the maintenance work ahead, not invent adoption.

## Recovery rule

Keep three independent copies until GitHub is confirmed:

- the source ZIP;
- the Git bundle;
- the extracted working folder.

A failed authentication or push does not delete or rewrite the source files. Re-running the publishing script is safe after correcting the reported issue.
