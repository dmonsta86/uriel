# Applying to Codex for Open Source

Official form: https://openai.com/form/codex-for-oss/

This guide was checked on **2026-08-06**. Reopen the form before submitting because program terms and fields may change.

## Current program summary

The current page says maintainers of active open-source projects may apply. It looks for meaningful usage, broad adoption, or clear ecosystem importance and evidence of active maintenance. Selected maintainers receive six months of ChatGPT Pro including Codex, may receive API credits for core OSS work, and qualified repositories may be considered for conditional Codex Security access. Applications are reviewed on a rolling basis.

## Current required preparation

Before applying:

1. publish this repository under an OSI-approved license;
2. make the GitHub repository public;
3. make the applicant's GitHub profile public;
4. replace every `YOUR-ACCOUNT` placeholder;
5. enable issues, security advisories, and Private Vulnerability Reporting;
6. create the first signed/tagged release and attach `dist/uriel.pyz` plus checksums;
7. ensure CI is green on Windows, Linux, and macOS;
8. add real maintainer activity: issues, responses, review, releases, and roadmap updates;
9. record truthful adoption evidence—never invent stars, downloads, users, citations, or institutional use;
10. locate the OpenAI Organization ID linked from the form.

## Current form fields

- first name;
- last name;
- ChatGPT-account email;
- public GitHub username;
- public GitHub repository URL;
- role: primary or core maintainer;
- why the repository qualifies — maximum 500 characters;
- interest in Codex Security and/or API credits;
- OpenAI Organization ID;
- how credits will be used — maximum 500 characters;
- anything else — maximum 500 characters.

Use `OPENAI_CODEX_FOR_OSS_APPLICATION.md` as a copy-safe worksheet.

## Strengthen the application before submission

Uriel is new. The form explicitly values usage/adoption or clear ecosystem importance, so a persuasive application should show more than a large vision. Good evidence includes:

- reproducible CI and a public threat model;
- a portable no-cost release;
- early issues from real users and documented responses;
- one or more external contributors;
- a demonstration repository with both a failed and earned Blessing;
- journal, lab, librarian, reproducibility, or OSS-maintainer feedback;
- release cadence and a concrete maintenance roadmap;
- a transparent list of what Uriel cannot establish;
- security and privacy practices.

A new project may still apply if it plays an important ecosystem role, but the explanation must be truthful and concrete.

## Appropriate use of requested credits

Credits should accelerate open-source maintenance, not become a hidden dependency of Uriel's scientific decision engine. Appropriate uses include:

- generating and reviewing test fixtures;
- cross-platform bug reproduction;
- schema migration review;
- documentation and issue triage;
- adversarial security review;
- locating candidate primary sources for humans to verify;
- comparing reviewer objections;
- release automation and maintenance tooling.

Core validation, provenance, reminders, and Blessing verification must remain usable offline with zero API spend.
