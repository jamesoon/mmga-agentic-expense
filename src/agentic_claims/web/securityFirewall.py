"""Prompt-injection firewall (Spec A B3).

Sanitizes user-typed text before it enters any LLM prompt. User text always
enters prompts as DATA inside a fixed fence, never as instructions.

Pure functions — no I/O, no LLM calls.
"""

from __future__ import annotations

import re

FENCE_OPEN = "<user_input>"
FENCE_CLOSE = "</user_input>"

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore_previous_instructions",
        re.compile(r"ignore\s+(?:all\s+|previous\s+)?instructions?", re.IGNORECASE),
    ),
    ("disregard_the_above", re.compile(r"disregard\s+(?:the\s+)?above", re.IGNORECASE)),
    ("system_tag", re.compile(r"(?im)^\s*system\s*:")),
    ("inst_tag", re.compile(r"\[/?INST\]")),
    ("closing_token", re.compile(r"</s>|<\|endoftext\|>|<\|im_end\|>")),
    ("long_base64_blob", re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")),
    ("tool_call_markdown", re.compile(r"```(?:tool|function)_call", re.IGNORECASE)),
]


def sanitizeUserText(raw: str) -> tuple[str, list[str]]:
    """Return (fenced_sanitized, matched_pattern_names).

    Every user-typed string should pass through this before being inserted
    into any LLM prompt. Matched patterns are replaced with [REDACTED], and
    the entire text is wrapped in a <user_input>…</user_input> fence so the
    LLM system prompt can treat it as data.
    """
    matched: list[str] = []
    sanitized = raw or ""
    for name, pattern in _PATTERNS:
        if pattern.search(sanitized):
            matched.append(name)
            sanitized = pattern.sub("[REDACTED]", sanitized)
    return f"{FENCE_OPEN}{sanitized}{FENCE_CLOSE}", matched
