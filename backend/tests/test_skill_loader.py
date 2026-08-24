import importlib
import os
import unittest

from app.skill_loader import SkillLoader


class SkillLoaderTests(unittest.TestCase):
    def test_loads_company_research_skill_verbatim(self) -> None:
        skill = SkillLoader().load("company-research")

        self.assertEqual(skill.name, "company-research")
        self.assertEqual(skill.path.name, "SKILL.md")
        self.assertTrue(skill.content.startswith("---"))
        self.assertIn("company-research", skill.content)

    def test_importing_app_loads_dotenv_file(self) -> None:
        os.environ.pop("OPENAI_MODEL", None)

        import app

        importlib.reload(app)

        self.assertEqual(os.getenv("OPENAI_MODEL"), "gpt-4.1-mini")


if __name__ == "__main__":
    unittest.main()
