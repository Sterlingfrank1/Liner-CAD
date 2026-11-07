"""Text height / width estimates from the measured font coefficients in the std (SPEC §2).

DXF TEXT height is the cap height. GB/T 14691 character height for Chinese is the character
body, which in simfang is ``cjk_em`` × cap height, so text containing CJK is written with
``height / cjk_em``. Widths use fixed per-character coefficients so results are deterministic:
ASCII is half width (``char_width.other``); every non-ASCII character (CJK, and also Φ × ± ° in
simfang) is full width (``char_width.cjk``).
"""

from __future__ import annotations


def is_cjk(ch: str) -> bool:
    o = ord(ch)
    return o >= 0x2E80 and not (0xFF61 <= o <= 0xFFDC)  # CJK and full-width forms, not half-width kana


def has_cjk(s: str) -> bool:
    return any(is_cjk(c) for c in s)


def dxf_height(s: str, h: float, std: dict) -> float:
    """DXF TEXT height for GB character height ``h``."""
    return h / std["text"]["cjk_em"] if has_cjk(s) else h


def text_size(s: str, h: float, std: dict) -> tuple[float, float]:
    """(width, height) of the text box for GB character height ``h``."""
    t = std["text"]
    dh = dxf_height(s, h, std)
    cw = t["char_width"]
    w = sum(cw["other"] if ord(c) < 128 else cw["cjk"] for c in s) * dh * t["width_factor"]
    box_h = h * 1.05 if has_cjk(s) else dh * 1.25  # CJK body vs cap height + descender
    return w, box_h
