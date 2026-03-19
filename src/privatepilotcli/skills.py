from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from privatepilotcli.config import GLOBAL_SKILLS_FILE

LOCAL_SKILLS_PATH = Path.cwd() / "skills.md"


@dataclass
class SkillDef:
    name: str
    description: str
    instructions: str
    triggers: list[str] = field(default_factory=list)


@dataclass
class ParsedSkills:
    system_prompt: str
    skills: list[SkillDef]


def load_skills() -> str:
    """Load skills.md — local takes full precedence over global."""
    if LOCAL_SKILLS_PATH.exists():
        return LOCAL_SKILLS_PATH.read_text()
    if GLOBAL_SKILLS_FILE.exists():
        return GLOBAL_SKILLS_FILE.read_text()
    return ""


def parse_skills(content: str) -> ParsedSkills:
    """
    Parse skills.md into a base system prompt + list of SkillDef blocks.

    Format:
      Everything before the first '## Skill:' heading = base system prompt.
      Each '## Skill: <name>' section may contain:
        **Description:** ...
        **Triggers:** comma-separated phrases
        **Instructions:** freeform text until next skill or EOF
    """
    if not content.strip():
        return ParsedSkills(system_prompt="", skills=[])

    skill_header_re = re.compile(r"^## Skill:\s*(.+)$", re.MULTILINE)
    matches = list(skill_header_re.finditer(content))

    if not matches:
        return ParsedSkills(system_prompt=content.strip(), skills=[])

    base_prompt = content[: matches[0].start()].strip()
    skills: list[SkillDef] = []

    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block = content[match.end() : end].strip()
        name = match.group(1).strip()
        description = _extract_field(block, "Description") or ""
        triggers_raw = _extract_field(block, "Triggers") or ""
        triggers = [t.strip() for t in triggers_raw.split(",") if t.strip()]
        instructions = _extract_field(block, "Instructions") or ""
        skills.append(SkillDef(name=name, description=description, instructions=instructions, triggers=triggers))

    # Build combined system prompt: base + all skill instructions
    parts = [base_prompt] if base_prompt else []
    for skill in skills:
        if skill.instructions:
            parts.append(f"### {skill.name}\n{skill.instructions.strip()}")

    return ParsedSkills(system_prompt="\n\n---\n\n".join(parts), skills=skills)


def _extract_field(block: str, field_name: str) -> str | None:
    """Extract the text content after a **FieldName:** marker."""
    pattern = re.compile(rf"\*\*{re.escape(field_name)}:\*\*\s*(.*?)(?=\n\*\*|\Z)", re.DOTALL)
    m = pattern.search(block)
    return m.group(1).strip() if m else None


def build_system_prompt(content: str) -> str:
    """Return the combined system prompt string from skills.md content."""
    if not content:
        return ""
    return parse_skills(content).system_prompt
