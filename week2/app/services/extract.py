from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, List

from dotenv import load_dotenv
from ollama import chat

load_dotenv()

logger = logging.getLogger(__name__)

# Default model; override with OLLAMA_MODEL env var.
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

SYSTEM_PROMPT: str = (
    "You are an action-item extraction assistant. "
    "Given free-form meeting notes or to-dos, return a JSON array of strings. "
    "Each element is a single, concise, actionable item rephrased in the imperative mood. "
    "Do NOT include explanations, markdown, or anything other than the JSON array. "
    "If there are no actionable items, return an empty array []."
)

# JSON Schema passed to Ollama's `format` parameter to force a top-level
# array of strings. This is more reliable than format="json" alone, which
# some models interpret loosely (e.g. returning an object instead of an array).
ACTION_ITEMS_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {"type": "string"},
}

BULLET_PREFIX_PATTERN = re.compile(r"^\s*([-*•]|\d+\.)\s+")
KEYWORD_PREFIXES = (
    "todo:",
    "action:",
    "next:",
)


def _is_action_line(line: str) -> bool:
    stripped = line.strip().lower()
    if not stripped:
        return False
    if BULLET_PREFIX_PATTERN.match(stripped):
        return True
    if any(stripped.startswith(prefix) for prefix in KEYWORD_PREFIXES):
        return True
    if "[ ]" in stripped or "[todo]" in stripped:
        return True
    return False


def extract_action_items(text: str) -> List[str]:
    lines = text.splitlines()
    extracted: List[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if _is_action_line(line):
            cleaned = BULLET_PREFIX_PATTERN.sub("", line)
            cleaned = cleaned.strip()
            # Trim common checkbox markers
            cleaned = cleaned.removeprefix("[ ]").strip()
            cleaned = cleaned.removeprefix("[todo]").strip()
            extracted.append(cleaned)
    # Fallback: if nothing matched, heuristically split into sentences and pick imperative-like ones
    if not extracted:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        for sentence in sentences:
            s = sentence.strip()
            if not s:
                continue
            if _looks_imperative(s):
                extracted.append(s)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: List[str] = []
    for item in extracted:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(item)
    return unique


def _looks_imperative(sentence: str) -> bool:
    words = re.findall(r"[A-Za-z']+", sentence)
    if not words:
        return False
    first = words[0]
    # Crude heuristic: treat these as imperative starters
    imperative_starters = {
        "add",
        "create",
        "implement",
        "fix",
        "update",
        "write",
        "check",
        "verify",
        "refactor",
        "document",
        "design",
        "investigate",
    }
    return first.lower() in imperative_starters


def _extract_json_array(text: str) -> List[str]:
    """Best-effort extraction of a JSON array of strings from (possibly messy) model output.

    Models sometimes wrap the JSON in markdown fences or add trailing commentary. We locate
    the first `[` and the matching `]`, parse, and coerce each element to a string.
    Raises ValueError if no valid array can be recovered.
    """
    stripped = text.strip()
    # Strip markdown code fences if present
    fence_match = re.match(r"^```(?:json)?\s*\n(.*?)\n```$", stripped, re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1).strip()

    start = stripped.find("[")
    if start == -1:
        raise ValueError("no JSON array found in model output")

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(stripped)):
        ch = stripped[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                candidate = stripped[start : i + 1]
                parsed = json.loads(candidate)
                if not isinstance(parsed, list):
                    raise ValueError("top-level JSON value is not an array")
                return [str(item) for item in parsed]
    raise ValueError("unterminated JSON array in model output")


def extract_action_items_llm(text: str, model: str | None = None) -> List[str]:
    """LLM-powered alternative to extract_action_items().

    Calls a local Ollama model with structured-output enforcement (format="json").
    Falls back to a regex-based JSON-array extractor for models that still add noise.
    Returns a deduplicated, order-preserving list of action-item strings.
    """
    model = model or OLLAMA_MODEL
    response = chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        options={"temperature": 0.0},
        format=ACTION_ITEMS_SCHEMA,
    )
    content = response.message.content
    try:
        items = _extract_json_array(content)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("Failed to parse LLM output as JSON array: %s. Raw: %r", exc, content)
        return []

    # Some models return an object whose values are arrays of items; flatten those.
    flattened: List[str] = []
    for item in items:
        # If the model returned nested arrays/objects inside the array,
        # coerce to string representation rather than crashing.
        if isinstance(item, (list, dict)):
            flattened.append(json.dumps(item, ensure_ascii=False))
        else:
            flattened.append(str(item))
    items = flattened

    # Clean up: strip whitespace, drop empties, deduplicate while preserving order.
    cleaned: List[str] = []
    seen: set[str] = set()
    for item in items:
        item = item.strip()
        if not item:
            continue
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(item)
    return cleaned
