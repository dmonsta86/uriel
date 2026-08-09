#!/usr/bin/env python3
"""Run Uriel release checks without requiring network access.

The report is rewritten after every step so an interrupted terminal, agent, or
CI job leaves a precise continuation point. Every subprocess is bounded by a
configurable timeout. An operating-system file lock prevents two release checks
from deleting or rebuilding the same artifacts concurrently.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import BinaryIO, List, Mapping, Optional, Sequence


PRE_BUILD_CHECKS = (
    "scripts/check_community_health.py",
    "scripts/check_public_identity.py",
    "scripts/check_readme.py",
    "scripts/check_i18n.py",
    "scripts/check_localization_integrity.py",
    "scripts/check_capability_status.py",
    "scripts/check_schema_mirror.py",
    "scripts/check_forge_trial.py",
)


class ReleaseInterrupted(Exception):
    """Raised by signal handlers so active child processes can be stopped cleanly."""

    def __init__(self, signum: int) -> None:
        super().__init__(f"release check interrupted by signal {signum}")
        self.signum = signum


def _termination_handler(signum: int, frame: object) -> None:
    del frame
    raise ReleaseInterrupted(signum)


class ReleaseLock:
    """Cross-platform, crash-releasing lock for one repository release check."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: Optional[BinaryIO] = None

    def __enter__(self) -> "ReleaseLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o600)
        self.handle = os.fdopen(descriptor, "r+b", buffering=0)
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                if not self.handle.read(1):
                    self.handle.seek(0)
                    self.handle.write(b" ")
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.handle.close()
            self.handle = None
            raise SystemExit(
                "another Uriel release check is already running for this repository; "
                "let that process finish or terminate it before retrying"
            ) from exc

        metadata = (
            f"pid={os.getpid()}\n"
            f"started_unix={int(time.time())}\n"
            f"python={sys.executable}\n"
        ).encode("utf-8")
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(metadata)
        self.handle.flush()
        os.fsync(self.handle.fileno())
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                # A stale unlocked marker is harmless; the next process can lock it.
                pass


def checkpoint(report: Path, log: Sequence[str], status: str) -> None:
    """Persist the release-check transcript using atomic replacement."""

    report.parent.mkdir(parents=True, exist_ok=True)
    temporary = report.with_name("." + report.name + ".tmp")
    temporary.write_text("\n".join([*log, "", "STATUS: " + status]) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(report))


def _stop_process(process: subprocess.Popen[str]) -> None:
    """Stop a timed-out process and, where supported, its process group."""

    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            # ``terminate()`` only targets the direct child on Windows.  The
            # built-in taskkill utility can terminate its complete descendant
            # tree, preventing a detached build from replacing dist/ after the
            # release checker itself has been interrupted.
            completed = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
            if completed.returncode and process.poll() is None:
                process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (OSError, subprocess.SubprocessError):
        try:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def _temporary_output_file():
    """Capture child output without making a platform code page fatal.

    Child processes on Windows can write the active console/code-page encoding
    directly to a redirected file descriptor. The release checker must retain
    the command result and readable diagnostics even when one byte is not valid
    UTF-8; a logging decode failure must never replace the actual test result.
    """

    return tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")


def run(
    command: Sequence[str],
    root: Path,
    log: List[str],
    report: Path,
    *,
    environment: Optional[Mapping[str, str]] = None,
    timeout_seconds: int,
) -> None:
    line = "$ " + " ".join(command)
    print(line, flush=True)
    log.append(line)
    checkpoint(report, log, "RUNNING")

    # Child output goes to real files, not pipes, so verbose builds cannot
    # deadlock. A heartbeat is printed and checkpointed every 15 seconds so a
    # slow platform never looks like a silent stall.
    with _temporary_output_file() as stdout_file, _temporary_output_file() as stderr_file:
        popen_kwargs = {
            "cwd": str(root),
            "text": True,
            "stdout": stdout_file,
            "stderr": stderr_file,
            "env": dict(environment) if environment is not None else None,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            popen_kwargs["start_new_session"] = True
        process = subprocess.Popen(command, **popen_kwargs)  # type: ignore[arg-type]
        started = time.monotonic()
        next_heartbeat = started + 15.0
        timed_out = False
        try:
            while process.poll() is None:
                now = time.monotonic()
                elapsed = now - started
                if elapsed >= timeout_seconds:
                    timed_out = True
                    _stop_process(process)
                    break
                if now >= next_heartbeat:
                    heartbeat = f"... still running ({int(elapsed)}s): {command[0]}"
                    print(heartbeat, flush=True)
                    log.append(heartbeat)
                    checkpoint(report, log, "RUNNING")
                    next_heartbeat = now + 15.0
                time.sleep(0.25)
        except ReleaseInterrupted as exc:
            _stop_process(process)
            message = f"INTERRUPTED: received signal {exc.signum}; active child process stopped"
            print(message, file=sys.stderr, flush=True)
            log.append(message)
            checkpoint(report, log, "INTERRUPTED")
            raise SystemExit(128 + exc.signum) from exc
        except BaseException:
            _stop_process(process)
            raise

        returncode = process.poll()
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read()
        stderr = stderr_file.read()

    if stdout:
        print(stdout, end="", flush=True)
        log.append(stdout.rstrip())
    if stderr:
        print(stderr, end="", file=sys.stderr, flush=True)
        log.append(stderr.rstrip())
    if timed_out:
        message = f"TIMEOUT: command exceeded {timeout_seconds} seconds"
        print(message, file=sys.stderr, flush=True)
        log.append(message)
        checkpoint(report, log, "FAILED_TIMEOUT")
        raise SystemExit(124)
    if returncode:
        log.append("EXIT CODE: " + str(returncode))
        checkpoint(report, log, "FAILED")
        raise SystemExit(returncode)
    checkpoint(report, log, "RUNNING")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


_FINGERPRINT_IGNORED_NAMES = {
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "build",
    "dist",
    "__pycache__",
    ".uriel-release-check.lock",
    "release-check.txt",
}


def source_fingerprint(root: Path) -> str:
    """Hash the release-relevant working tree for safe interrupted-check reuse."""

    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        relative = path.relative_to(root)
        if any(
            part in _FINGERPRINT_IGNORED_NAMES or part.endswith(".egg-info")
            for part in relative.parts
        ):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        if path.is_symlink():
            payload = ("link\0" + os.readlink(path)).encode("utf-8", errors="surrogateescape")
        elif path.is_file():
            payload = path.read_bytes()
        else:
            continue
        name = relative.as_posix().encode("utf-8", errors="surrogateescape")
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def execute(args: argparse.Namespace, root: Path, report: Path) -> int:
    log: List[str] = [
        "Uriel release check",
        "repository: " + str(root),
        "python: " + sys.version.replace("\n", " "),
        "full: " + str(bool(args.full)).lower(),
        "reuse_artifacts: " + str(bool(args.reuse_artifacts)).lower(),
        "command_timeout_seconds: " + str(args.command_timeout),
    ]
    checkpoint(report, log, "STARTED")

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "src") + os.pathsep + environment.get("PYTHONPATH", "")

    def checked(command: Sequence[str], *, multiplier: int = 1, env: Optional[Mapping[str, str]] = None) -> None:
        run(
            command,
            root,
            log,
            report,
            environment=environment if env is None else env,
            timeout_seconds=args.command_timeout * multiplier,
        )

    checked([sys.executable, "-m", "compileall", "-q", "src", "tests", "scripts", "examples"])
    for checker in PRE_BUILD_CHECKS:
        checked([sys.executable, checker])
    checked([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    checked([sys.executable, "scripts/privacy_sweep.py"])

    build_fingerprint = source_fingerprint(root)
    fingerprint_path = root / "dist" / "BUILD_INPUT_SHA256"
    if args.full and not args.reuse_artifacts:
        checked([sys.executable, "scripts/build_distributions.py", "--clean"], multiplier=2)
        fingerprint_path.write_text(build_fingerprint + "\n", encoding="ascii")
        log.append("build_input_sha256: " + build_fingerprint)
        checkpoint(report, log, "RUNNING")
    elif args.full:
        existing = sorted(path.name for path in (root / "dist").iterdir() if path.is_file()) if (root / "dist").is_dir() else []
        log.append("reusing release artifacts: " + (", ".join(existing) or "<none>"))
        checkpoint(report, log, "RUNNING")
        if not fingerprint_path.is_file():
            message = "--reuse-artifacts requires dist/BUILD_INPUT_SHA256 from a prior full check"
            log.append("FAILED: " + message)
            checkpoint(report, log, "FAILED")
            raise SystemExit(message)
        recorded_fingerprint = fingerprint_path.read_text(encoding="ascii").strip()
        if recorded_fingerprint != build_fingerprint:
            message = "source files changed after the reusable distributions were built; rerun --full without --reuse-artifacts"
            log.append("FAILED: " + message)
            checkpoint(report, log, "FAILED")
            raise SystemExit(message)
        log.append("build_input_sha256: " + build_fingerprint + " (matched)")
        checkpoint(report, log, "RUNNING")
    checked([sys.executable, "scripts/build_portable.py"])
    if args.full:
        checked([sys.executable, "scripts/make_checksums.py"])
    checked([sys.executable, "dist/uriel.pyz", "--version"])
    checked([sys.executable, "-m", "uriel", "--version"])

    if args.full:
        wheels = sorted(path for path in (root / "dist").glob("*.whl") if path.is_file())
        source_archives = sorted(path for path in (root / "dist").glob("*.tar.gz") if path.is_file())
        wheel_names = ", ".join(path.name for path in wheels) or "<none>"
        source_names = ", ".join(path.name for path in source_archives) or "<none>"
        log.append("release wheels: " + wheel_names)
        log.append("release source distributions: " + source_names)
        checkpoint(report, log, "RUNNING")
        if len(wheels) != 1 or len(source_archives) != 1:
            message = (
                "full release check expected exactly one wheel and one source distribution; "
                "found wheels: " + wheel_names + "; source distributions: " + source_names
            )
            log.append("FAILED: " + message)
            checkpoint(report, log, "FAILED")
            raise SystemExit(message)

        with tempfile.TemporaryDirectory(prefix="uriel-release-venv-") as temporary:
            virtual_environment = Path(temporary) / "venv"
            checked([sys.executable, "-m", "venv", "--without-pip", str(virtual_environment)], multiplier=2)
            if os.name == "nt":
                python = virtual_environment / "Scripts" / "python.exe"
                executable = virtual_environment / "Scripts" / "uriel.exe"
            else:
                python = virtual_environment / "bin" / "python"
                executable = virtual_environment / "bin" / "uriel"
            clean_environment = os.environ.copy()
            clean_environment.pop("PYTHONPATH", None)
            checked(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "--python",
                    str(python),
                    "install",
                    "--no-deps",
                    "--no-index",
                    str(wheels[0]),
                ],
                env=clean_environment,
            )
            checked([str(python), "-m", "uriel", "--version"], env=clean_environment)
            checked([str(executable), "--version"], env=clean_environment)
            checked([sys.executable, "-m", "pip", "--python", str(python), "check"], env=clean_environment)
            schema_check = (
                "import importlib.resources as r; "
                "from uriel.data_contracts import DATA_SCHEMA_FILES; "
                "p=r.files('uriel.schemas'); "
                "required={'uriel.audit.v1.schema.json','uriel.blessing.v1.schema.json',"
                "'uriel.external_review.v1.schema.json','uriel.project.v1.schema.json',"
                "'uriel.source_manifest.v1.schema.json'} | set(DATA_SCHEMA_FILES.values()); "
                "actual={x.name for x in p.iterdir() if x.name.endswith('.json')}; "
                "assert required <= actual, sorted(required-actual); print('packaged schemas: PASS')"
            )
            checked([str(python), "-c", schema_check], env=clean_environment)
            checked(
                [
                    str(python),
                    "scripts/smoke_installed_data_ingress.py",
                    "--executable",
                    str(executable),
                ],
                env=clean_environment,
            )

    portable = root / "dist" / "uriel.pyz"
    log.extend(["", "RESULT: PASS", "portable_sha256: " + sha(portable)])
    checkpoint(report, log, "PASS")
    if args.full:
        distribution_report = root / "dist" / "release-check.txt"
        if distribution_report.resolve() != report.resolve():
            shutil.copy2(report, distribution_report)
    print("report:", report, flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--report", default="release-check.txt")
    parser.add_argument("--full", action="store_true", help="build distributions and test a fresh wheel install")
    parser.add_argument(
        "--reuse-artifacts",
        action="store_true",
        help=(
            "resume an interrupted --full check using hash-matched wheel/sdist artifacts in dist; "
            "tests and privacy checks still run"
        ),
    )
    parser.add_argument(
        "--command-timeout",
        type=int,
        default=300,
        help="maximum seconds for each external command (default: 300)",
    )
    args = parser.parse_args()
    if args.command_timeout < 10:
        parser.error("--command-timeout must be at least 10 seconds")
    if args.reuse_artifacts and not args.full:
        parser.error("--reuse-artifacts requires --full")

    root = Path(args.repository).resolve()
    report = Path(args.report)
    if not report.is_absolute():
        report = root / report

    previous_handlers = []
    for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGBREAK"):
        signum = getattr(signal, name, None)
        if signum is None:
            continue
        previous_handlers.append((signum, signal.getsignal(signum)))
        signal.signal(signum, _termination_handler)
    try:
        with ReleaseLock(root / ".uriel-release-check.lock"):
            return execute(args, root, report)
    except ReleaseInterrupted as exc:
        # Interruptions that arrive between subprocesses still leave a durable
        # continuation marker. Interruptions during a subprocess are handled
        # inside run(), which first terminates the whole child process tree.
        prior = report.read_text(encoding="utf-8").splitlines() if report.is_file() else []
        if prior and prior[-1].startswith("STATUS: "):
            prior.pop()
        while prior and not prior[-1]:
            prior.pop()
        message = f"INTERRUPTED: received signal {exc.signum}; no child process remained active"
        print(message, file=sys.stderr, flush=True)
        prior.append(message)
        checkpoint(report, prior, "INTERRUPTED")
        return 128 + exc.signum
    finally:
        for signum, handler in previous_handlers:
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
