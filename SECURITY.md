# Security policy

## Supported version

Security fixes are applied to the latest release branch. Version 1.0.x is currently supported.

## Report privately

Do not open a public issue for a vulnerability that could enable path escape, arbitrary command execution, forged receipts, forged Blessings, ledger bypass, secret disclosure, unsafe archive extraction, or deletion outside a project root.

Until a dedicated security advisory address is configured, use GitHub's **Report a vulnerability** feature after the repository is published. The maintainer should enable Private Vulnerability Reporting under repository security settings before announcing the project.

Include:

- affected version and operating system;
- minimal reproduction inside a disposable directory;
- files or paths touched;
- expected and actual behavior;
- whether a Blessing or verification result can be forged;
- suggested mitigation, if known.

Never include real confidential research data in a report. Use synthetic fixtures and hashes.

## Security invariants

Uriel's trusted core must preserve these invariants:

- every managed path is confined beneath one canonical, non-linked root;
- source enumeration never follows links;
- workloads execute an explicit argv vector with `shell=False`;
- source, receipt, audit, ledger, and Blessing hashes fail closed;
- external model output cannot pass a Gate or issue a Blessing;
- a Blessing binds the exact audited source state and policy version;
- uninstall or cleanup code never targets a parent, sibling, checkout root, home directory, or inferred path;
- no provider credential is written into project state or a Blessing package.
