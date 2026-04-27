"""
LLM-based scanner pass: sends source files to the model and asks it to
flag concrete issues a senior reviewer would file as tickets.

Findings come back in the same `Suggestion` shape as the regex pass so the
API can merge them transparently. This is the "real value" layer — it finds
work that nobody bothered to TODO, which is the whole point.

Cost guard: caps the number of files sent and skips files larger than
~6 KB (most "interesting" modules are well under). Handles 429s by trying
the model fallback chain we already use in ticket_parser.
"""
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import List, Optional

import httpx

from .todo_scanner import Suggestion

logger = logging.getLogger(__name__)


_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Tried in order if the previous model 429s/fails. Keep these in sync with
# what's actually available on OpenRouter — model names change over time.
_MODEL_FALLBACKS = [
    "google/gemma-4-26b-a4b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-coder-32b-instruct:free",
    "deepseek/deepseek-chat-v3.1:free",
]

# Hygiene delay between LLM calls — keeps us under the per-minute cap on the free tier.
# A successful Gemma call earlier in the loop "uses up" a slot; pacing slows the burn.
_INTER_CALL_DELAY_SECONDS = 2.0

# Files larger than this go regex-only — keeps prompts within free-tier limits.
_MAX_FILE_BYTES_FOR_LLM = 6000

# Per-file cap on issues returned, regardless of what the model says.
_MAX_ISSUES_PER_FILE = 3

_VALID_TYPES = {"Bug", "Task", "Refactor"}

_SYSTEM_PROMPT = """\
You are a senior code reviewer doing a backlog grooming pass.

Look at the file the user sends and identify up to 3 CONCRETE issues that should
become tickets. Focus on:
- Bugs (logic errors, unhandled edge cases, race conditions)
- Refactor opportunities (duplication, hardcoded values, complexity, clearer abstractions)
- Missing tests for non-trivial functions
- Security concerns (unescaped input, unsafe SQL, secrets in code)

Skip nitpicks (style, naming, formatting). Only file things a reviewer would actually
want a ticket created for.

Return ONLY a JSON object — no markdown, no commentary — in this exact shape:
{
  "issues": [
    {
      "type":   "Bug" | "Task" | "Refactor",
      "title":  "<short actionable title, ≤80 chars>",
      "line":   <1-indexed line number where the issue lives>,
      "reason": "<one sentence explaining why this matters>"
    }
  ]
}

If the file looks fine, return {"issues": []}. Don't invent issues to fill the slots.
"""


def analyze_file(
    file_path: Path,
    rel_path: str,
    api_key: str,
) -> List[Suggestion]:
    """
    Run the LLM over one file and return any issues it found as Suggestions.

    Args:
        file_path: Absolute path to the file on disk.
        rel_path:  Path relative to the workspace root (used in the Suggestion).
        api_key:   OpenRouter API key.
    """
    try:
        if file_path.stat().st_size > _MAX_FILE_BYTES_FOR_LLM:
            logger.debug("Skipping %s for LLM — too large", rel_path)
            return []
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        logger.debug("Could not read %s: %s", rel_path, e)
        return []

    if not content.strip():
        return []

    user_msg = f"File: {rel_path}\n\n```\n{content}\n```"
    raw = _call_openrouter(user_msg, api_key)
    if raw is None:
        return []

    try:
        data = _extract_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("LLM returned non-JSON for %s: %s", rel_path, e)
        return []

    issues = data.get("issues", [])[:_MAX_ISSUES_PER_FILE]
    suggestions: List[Suggestion] = []
    lines = content.splitlines()

    for issue in issues:
        ttype = issue.get("type", "Task")
        if ttype not in _VALID_TYPES:
            ttype = "Task"

        title = (issue.get("title") or "").strip()
        if not title:
            continue

        line = max(1, min(int(issue.get("line", 1) or 1), len(lines) or 1))
        snippet_line = lines[line - 1] if 0 < line <= len(lines) else ""

        suggestions.append(Suggestion(
            id=_hash_id(rel_path, line, title),
            type=ttype,
            title=title[:100],
            file=rel_path,
            line=line,
            snippet=snippet_line.rstrip("\n"),
        ))

    if suggestions:
        logger.info("LLM found %d issue(s) in %s", len(suggestions), rel_path)
    return suggestions


def _call_openrouter(user_msg: str, api_key: str) -> Optional[str]:
    """Try each model in the fallback chain. Return raw content string or None."""
    for model in _MODEL_FALLBACKS:
        for attempt, backoff in enumerate([0, 2, 5]):
            if backoff:
                time.sleep(backoff)
            try:
                resp = httpx.post(
                    _OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type":  "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": _SYSTEM_PROMPT},
                            {"role": "user",   "content": user_msg},
                        ],
                        "max_tokens":  600,
                        "temperature": 0.1,
                    },
                    timeout=30.0,
                )
                if resp.status_code == 429:
                    logger.warning("LLM scanner rate-limited on %s (attempt %d)", model, attempt + 1)
                    continue
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except httpx.HTTPError as e:
                logger.warning("LLM scanner: %s failed: %s", model, e)
                break
    return None


def _extract_json(raw: str) -> dict:
    """Pull a JSON object out of the model's reply, tolerating code fences."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def _hash_id(rel_path: str, line: int, title: str) -> str:
    """Stable ID based on file+line+title so re-runs return the same id."""
    h = hashlib.sha1(f"llm:{rel_path}:{line}:{title}".encode()).hexdigest()
    return f"l_{h[:10]}"
