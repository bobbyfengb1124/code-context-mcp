"""Decide which files in a working tree are worth indexing."""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import git

VENDOR_DIRS = {"vendor", "node_modules", "third_party", "bower_components"}
MAX_BYTES = 1_000_000
SNIFF_BYTES = 8192


@dataclass
class Scan:
    files: list[str] = field(default_factory=list)  # repo-relative, forward slashes
    skipped: Counter = field(default_factory=Counter)  # reason -> count

    @property
    def scanned(self) -> int:
        return len(self.files) + sum(self.skipped.values())


def _ls(root: Path, *args: str) -> list[str]:
    return [p for p in git.run(root, "ls-files", "-z", *args).split("\0") if p]


def skip_reason(path: str, data: bytes, size: int) -> str | None:
    if VENDOR_DIRS.intersection(path.split("/")[:-1]):
        return "vendored"
    if size > MAX_BYTES:
        return "too large"
    if b"\0" in data[:SNIFF_BYTES]:
        return "binary"
    return None


def scan(root: Path) -> Scan:
    result = Scan()
    result.skipped["ignored"] = len(_ls(root, "--others", "--ignored", "--exclude-standard"))
    for path in dict.fromkeys(_ls(root, "--cached", "--others", "--exclude-standard")):
        full = root / path
        if not full.is_file():  # tracked but deleted in the working tree
            continue
        size = full.stat().st_size
        with full.open("rb") as f:
            head = f.read(SNIFF_BYTES)
        reason = skip_reason(path, head, size)
        if reason:
            result.skipped[reason] += 1
        else:
            result.files.append(path)
    return result
