# Security Policy

## Supported versions

Security fixes are applied to the latest supported public release and current
development branch as stated in the release notes.

## Report privately

Do not open a public issue for a suspected vulnerability.

Use GitHub's private vulnerability-reporting flow from the repository Security
page when enabled. Otherwise use the private contact method listed by the
maintainer in this file.

Include:

- affected version and commit;
- operating system and installation type;
- exact reproduction;
- security impact;
- minimal synthetic proof;
- logs or receipts without credentials or private research;
- whether the problem permits source writes, path escape, code execution,
  authority bypass, privacy loss, archive escape, or supply-chain compromise.

## Research boundaries

Test only systems and data you own or are authorized to test.

Do not upload participant data, unpublished third-party manuscripts, credentials
or restricted research in a report.

## Coordinated disclosure

Please allow maintainers time to reproduce and prepare a fix before public
disclosure. Uriel does not currently offer a bug bounty.

## Scope

Examples include:

```text
path confinement bypass
unsafe symlink/junction/archive behavior
arbitrary code execution
credential or private-data exposure
hidden network behavior
Gate/Blessing/authority bypass
tamper-verification bypass
dependency or release-workflow compromise
```
