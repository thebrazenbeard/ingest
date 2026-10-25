"""Fail-closed regression guard for concealed editor workspace-open execution.

Historical suspicious blobs remain recoverable in Git history. The active
working tree must not configure a hidden task or permission to auto-run one.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTORUN = re.compile(r'"runOn"\s*:\s*"folderOpen"')


class EditorStartupSafetyTests(unittest.TestCase):
    def test_no_automatic_workspace_open_tasks(self):
        tasks_path = ROOT / ".vscode" / "tasks.json"
        self.assertTrue(tasks_path.is_file(), "Safety-reviewed task configuration is required")
        document = json.loads(tasks_path.read_text(encoding="utf-8"))
        for task in document.get("tasks", []):
            with self.subTest(task=task.get("label")):
                self.assertNotEqual(
                    task.get("runOptions", {}).get("runOn"),
                    "folderOpen",
                    "Opening a repository must not launch code automatically",
                )

    def test_workspace_automatic_task_consent_is_absent(self):
        settings_path = ROOT / ".vscode" / "settings.json"
        self.assertTrue(settings_path.is_file(), "Safety-reviewed editor settings are required")
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertNotIn("task.allowAutomaticTasks", settings)
        self.assertNotIn("tasks", settings)

    def test_no_folder_open_in_any_editor_configuration(self):
        paths = list((ROOT / ".vscode").glob("*.json"))
        paths.extend(ROOT.glob("*.code-workspace"))
        for path in paths:
            with self.subTest(path=path.name):
                self.assertIsNone(
                    AUTORUN.search(path.read_text(encoding="utf-8")),
                    "Editor configuration must not declare a folderOpen task",
                )

    def test_disguised_node_payload_is_absent(self):
        self.assertFalse(
            (ROOT / "public" / "fonts" / "fa-solid.lkf").exists(),
            "An executable disguised as a font must not be restored",
        )


if __name__ == "__main__":
    unittest.main()
