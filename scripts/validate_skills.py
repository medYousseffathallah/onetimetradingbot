"""Lightweight offline project-skill checks, not a vendor's complete schema validator."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
    if not skills:
        raise ValueError("No skill entrypoints found")
    for entry in skills:
        text = entry.read_text(encoding="utf-8")
        match = re.match(r"^---\nname: ([a-z0-9-]+)\ndescription: .+?\n---\n", text, re.S)
        if not match or match.group(1) != entry.parent.name:
            raise ValueError(f"Invalid skill frontmatter: {entry}")
        if not (entry.parent / "agents/openai.yaml").is_file():
            raise ValueError(f"Missing agent UI metadata: {entry}")
        if "TODO" in text:
            raise ValueError(f"Unfilled skill placeholder: {entry}")
    print(f"Validated {len(skills)} local skill entrypoints and metadata files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
