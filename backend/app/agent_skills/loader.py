from dataclasses import dataclass
from pathlib import Path

import yaml

SKILLS_DIR = Path(__file__).parent


@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str


@dataclass(frozen=True)
class Skill(SkillInfo):
    instructions: str


def _parse_skill_md(path: Path) -> Skill:
    text = path.read_text()
    if not text.startswith("---"):
        raise ValueError(f"{path} is missing YAML frontmatter")
    _, frontmatter_raw, body = text.split("---", 2)
    frontmatter = yaml.safe_load(frontmatter_raw) or {}
    return Skill(
        name=frontmatter["name"],
        description=frontmatter["description"],
        instructions=body.strip(),
    )


def list_skills() -> list[SkillInfo]:
    """Progressive-disclosure index: name + description only, no full instructions."""
    skills = []
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        skill = _parse_skill_md(skill_md)
        skills.append(SkillInfo(name=skill.name, description=skill.description))
    return skills


def load_skill(name: str) -> Skill:
    """Loads full skill instructions for injection into a single Claude call's system prompt."""
    for skill_md in SKILLS_DIR.glob("*/SKILL.md"):
        skill = _parse_skill_md(skill_md)
        if skill.name == name:
            return skill
    raise KeyError(f"No skill named {name!r} found under {SKILLS_DIR}")
