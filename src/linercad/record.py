"""Revision layer hook (SPEC §7).

Every public mutating API method is decorated with ``@mutator("op")``. While a temp
script runs, the drawing carries a recorder and the outermost call of each mutator is
recorded as one action-log operation. Outside a temp script (building ``drawing.py``,
replaying the log) there is no recorder and the decorator only calls through.
"""

from __future__ import annotations

import functools


def mutator(op: str):
    """Mark a public method as a modifying API call recorded under operation name ``op``."""

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            d = self if hasattr(self, "_recorder") else self._d
            rec = d._recorder
            if rec is None:
                return fn(self, *args, **kwargs)
            return rec.call(op, fn, self, args, kwargs)

        wrapper.__mutator__ = op
        return wrapper

    return deco
