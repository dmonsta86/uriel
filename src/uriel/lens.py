"""Zero-install Uriel Lens and Seed prompt distribution.

Ships the advisory copy-paste prompts from the ``lens_zero_install`` pack as
package data so ``uriel lens`` can print them on any machine without an
installer or an AI provider.  Lens reviews are read-only and advisory; they
can never issue a Blessing.  The shipped files are hash-verified against the
pack manifest on every read (fail-closed on drift).
"""
from __future__ import annotations

import hashlib
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Mapping

from .core import Refusal

LENS_PACKAGE = "uriel.data.lens"

#: Relative path -> expected SHA-256, transcribed from the pack SHA256SUMS.txt.
MANIFEST: Dict[str, str] = {
    "COPY_THIS_ONE.txt": "ef58aba9f68e2d78f229b39b1c87e43516722c0b8c6c50e11eaa05550640ac68",
    "URIEL_LENS_COMPACT.txt": "ef58aba9f68e2d78f229b39b1c87e43516722c0b8c6c50e11eaa05550640ac68",
    "URIEL_LENS_FULL.md": "31a8ea7487db140bae12962df7eeda30df76b19a881229e5512c34ab54054b19",
    "URIEL_SEED_PROMPT.txt": "969a359e6d332aefb8cbeef4cfb296ade1006a73f00c89f182d9740cee96e974",
    "uriel-lens-skill.md": "112cda2fe0ccb136301539186564e7ed26053200d2e0323a85ecfac333a206db",
    "EXAMPLE_REVIEW.md": "1081a7599ae1d0a9432f3e89730194ae1e5e951ace2a3cf298a4a3c4b73b7d31",
    "LICENSE": "1eac23f8fa72fa3698434403c470f412191ffd6ba3f22325e3327a08b38a6c27",
}

NAMES = ("compact", "full", "seed", "skill", "example", "copy_this_one")


def _asset_bytes(name: str) -> bytes:
    resource = resources.files(LENS_PACKAGE).joinpath(name)
    try:
        raw = resource.read_bytes()
    except (OSError, FileNotFoundError, IsADirectoryError) as exc:
        raise Refusal(
            "Lens asset {0} is missing from the installation.".format(name),
            code="LENS_ASSET_MISSING",
            repairs=["Reinstall or rebuild the package; the lens data files ship inside the wheel."],
        ) from exc
    digest = hashlib.sha256(raw).hexdigest()
    expected = MANIFEST.get(name)
    if expected is None:
        raise Refusal(
            "Lens asset {0} is not covered by the pack manifest.".format(name),
            code="LENS_ASSET_UNVERIFIED",
        )
    if digest != expected:
        raise Refusal(
            "Lens asset {0} failed its SHA-256 check.".format(name),
            code="LENS_ASSET_DRIFT",
            repairs=["Do not use a modified Lens prompt as if it were the reviewed pack."],
        )
    return raw


def asset_hashes() -> Dict[str, str]:
    """Return the manifest (name -> sha256) for the shipped lens pack."""
    return dict(MANIFEST)


def lens_names() -> List[str]:
    """Return the selectable lens asset names."""
    return list(NAMES)


def lens_prompt(name: str) -> str:
    """Return the verified text of one lens asset."""
    mapping = {
        "compact": "URIEL_LENS_COMPACT.txt",
        "copy_this_one": "COPY_THIS_ONE.txt",
        "full": "URIEL_LENS_FULL.md",
        "seed": "URIEL_SEED_PROMPT.txt",
        "skill": "uriel-lens-skill.md",
        "example": "EXAMPLE_REVIEW.md",
    }
    filename = mapping.get(name)
    if filename is None:
        raise Refusal(
            "Unknown Lens asset '{0}'.".format(name),
            code="LENS_UNKNOWN_ASSET",
            repairs=[
                "Choose one of: {0}.".format(", ".join(NAMES)),
                "Run `uriel lens --which compact` for the recommended copy-paste prompt.",
            ],
        )
    return _asset_bytes(filename).decode("utf-8")


def write_lens(root: Path, name: str, output: Path) -> Dict[str, Any]:
    """Write one verified lens asset to an output path (atomic, no overwrite)."""
    if output.exists():
        raise Refusal(
            "Refusing to overwrite existing file {0}.".format(output),
            code="LENS_OUTPUT_EXISTS",
            repairs=["Choose a different --output path or remove the existing file first."],
        )
    text = lens_prompt(name)
    target = Path(output).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(text.encode("utf-8"))
    temporary.replace(target)
    return {
        "asset": name,
        "output": str(target),
        "sha256": MANIFEST[{
            "compact": "URIEL_LENS_COMPACT.txt",
            "copy_this_one": "COPY_THIS_ONE.txt",
            "full": "URIEL_LENS_FULL.md",
            "seed": "URIEL_SEED_PROMPT.txt",
            "skill": "uriel-lens-skill.md",
            "example": "EXAMPLE_REVIEW.md",
        }[name]],
        "bytes": len(text.encode("utf-8")),
        "advisory_only": True,
        "note": "Lens is a read-only advisory review and cannot issue a Blessing.",
    }
