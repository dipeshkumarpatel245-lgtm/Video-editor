from __future__ import annotations
import json, logging, shlex, subprocess, sys
from typing import Sequence

log = logging.getLogger("videotemplate")


def run(cmd: Sequence[str],
        *,
        capture: bool = True,
        timeout: int = 600,
        check: bool = True,
        **kw) -> subprocess.CompletedProcess:
    """Run *cmd* with optional timeout; raise on error."""
    log.debug("RUN %s", " ".join(shlex.quote(c) for c in cmd))
    cp = subprocess.run(
        list(cmd),
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        timeout=timeout,
        **kw,
    )
    if check and cp.returncode != 0:
        err = (cp.stderr or b"").decode("utf-8", errors="replace")
        raise RuntimeError(f"Command failed ({cp.returncode}): {cmd[0]}\n{err[:2000]}")
    return cp


def run_ffmpeg(*args: str, input_file: str | None = None, timeout: int = 600) -> str:
    """Run an ffmpeg command (no -y assumed by caller) and return stderr log."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "warning"]
    if input_file:
        cmd += ["-i", input_file]
    cmd += list(args)
    cp = run(cmd, timeout=timeout)
    return (cp.stderr or b"").decode("utf-8", errors="replace")


def probe_json(input_file: str, timeout: int = 30) -> dict:
    """Run ffprobe and return parsed JSON output."""
    cmd = ["ffprobe",
           "-v", "quiet",
           "-print_format", "json",
           "-show_format", "-show_streams",
           input_file]
    cp = run(cmd, timeout=timeout)
    return json.loads(cp.stdout)