"""Load project-local Agent skills without coupling them to graph nodes."""

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIRECTORY = PROJECT_ROOT / "skills"


class SkillNotFoundError(FileNotFoundError):
    """Raised when a requested skill does not have a local SKILL.md file."""


@dataclass(frozen=True)
class SkillPrompt:
    """The immutable prompt source for a named skill."""

    name: str
    content: str
    path: Path


class SkillLoader:
    """Read skills stored as ``skills/<skill_name>/SKILL.md``.

    Skill text is returned verbatim. This class intentionally does not parse or
    rewrite the markdown, so a skill remains the source of truth for its prompt.
    """

    def __init__(self, skills_directory: Path = SKILLS_DIRECTORY) -> None:
        self.skills_directory = skills_directory.resolve()

    def load(self, skill_name: str) -> SkillPrompt:
        if not skill_name or Path(skill_name).name != skill_name:
            raise ValueError("skill_name must be a single directory name")

        skill_path = (self.skills_directory / skill_name / "SKILL.md").resolve()
        if not skill_path.is_relative_to(self.skills_directory):
            raise ValueError("skill path must be inside the skills directory")
        if not skill_path.is_file():
            raise SkillNotFoundError(f"Skill not found: {skill_name}")

        return SkillPrompt(
            name=skill_name,
            content=skill_path.read_text(encoding="utf-8"),
            path=skill_path,
        )
