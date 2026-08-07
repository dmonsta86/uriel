# Compatibility and support policy

## Design target

Uriel’s trusted runtime is written for CPython 3.9 or newer and has no third-party runtime dependencies. The intended desktop/server targets are:

- Linux x86-64;
- Windows x86-64, including Windows PowerShell 5.1+ wrappers;
- macOS Intel x86-64;
- macOS Apple Silicon arm64 for current Python versions;
- any other platform where the standard-library filesystem, SQLite, hashing, ZIP, subprocess, and atomic-replace behavior meets Uriel’s tests.

## What “supported” means

A platform is not supported merely because it appears in this document. Public support is earned when the current commit passes the corresponding GitHub Actions job.

The main compatibility matrix tests Python 3.9 through 3.14 on:

- `ubuntu-latest` x86-64;
- `windows-latest` x86-64;
- `macos-15-intel` x86-64.

A separate smoke matrix tests current Python versions on `macos-latest` arm64. Older CPython releases are tested on an Intel macOS runner because GitHub’s arm64 images do not retain every older Python build.

## Why the macOS runners are explicit

GitHub currently maps `macos-latest` to an arm64 runner, while `macos-15-intel` and `macos-26-intel` are explicit Intel labels. Architecture affects which Python builds are available. Uriel therefore tests the complete declared version range on Intel and tests Apple Silicon separately rather than pretending one floating label proves both architectures.

## Release policy

Before tagging a release candidate:

1. all mandatory x86-64 matrix jobs must be green;
2. the package job must build the wheel, source distribution, portable zipapp, checksums, and verification transcript;
3. the privacy sweep and full release check must pass on the exact tagged tree;
4. known Apple Silicon failures must be documented rather than hidden;
5. the README must not claim more compatibility than the public matrix demonstrates.

## Local verification

Windows PowerShell:

```powershell
py -3 -m venv .maintainer-venv
.\.maintainer-venv\Scripts\Activate.ps1
python -m pip install --upgrade pip "setuptools>=77" wheel build
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts\privacy_sweep.py
python scripts\release_check.py --full
```

macOS or Linux:

```bash
python3 -m venv .maintainer-venv
. .maintainer-venv/bin/activate
python -m pip install --upgrade pip 'setuptools>=77' wheel build
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/privacy_sweep.py
python scripts/release_check.py --full
```

A local pass proves only that local environment. GitHub Actions provides the public cross-platform record.
