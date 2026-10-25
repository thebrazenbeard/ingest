"""Regression guard against concealed VS Code workspace-open execution.

The historical suspicious blob remains recoverable in Git history. The active
working tree must never silently run a task when the folder opens.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EditorStartupSafetyTests(unittest.TestCase):
    def test_no_automatic_workspace_open_tasks(self):
        tasks_path = ROOT / ".vscode" / "tasks.json"
        if not tasks_path.exists():
            return
        document = json.loads(tasks_path.read_text(encoding="utf-8"))
        for task in document.get("tasks", []):
            with self.subTest(task=task.get("label")):
                self.assertNotEqual(
                    task.get("runOptions", {}).get("runOn"),
                    "folderOpen",
                    "Opening a repository must not launch code automatically",
                )

    def test_disguised_node_payload_is_absent(self):
        self.assertFalse(
            (ROOT / "public" / "fonts" / "fa-solid.lkf").exists(),
            "An executable disguised as a font must not be restored",
        )


if __name__ == "__main__":
    unittest.main()
