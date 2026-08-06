# Portable Uriel

The portable archive is the accessible “app without an installer” option. It contains the same Python package as the normal CLI and has no third-party runtime dependency.

## Build

```console
python scripts/build_portable.py
```

Output:

```text
dist/uriel.pyz
```

## Run

Windows:

```powershell
py -3 .\uriel.pyz --version
py -3 .\uriel.pyz intake "YOUR QUESTION" --root .\my-project
```

Linux/macOS:

```console
python3 uriel.pyz --version
python3 uriel.pyz intake "YOUR QUESTION" --root ./my-project
```

The archive does not bundle Python itself. A later native-binary experiment may use PyInstaller or a Rust launcher, but that would no longer be zero-dependency at build time and would require separate platform releases. The zipapp is transparent, reproducible, and inspectable with any ZIP tool.

## Verify the distributed file

Release artifacts include `SHA256SUMS`. On Linux/macOS:

```console
sha256sum -c SHA256SUMS
```

On PowerShell:

```powershell
Get-FileHash .\uriel.pyz -Algorithm SHA256
```
