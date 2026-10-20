"""Word-level diff for HumanWrite AI v1 (side-by-side comparison view)."""

from __future__ import annotations

import difflib
import re

_TOKEN_RE = re.compile(r"\S+")


def word_diff(a: str, b: str) -> list[dict]:
    """Return [{type, text}] with type in {'eq','del','ins'} over word tokens."""
    a_toks = _TOKEN_RE.findall(a or "")
    b_toks = _TOKEN_RE.findall(b or "")
    sm = difflib.SequenceMatcher(None, a_toks, b_toks, autojunk=False)
    ops: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            ops.append({"type": "eq", "text": " ".join(a_toks[i1:i2])})
        elif tag == "delete":
            ops.append({"type": "del", "text": " ".join(a_toks[i1:i2])})
        elif tag == "insert":
            ops.append({"type": "ins", "text": " ".join(b_toks[j1:j2])})
        elif tag == "replace":
            ops.append({"type": "del", "text": " ".join(a_toks[i1:i2])})
            ops.append({"type": "ins", "text": " ".join(b_toks[j1:j2])})
    return [o for o in ops if o["text"]]
