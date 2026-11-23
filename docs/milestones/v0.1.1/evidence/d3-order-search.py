"""Evidence-only: exhaustive search for a globally continuous, crossing-free balloon order.

Run from the repository root (takes about 100 s):

    uv run python docs/milestones/v0.1.1/evidence/d3-order-search.py

It rebuilds the vise L3 assembly, captures the exact view bbox and component anchors the layout
sees, then enumerates every four-side composition of the BOM numbers into consecutive blocks, every
per-block slide on a 7-point grid around the anchor mean, and both walk directions.  It prints the
configuration count and the number of crossing-free configurations (zero for vise), reproducing the
D3 evidence claim.  Not imported by the package or tests.
"""

from __future__ import annotations

import itertools
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))

import linercad.layout as L  # noqa: E402
from linercad.runtime import build  # noqa: E402

STEP, OFFSET, R = 10.0, 8.0, 4.5  # [assembly] geometry + [placement].balloon_clearance
CW = ("top", "right", "bottom", "left")
SIGN = {"top": 1.0, "bottom": -1.0, "left": 1.0, "right": -1.0}
AX = {"top": 0, "bottom": 0, "left": 1, "right": 1}


def capture(case: str):
    """Build the case with the plan disabled; capture (B, anchors) the layout passes to it."""
    seen = {}
    orig = L._balloon_plan

    def spy(B, numbered, step, offset, r, written=None, obstacles=()):
        if len(numbered) >= 8 and "args" not in seen:
            seen["args"] = (B, numbered)
        return None

    L._balloon_plan = spy
    try:
        work = Path(tempfile.mkdtemp()) / case
        shutil.copytree(
            REPO / "evals" / "L3" / case,
            work,
            ignore=shutil.ignore_patterns(".linercad", "__pycache__", "*.jsonl", "*.dxf"),
        )
        build(work)
    finally:
        L._balloon_plan = orig
    return seen["args"]


def compositions(n, k):
    if k == 1:
        yield (n,)
        return
    for first in range(n + 1):
        for rest in compositions(n - first, k - 1):
            yield (first,) + rest


def items(B, anchors, order, comp, offs, cw):
    out = []
    i = oi = 0
    for side, cnt in zip(order, comp):
        group = [j + 1 for j in range(i, i + cnt)]
        i += cnt
        if not group:
            continue
        sign = cw * SIGN[side]
        mean = sum(anchors[n][AX[side]] for n in group) / len(group) + offs[oi]
        oi += 1
        for k, n in enumerate(group):
            t = mean + (k - (len(group) - 1) / 2) * STEP * sign
            c = {
                "top": (t, B[3] + OFFSET + R),
                "bottom": (t, B[1] - OFFSET - R),
                "left": (B[0] - OFFSET - R, t),
                "right": (B[2] + OFFSET + R, t),
            }[side]
            out.append((anchors[n], c))
    return out


def crosses(items_):
    def sc(a, b, c, d):
        def o(p, q, r):
            return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

        return o(c, d, a) * o(c, d, b) < -1e-12 and o(a, b, c) * o(a, b, d) < -1e-12

    return any(
        sc(items_[i][0], items_[i][1], items_[j][0], items_[j][1])
        for i in range(len(items_))
        for j in range(i + 1, len(items_))
    )


def main(case="vise"):
    B, numbered = capture(case)
    anchors = dict(numbered)
    nums = sorted(anchors)
    n = len(nums)
    comps = list(compositions(n, 4))
    grid = tuple(x * STEP for x in (0, 1, -1, 2, -2, 3, -3))
    count = zero = 0
    for cw in (1.0, -1.0):
        for rot in range(4):
            order = tuple(CW[(rot + i) % 4] for i in range(4))
            if cw < 0:
                order = tuple(reversed(order))
            for comp in comps:
                m = sum(1 for c in comp if c)
                for offs in itertools.product(grid, repeat=m):
                    count += 1
                    if not crosses(items(B, anchors, order, comp, offs, cw)):
                        zero += 1
    print(f"{case}: n={n} configurations={count} zero-crossing={zero}")
    return 0 if zero == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "vise"))
