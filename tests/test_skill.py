import re
from importlib import resources

from linercad.cli import COMMANDS


def test_skill_is_short_and_mentions_only_real_commands():
    text = (resources.files("linercad") / "skill" / "SKILL.md").read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 300
    used = set(re.findall(r"lcad ([a-z]+)", text))
    assert used and used <= set(COMMANDS), used - set(COMMANDS)
