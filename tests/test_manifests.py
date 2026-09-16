import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "when-in-rome" / "SKILL.md"
NAME = "when-in-rome"
JSON_MANIFESTS = [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", ".codex-plugin/plugin.json",
                  ".agents/plugins/marketplace.json", "gemini-extension.json", "qwen-extension.json", "kimi.plugin.json",
                  "plugin.json", "opencode.json", "hooks/hooks.json"]
VERSIONED = [".claude-plugin/plugin.json", ".codex-plugin/plugin.json", "gemini-extension.json", "qwen-extension.json",
             "kimi.plugin.json", "plugin.json"]


def skill_version():
    m = re.search(r'^\s*version:\s*"?([0-9]+\.[0-9]+\.[0-9]+)"?\s*$', SKILL.read_text(encoding="utf-8"), re.M)
    assert m
    return m.group(1)


class ManifestTests(unittest.TestCase):
    def test_json_parses_and_names_match(self):
        for rel in JSON_MANIFESTS:
            data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
            if "name" in data:
                self.assertEqual(data["name"], NAME, rel)
            for p in data.get("plugins", []):
                self.assertEqual(p["name"], NAME, rel)

    def test_versions_aligned(self):
        v = skill_version()
        for rel in VERSIONED:
            self.assertEqual(json.loads((ROOT / rel).read_text(encoding="utf-8")).get("version"), v, rel)
        self.assertIn(f"## [{v}]", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_cursor_mirror(self):
        self.assertEqual((ROOT / ".cursor" / "skills" / NAME / "SKILL.md").read_bytes(), SKILL.read_bytes())

    def test_hooks_reference_existing_scripts(self):
        data = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        for event, groups in data["hooks"].items():
            for g in groups:
                for h in g["hooks"]:
                    m = re.search(r"hooks/(\w+\.py)", h["command"])
                    self.assertTrue(m and (ROOT / "hooks" / m.group(1)).exists(), h["command"])

    def test_install_docs_cover_platforms(self):
        text = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
        for p in ["Claude Code", "Codex", "Cursor", "Gemini CLI", "OpenCode", "Kimi", "Qwen", "Copilot", "Zed", "commit-msg"]:
            self.assertIn(p, text, p)

    def test_gemini_and_opencode_paths(self):
        g = json.loads((ROOT / "gemini-extension.json").read_text(encoding="utf-8"))
        self.assertIn("@./skills/when-in-rome/SKILL.md", (ROOT / g["contextFileName"]).read_text(encoding="utf-8"))
        for p in json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))["plugin"]:
            self.assertTrue((ROOT / p).exists(), p)


if __name__ == "__main__":
    unittest.main()
