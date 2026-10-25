"""Source guard against concealed editor-startup execution.

This makes no claim about prior editor consent or workstation effects.
"""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISGUISED_ASSETS = ("fa-solid.lkf", "fa-solid-500.woff2")


def read_jsonc(path: Path) -> dict:
    value = path.read_text(encoding="utf-8")
    return json.loads(re.sub(r",\s*(?=[}\]])", "", value))


class EditorStartupSourceGuardTests(unittest.TestCase):
    def test_disguised_executable_assets_absent(self):
        for name in DISGUISED_ASSETS:
            with self.subTest(asset=name):
                self.assertFalse((ROOT / "public" / "fonts" / name).exists())

    def test_no_implicit_workspace_task_or_disguised_asset_command(self):
        config = read_jsonc(ROOT / ".vscode" / "tasks.json")
        for task in config.get("tasks", ()):
            with self.subTest(task=task.get("label")):
                self.assertNotEqual(
                    task.get("runOptions", {}).get("runOn"), "folderOpen"
                )
                command = str(task.get("command", ""))
                for name in DISGUISED_ASSETS:
                    self.assertNotIn(name, command)

    def test_workspace_settings_do_not_claim_task_consent(self):
        settings = read_jsonc(ROOT / ".vscode" / "settings.json")
        self.assertNotIn("task.allowAutomaticTasks", settings)
        self.assertNotIn("tasks", settings)


if __name__ == "__main__":
    unittest.main()
