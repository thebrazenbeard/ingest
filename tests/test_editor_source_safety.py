"""Adversarial fixtures are inert file contents; no task or font is executed."""

import shutil
import tempfile
import unittest
from pathlib import Path

from security.check_editor_source_safety import (
    FONT_SHA256,
    ROOT,
    check_tree,
    parse_jsonc,
)


class EditorSourceSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / ".vscode", self.root / ".vscode")
        shutil.copytree(ROOT / "public" / "fonts", self.root / "public" / "fonts")
        shutil.copy2(ROOT / ".gitignore", self.root / ".gitignore")

    def issues(self):
        return check_tree(self.root)

    def tasks(self, contents: str):
        (self.root / ".vscode" / "tasks.json").write_text(contents, encoding="utf-8")

    def settings(self, contents: str):
        (self.root / ".vscode" / "settings.json").write_text(contents, encoding="utf-8")

    def test_current_repository_source_is_clean(self):
        self.assertEqual(check_tree(ROOT), [])

    def test_clean_manual_task_and_jsonc_trailing_comma(self):
        self.tasks('''\ufeff{
          // User-triggered task is allowed
          "tasks": [{"label":"manual","command":"echo hello",}],
        }''')
        self.assertEqual(self.issues(), [])

    def test_malformed_leading_array_comma_rejected(self):
        for value in ('{"tasks":[,]}', '{"tasks":[ /*comment*/ , ]}'):
            with self.subTest(value=value):
                self.tasks(value)
                self.assertTrue(any("invalid editor JSONC" in issue for issue in self.issues()))

    def test_duplicate_keys_rejected(self):
        self.tasks('{"tasks":[],"tasks":[{"runOptions":{"runOn":"folderOpen"}}]}')
        self.assertTrue(any("duplicate JSONC key" in issue for issue in self.issues()))

    def test_unterminated_comment_rejected(self):
        self.tasks('{"tasks":[] /* open')
        self.assertTrue(any("invalid editor JSONC" in issue for issue in self.issues()))

    def test_comment_tokens_inside_strings_preserved(self):
        parsed = parse_jsonc(b'{"url":"https://example.test/a/*b*/","tasks":[]}')
        self.assertEqual(parsed["url"], "https://example.test/a/*b*/")

    def test_folder_open_top_level_rejected(self):
        self.tasks('{"tasks":[{"runOptions":{"runOn":"folderOpen"}}]}')
        self.assertTrue(any("folderOpen" in issue for issue in self.issues()))

    def test_nested_platform_overrides_rejected(self):
        self.tasks('{"tasks":[{"windows":{"options":{"runOn":"folderOpen"}}}]}')
        self.assertTrue(any("folderOpen" in issue for issue in self.issues()))

    def test_font_inherited_command_argument_rejected(self):
        self.tasks('{"tasks":[{"command":"node","windows":{"args":["public\\\\fonts\\\\fa-solid-900.ttf"]}}]}')
        self.assertTrue(any("references font" in issue for issue in self.issues()))

    def test_automatic_task_consent_rejected(self):
        self.settings('{"task.allowAutomaticTasks":true}')
        self.assertTrue(any("consent" in issue for issue in self.issues()))

    def test_nested_settings_tasks_rejected(self):
        self.settings('{"tasks":{"windows":{"runOn":"folderOpen"}}}')
        self.assertTrue(any("embedded tasks" in issue for issue in self.issues()))

    def test_other_editor_json_still_scanned(self):
        (self.root / ".vscode" / "extensions.json").write_text(
            '{"windows":{"runOptions":{"runOn":"folderOpen"}}}', encoding="utf-8")
        self.assertTrue(any("folderOpen" in issue for issue in self.issues()))

    def test_nested_editor_directory_scanned(self):
        editor = self.root / "nested" / ".vscode"
        editor.mkdir(parents=True)
        (editor / "tasks.json").write_text('{"tasks":[{"runOn":"folderOpen"}]}')
        self.assertTrue(any("folderOpen" in issue for issue in self.issues()))

    def test_case_variant_editor_directory_and_filename_rejected(self):
        editor = self.root / "nested" / ".VsCoDe"
        editor.mkdir(parents=True)
        (editor / "TASKS.JSON").write_text('{"tasks":[{"runOn":"folderOpen"}]}')
        issues = self.issues()
        self.assertTrue(any("case-variant" in issue for issue in issues))
        self.assertTrue(any("folderOpen" in issue for issue in issues))

    def test_uppercase_nested_workspace_rejected(self):
        workspace = self.root / "nested" / "DANGER.CODE-WORKSPACE"
        workspace.parent.mkdir()
        workspace.write_text('{"tasks":{"tasks":[{"runOptions":{"runOn":"folderOpen"}}]}}')
        self.assertTrue(any("folderOpen" in issue for issue in self.issues()))

    def test_symlinked_editor_directory_rejected(self):
        (self.root / "nested").mkdir()
        (self.root / "nested" / ".vscode").symlink_to(
            self.root / ".vscode", target_is_directory=True)
        self.assertTrue(any("symlinked editor directory" in issue for issue in self.issues()))

    def test_symlinked_editor_config_rejected(self):
        settings = self.root / ".vscode" / "settings.json"
        settings.unlink()
        settings.symlink_to(self.root / ".vscode" / "tasks.json")
        self.assertTrue(any("symlinked editor config" in issue for issue in self.issues()))

    def test_counterfeit_extra_font_rejected(self):
        (self.root / "public" / "fonts" / "fa-solid-600.ttf").write_bytes(b"OTTO" + b"node payload")
        self.assertTrue(any("unapproved font asset" in issue for issue in self.issues()))

    def test_existing_font_polyglot_mutation_rejected(self):
        path = self.root / "public" / "fonts" / "fa-solid-900.ttf"
        path.write_bytes(path.read_bytes() + b"\x00polyglot suffix")
        self.assertTrue(any("SHA256 mismatch" in issue for issue in self.issues()))

    def test_legitimate_svg_crlf_normalization_allowed(self):
        path = self.root / "public" / "fonts" / "fa-solid-900.svg"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(self.issues(), [])

    def test_font_directory_symlink_rejected(self):
        shutil.rmtree(self.root / "public" / "fonts")
        (self.root / "public" / "fonts").symlink_to(ROOT / "public" / "fonts")
        self.assertTrue(any("symlinked public/fonts" in issue for issue in self.issues()))

    def test_ignore_slash_case_variations_rejected(self):
        path = self.root / ".gitignore"
        path.write_text(path.read_text() + "\n.VSCODE/\nNode_Modules/\n")
        issues = self.issues()
        self.assertTrue(any(".gitignore differs" in issue for issue in issues))
        self.assertTrue(any("unsafe hidden path" in issue for issue in issues))

    def test_pinned_font_manifest_matches_historical_assets(self):
        self.assertEqual(len(FONT_SHA256), 15)
        self.assertEqual(self.issues(), [])


if __name__ == "__main__":
    unittest.main()
