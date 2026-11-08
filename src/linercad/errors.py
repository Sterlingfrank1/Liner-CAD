"""Errors given back to the agent: element ID, reason, values and candidates (SPEC §4.6)."""

from __future__ import annotations


class LinerError(Exception):
    """Base error. Every field is meant for the agent to fix its script and retry."""

    code = "error"

    def __init__(
        self,
        message: str,
        *,
        id: str | None = None,
        candidates=None,
        values=None,
        hint: str | None = None,
        code: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.id = id
        self.candidates = list(candidates or [])
        self.values = dict(values or {})
        self.hint = hint

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "id": self.id,
            "candidates": self.candidates,
            "values": self.values,
            "hint": self.hint,
            **{k: getattr(self, k) for k in ("where", "trace") if getattr(self, k, None)},
        }

    def __str__(self) -> str:
        s = self.message
        if self.candidates:
            s += "；候选：" + ", ".join(str(c) for c in self.candidates)
        if self.hint:
            s += "；提示：" + self.hint
        return s


class NotFound(LinerError):
    code = "not_found"


class CountMismatch(LinerError):
    code = "count_mismatch"


class InvalidArgument(LinerError):
    code = "invalid_arg"


class UnknownAttribute(InvalidArgument, AttributeError):
    """Unknown method or field on an API object; lists what is available."""


class DuplicateId(LinerError):
    code = "duplicate_id"


class ParamError(LinerError):
    code = "param"


class StaleOp(LinerError):
    code = "stale"


class ScriptError(LinerError):
    code = "script"


class BuildError(LinerError):
    code = "build"


class GitError(LinerError):
    code = "git"


class UndoError(LinerError):
    code = "undo"


class NoOps(LinerError):
    code = "no_ops"


class DirtySource(LinerError):
    code = "dirty"
