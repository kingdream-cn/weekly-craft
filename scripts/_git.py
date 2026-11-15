"""Small Git helpers shared by publishing and the optional dual-repo adapter."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


def git(repo: Path, *args: str, check=True):
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if check and result.returncode:
        # Git stderr may contain authenticated remote URLs or private payloads.
        raise ValueError(f"Git {args[0]} failed; inspect the repository locally")
    return result


def root(path: Path) -> Path:
    result = git(path, "rev-parse", "--show-toplevel")
    found = Path(result.stdout.strip()).resolve()
    if found != path.resolve():
        raise ValueError("Use a Git repository root directory")
    return found


def remote_key(value: str) -> str:
    """Compare HTTPS/SSH Git remotes without logging credentials."""
    value = value.strip()
    scp = re.fullmatch(r"(?:[^/@:]+@)?([^/:]+):(.+)", value)
    if "://" not in value and scp:
        host, path = scp.groups()
    elif "://" in value:
        parsed = urlsplit(value)
        if parsed.scheme == "file":
            return str(Path(parsed.path).resolve())
        host, path = parsed.hostname or "", parsed.path
    else:
        return str(Path(value).expanduser().resolve())
    return f"{host.lower()}/{path.strip('/').removesuffix('.git')}".lower()


def github_name(repo: Path) -> str:
    key = remote_key(git(repo, "remote", "get-url", "origin").stdout)
    if not re.fullmatch(r"github\.com/[a-z0-9_.-]+/[a-z0-9_.-]+", key):
        raise ValueError("This adapter expects GitHub repositories with an origin remote")
    return key.removeprefix("github.com/")


def relative_file(value: str) -> Path:
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts or path.parts[0] == ".git":
        raise ValueError("Expected a relative path inside the target repository")
    return path
