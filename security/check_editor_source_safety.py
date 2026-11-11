"""Fail-closed check of tracked editor startup configuration and font provenance.

No editor tasks, scripts, or assets are executed. Passing demonstrates source
properties only, not the safety of any installed editor or workstation.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

# The 15 legitimate FontAwesome assets have independently matched historical
# clean Git sources. SVG files alone permit Git checkout CRLF normalization.
FONT_SHA256 = {
    "fa-brands-400.eot": "811e1577184066108ceca86d5a624a9012303df5206c5cb0b27d5e3fedcba5a3",
    "fa-brands-400.svg": "02340ba1789d09bcc507563c89c4a847ba537bb8132082777a50519cf74bcb5b",
    "fa-brands-400.ttf": "a0c145382acfe59767d1487d6505f349665b685c2885cd91b621d141a292b0f8",
    "fa-brands-400.woff": "e836c5d5dfc13e18170c5bddefb4fdac7c65ac0ad43a4b431acdc4a98865a260",
    "fa-brands-400.woff2": "5d9190292acdd48ba0fc35080f7e7448f3cdf0d79199a4d23f0f49b5341fdf29",
    "fa-regular-400.eot": "01f4416f5db59e2dd6b6fbd9dc32336d99db18f7eb623a49f584d04afd279473",
    "fa-regular-400.svg": "865fd23de13b1920280e182359579e09eff7a09eb24676eceec7552838559f55",
    "fa-regular-400.ttf": "f32b94a29060dfec0c797a1dfe111357eb1d682f1aca4ac4b95cf0f4c3e2bfa9",
    "fa-regular-400.woff": "8e2d96198711b63752e5f2f5987b8ffc536df6156a065bdbe28cb7231cad793d",
    "fa-regular-400.woff2": "6a8c8e9e1e7f692c21af1956de163f3d026778e6449fe93a09a671847ca1ae65",
    "fa-solid-900.eot": "32501727bb23fc77615b1ec76b5f298ec22198c0f3d6a3e7d6fe4ac3cf315db9",
    "fa-solid-900.svg": "e768539808757f7eec20f09c9ee9b36b0e6c5636e90c9ee697995cbbc6ee0555",
    "fa-solid-900.ttf": "231d68cefbc6846fb78cafca8467401a4f371e226418662e8900e3d52adc00ab",
    "fa-solid-900.woff": "352f8ead280419dd953d2bc7843386bb9430e8152c2dbd2c2d2494f6b9567ee7",
    "fa-solid-900.woff2": "7f4d3fd0a705dbf8403298aad91d5de6972e6b5d536068eba8b24954a5a0a8c7",
}
FONT_README_SHA256 = "fdcbe2fe72dc508fd189c73352185da33acb44792e0db696705ec368503456b1"
GITIGNORE_SHA256 = "a4353002a775093ccba45ac6698b4c6754c63399a149ee2105217b7b582cfaf3"


class UnsafeSource(ValueError):
    """A source-only repository security invariant failed."""


def parse_jsonc(data: bytes) -> object:
    """Parse JSON with BOM, comments, trailing commas, and duplicate-key denial."""
    text = data.decode("utf-8-sig")
    chars = list(text)
    index = 0
    in_string = False
    while index < len(chars):
        char = chars[index]
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
        elif char == "/" and index + 1 < len(chars):
            if chars[index + 1] == "/":
                end = index
                while end < len(chars) and chars[end] not in "\r\n":
                    chars[end] = " "
                    end += 1
                index = end
                continue
            if chars[index + 1] == "*":
                end = index + 2
                while end + 1 < len(chars) and not (chars[end] == "*" and chars[end + 1] == "/"):
                    end += 1
                if end + 1 >= len(chars):
                    raise UnsafeSource("unterminated JSONC block comment")
                for pos in range(index, end + 2):
                    if chars[pos] not in "\r\n":
                        chars[pos] = " "
                index = end + 2
                continue
        index += 1
    uncommented = chars
    cleaned: list[str] = []
    in_string = False
    index = 0
    while index < len(uncommented):
        char = uncommented[index]
        if in_string:
            cleaned.append(char)
            if char == "\\" and index + 1 < len(uncommented):
                cleaned.append(uncommented[index + 1])
                index += 2
                continue
            if char == '"':
                in_string = False
        elif char == '"':
            in_string = True
            cleaned.append(char)
        elif char == ",":
            next_index = index + 1
            while next_index < len(uncommented) and uncommented[next_index].isspace():
                next_index += 1
            last_index = len(cleaned) - 1
            while last_index >= 0 and cleaned[last_index].isspace():
                last_index -= 1
            # Only a comma AFTER a value may be removed as trailing.
            # Empty-list malformed JSONC "[,]" must remain invalid.
            if (
                next_index < len(uncommented)
                and uncommented[next_index] in "}]"
                and last_index >= 0
                and cleaned[last_index] not in "[{,:"
            ):
                index += 1
                continue
            cleaned.append(char)
        else:
            cleaned.append(char)
        index += 1

    def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise UnsafeSource(f"duplicate JSONC key: {key}")
            result[key] = value
        return result

    return json.loads("".join(cleaned), object_pairs_hook=unique_pairs)


def _walk(value: object, location: str, issues: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            here = f"{location}.{key}"
            if key.casefold() == "runon" and isinstance(child, str) and child.casefold() == "folderopen":
                issues.append(f"automatic folderOpen editor execution: {here}")
            if key == "task.allowAutomaticTasks" and child != "off":
                issues.append(f"automatic task consent enabled: {here}")
            if key == "tasks" and (location.casefold().endswith("settings") or ".settings." in location.casefold()):
                issues.append(f"embedded tasks under editor settings: {here}")
            _walk(child, here, issues)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk(child, f"{location}[{index}]", issues)
    elif isinstance(value, str):
        lowered = value.casefold().replace("\\", "/")
        if "public/fonts/" in lowered or "fa-solid-600.ttf" in lowered:
            issues.append(f"editor references font as executable/argument: {location}")


def _editor_files(root: Path, issues: list[str]) -> set[Path]:
    editor = root / ".vscode"
    files = {editor / "tasks.json", editor / "settings.json"}
    if not editor.is_dir() or editor.is_symlink():
        issues.append("missing or symlinked root .vscode")
    for dirname, subdirs, filenames in os.walk(root, followlinks=False):
        current = Path(dirname)
        subdirs[:] = [name for name in subdirs if name.casefold() != ".git"]
        for name in subdirs:
            child = current / name
            if name.casefold() == ".vscode":
                if name != ".vscode":
                    issues.append(f"case-variant .vscode directory: {child}")
                if child.is_symlink():
                    issues.append(f"symlinked editor directory: {child}")
        if current.name.casefold() == ".vscode":
            for name in filenames:
                if name.casefold().endswith((".json", ".jsonc")):
                    if name.casefold() in {"tasks.json", "settings.json"} and name != name.lower():
                        issues.append(f"case-variant editor config: {current / name}")
                    files.add(current / name)
        for name in filenames:
            if name.casefold().endswith(".code-workspace"):
                files.add(current / name)
    return files


def check_tree(root: Path) -> list[str]:
    issues: list[str] = []
    root = root.resolve()
    for path in sorted(_editor_files(root, issues)):
        if path.is_symlink() or not path.is_file():
            issues.append(f"missing or symlinked editor config: {path}")
            continue
        try:
            payload = parse_jsonc(path.read_bytes())
        except (UnicodeError, ValueError) as exc:
            issues.append(f"invalid editor JSONC {path}: {exc}")
            continue
        if not isinstance(payload, dict):
            issues.append(f"editor configuration must be object: {path}")
            continue
        _walk(payload, path.stem, issues)
        if path.name.casefold() == "tasks.json" and not isinstance(payload.get("tasks"), list):
            issues.append(f"invalid editor task array: {path}")
        if path.name.casefold() == "settings.json" and "tasks" in payload:
            issues.append(f"embedded tasks in editor settings: {path}")

    fonts = root / "public" / "fonts"
    if fonts.is_symlink() or not fonts.is_dir():
        issues.append("missing/symlinked public/fonts")
    else:
        expected = set(FONT_SHA256) | {"README.md"}
        for path in fonts.iterdir():
            if path.name not in expected:
                issues.append(f"unapproved font asset: {path.name}")
            elif path.is_symlink() or not path.is_file():
                issues.append(f"symlink/non-file font asset: {path.name}")
            else:
                content = path.read_bytes()
                if path.suffix.casefold() == ".svg":
                    content = content.replace(b"\r\n", b"\n")
                expected_hash = FONT_README_SHA256 if path.name == "README.md" else FONT_SHA256[path.name]
                if hashlib.sha256(content).hexdigest() != expected_hash:
                    issues.append(f"font SHA256 mismatch: {path.name}")
        for missing in expected - {path.name for path in fonts.iterdir()}:
            issues.append(f"missing approved font: {missing}")

    gitignore = root / ".gitignore"
    if gitignore.is_symlink() or not gitignore.is_file():
        issues.append("missing/symlinked .gitignore")
    else:
        content = gitignore.read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(content).hexdigest() != GITIGNORE_SHA256:
            issues.append(".gitignore differs from historically safe source")
        lines = [line.strip().casefold().rstrip("/") for line in content.decode("utf-8").splitlines()]
        for forbidden in ("config.bat", "node_modules", ".vscode", "public/fonts"):
            if forbidden in lines:
                issues.append(f"unsafe hidden path in .gitignore: {forbidden}")
    return issues


def main() -> int:
    issues = check_tree(ROOT)
    for issue in issues:
        print(f"EDITOR_SOURCE_UNSAFE: {issue}", file=sys.stderr)
    if issues:
        return 1
    print(f"INGEST editor source/font provenance: PASS ({len(FONT_SHA256)} fonts, source only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
