"""
Day 1 scanner: walks a workspace, finds TODO/FIXME/HACK/XXX comment markers,
returns them as ticket suggestions.

Day 2 will add an LLM classification pass over candidate code regions
(missing tests, refactor opportunities, security smells). That logic plugs
in alongside _scan_file — same Suggestion shape, different detector.
"""
import hashlib
import logging
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterator, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Suggestion:
    id: str          # stable hash (file + line + marker) so the UI can dedupe
    type: str        # "Task" | "Bug" | "Refactor"
    title: str       # what the ticket is about
    file: str        # relative to workspace root
    line: int        # 1-indexed
    snippet: str     # the matching line, possibly with ±1 context

    def to_dict(self) -> dict:
        return asdict(self)


# Comment markers → canonical ticket type.
_MARKER_TYPES = {
    "TODO":  "Task",
    "FIXME": "Bug",
    "HACK":  "Refactor",
    "XXX":   "Refactor",
}

# Matches comment-prefixed markers in any common language style.
# Examples it catches:
#   # TODO: do the thing
#   // FIXME(piram): broken on Safari
#   /* HACK — temporary workaround */
#   <!-- TODO add the alt text -->
_MARKER_RE = re.compile(
    r"(?:#|//|/\*|<!--)\s*"
    r"(TODO|FIXME|HACK|XXX)"
    r"(?:\([^)]*\))?"           # optional (author) tag
    r"\s*[:,\-—]?\s*"           # optional separator
    r"(?P<text>.*?)"
    r"\s*(?:\*/|-->)?\s*$",
    re.IGNORECASE,
)

# Directories we skip entirely (build artifacts, vendored deps, vcs internals).
_SKIP_DIRS = frozenset({
    "node_modules", ".venv", "venv", "env", ".git", "dist", "build",
    "__pycache__", ".next", "target", "out", ".pytest_cache", ".mypy_cache",
    ".idea", ".vscode", "coverage", ".turbo", ".cache", "vendor",
    "site-packages", ".tox", ".eggs",
})

# File extensions we actually scan. Skips binaries, lockfiles, etc.
_SCAN_EXTS = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".swift", ".rb", ".php", ".cs",
    ".c", ".cpp", ".h", ".hpp", ".m", ".mm",
    ".vue", ".svelte", ".html", ".css", ".scss", ".sass",
    ".sh", ".bash", ".zsh", ".yaml", ".yml", ".sql",
})

# Hard cap so scanning a monorepo doesn't blow up the response or timeout.
_MAX_FILES = 2000
_MAX_FILE_BYTES = 500_000   # skip files bigger than 500 KB (likely generated)


def scan_workspace(
    workspace_path: str,
    limit: Optional[int] = None,
    llm_api_key: Optional[str] = None,
    max_llm_files: int = 5,
) -> List[Suggestion]:
    """
    Walk *workspace_path* and return ticket suggestions.

    Always runs the regex pass (TODO/FIXME/HACK/XXX comment markers).
    If *llm_api_key* is provided, also runs an LLM pass over up to
    *max_llm_files* files — preferring files that already have regex hits
    since those are usually richer in surrounding issues.

    Args:
        workspace_path: Absolute path to the project root.
        limit:          Optional cap on suggestions returned.
        llm_api_key:    OpenRouter key. When set, enables the LLM pass.
        max_llm_files:  Cost guard — most files we'll send to the LLM.
    """
    root = Path(workspace_path).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Workspace path does not exist or isn't a directory: {workspace_path}")

    regex_suggestions: List[Suggestion] = []
    files_with_hits: List[Path] = []
    all_scanned_files: List[Path] = []
    files_scanned = 0

    for file_path in _walk(root):
        if files_scanned >= _MAX_FILES:
            logger.warning("Hit max files cap (%d), stopping scan", _MAX_FILES)
            break
        files_scanned += 1
        all_scanned_files.append(file_path)
        try:
            file_hits = _scan_file(file_path, root)
            if file_hits:
                files_with_hits.append(file_path)
            regex_suggestions.extend(file_hits)
        except (OSError, UnicodeDecodeError) as e:
            logger.debug("Skipping %s: %s", file_path, e)
            continue

    logger.info(
        "Regex pass: scanned %d files in %s — found %d suggestions",
        files_scanned, root, len(regex_suggestions),
    )

    llm_suggestions: List[Suggestion] = []
    if llm_api_key:
        # Prefer files with regex hits, then fall back to other source files.
        # This keeps the LLM focused on areas already showing signs of churn.
        candidates: List[Path] = []
        seen = set()
        for fp in files_with_hits + all_scanned_files:
            if fp in seen:
                continue
            seen.add(fp)
            candidates.append(fp)
            if len(candidates) >= max_llm_files:
                break

        if candidates:
            import time
            from .llm_scanner import analyze_file, _INTER_CALL_DELAY_SECONDS
            for i, fp in enumerate(candidates):
                if i > 0:
                    # Pace requests so we don't burn through the free-tier per-minute cap
                    time.sleep(_INTER_CALL_DELAY_SECONDS)
                rel = str(fp.relative_to(root))
                try:
                    llm_suggestions.extend(analyze_file(fp, rel, llm_api_key))
                except Exception as e:
                    logger.warning("LLM scan failed on %s: %s", rel, e)
                    continue
            logger.info("LLM pass: analysed %d file(s), found %d suggestion(s)",
                        len(candidates), len(llm_suggestions))

    suggestions = regex_suggestions + llm_suggestions

    if limit and len(suggestions) > limit:
        suggestions = suggestions[:limit]

    return suggestions


def _walk(root: Path) -> Iterator[Path]:
    """Yield every scannable file under *root*, skipping ignored directories."""
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in _SCAN_EXTS:
            continue
        try:
            if path.stat().st_size > _MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield path


def _scan_file(path: Path, root: Path) -> List[Suggestion]:
    """Scan a single file for marker comments and return one Suggestion per hit."""
    rel = str(path.relative_to(root))
    suggestions: List[Suggestion] = []

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, start=1):
            m = _MARKER_RE.search(line)
            if not m:
                continue

            marker = m.group(1).upper()
            text   = (m.group("text") or "").strip()
            ttype  = _MARKER_TYPES.get(marker, "Task")

            title = text if text else f"Address {marker} at {rel}:{lineno}"
            # Trim to keep titles tight
            if len(title) > 100:
                title = title[:97] + "..."

            suggestions.append(Suggestion(
                id=_hash_id(rel, lineno, marker),
                type=ttype,
                title=title,
                file=rel,
                line=lineno,
                snippet=line.rstrip("\n"),
            ))

    return suggestions


def _hash_id(rel_path: str, line: int, marker: str) -> str:
    """Stable short ID so re-scans return the same id for the same finding."""
    h = hashlib.sha1(f"{rel_path}:{line}:{marker}".encode()).hexdigest()
    return f"s_{h[:10]}"
