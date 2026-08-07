# ADR 0008: The Forge of Uriel Public Identity & Documentation Pass

- **Status**: Accepted
- **Date**: 2026-08-07
- **Authors**: AI Assistant & Daniel Esquivel (Maintainer)

## Context
Wave U7 establishes the public product display name **The Forge of Uriel** while preserving complete backward compatibility for the Python package (`uriel`), CLI command (`uriel`), repository name (`uriel`), repository URLs (`https://github.com/dmonsta86/uriel`), and schema IDs.

To ensure non-destabilization of earlier feature branches, this wave is isolated on a dedicated feature branch `feature/uriel-forge-public-identity`.

## Decision
1. Create and isolate all public branding, README, QRD, Forge Method docs, capability status artifacts, metadata updates, and fail-closed public identity checks on branch `feature/uriel-forge-public-identity`.
2. Maintain backward compatibility for all runtime names (`uriel`), CLI commands, package entry points, and existing schema specifications.
3. Establish **The Forge Method** and **The Blessing of Uriel** as core closure and verification protocols.
4. Restrict named online AI model recommendations in public documentation strictly to the maintainer-recommended model (see `docs/AI_USAGE_AND_PRIVACY.md`) accompanied by all required non-dependency and privacy disclaimers.

## Consequences
- Clean separation of public branding changes without breaking low-level API/CLI contracts.
- Automated fail-closed identity verification prevents accidental provider/brand regression in future release builds.
