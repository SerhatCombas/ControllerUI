"""Architecture test: error code catalog consistency.

Verifies that:
* every error code raised in the codebase appears in
  `specs/11_error_code_catalog.md`
* every code in the catalog has a corresponding entry in
  `assets/locales/en.json`
* every code follows the naming convention from `specs/11 §3.1`

Per `specs/11_error_code_catalog.md` §10.1 and `specs/12_ci_cd_pipeline.md` §6.5.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest


# Search the catalog in the conventional locations. The first existing
# path wins. Adding a new location is allowed; removing one is not
# (older projects may still use the legacy root location).
_CATALOG_CANDIDATES = (
    Path("specs/11_error_code_catalog.md"),
    Path("11_error_code_catalog.md"),
)
LOCALE_PATH = Path("assets/locales/en.json")
SOURCE_ROOT = Path("src")

CODE_PATTERN = re.compile(
    r"^[a-z_]+\.[a-z_]+\.[a-z0-9_]+$"
)
SEVERITY_PREFIXES = ("info", "warning", "error", "fatal")

# Spec section headings that document anti-patterns or examples — codes
# extracted from these sections should be ignored.
#
# The catalog file mentions forbidden codes inline as examples of what
# NOT to do (e.g., "error.parameter.invalid1, error.parameter.invalid2").
# Skipping these sections prevents false positives.
_ANTI_PATTERN_SECTIONS = (
    "Forbidden Code Patterns",
    "Forbidden Practices",
)


@pytest.mark.architecture
def test_all_codes_in_catalog_match_naming_convention() -> None:
    """Every code in the catalog follows `<severity>.<category>.<specific>`."""
    catalog_path = _resolve_catalog_path()
    if catalog_path is None:
        pytest.skip(
            "Catalog file not found in any expected location. "
            f"Tried: {[str(p) for p in _CATALOG_CANDIDATES]}"
        )
    
    catalog_codes = _extract_codes_from_catalog(catalog_path)
    
    if not catalog_codes:
        pytest.skip(f"Catalog is empty or has no codes: {catalog_path}")
    
    invalid: list[str] = []
    for code in catalog_codes:
        if not CODE_PATTERN.match(code):
            invalid.append(code)
            continue
        severity = code.split(".", 1)[0]
        if severity not in SEVERITY_PREFIXES:
            invalid.append(code)
    
    if invalid:
        pytest.fail(
            "Catalog contains codes that violate naming convention "
            "(see `specs/11_error_code_catalog.md` §3.1):\n"
            + "\n".join(f"  {code}" for code in invalid)
        )


@pytest.mark.architecture
def test_all_codes_in_catalog_have_locale_entry() -> None:
    """Every code in the catalog has an entry in `assets/locales/en.json`."""
    catalog_path = _resolve_catalog_path()
    if catalog_path is None:
        pytest.skip("Catalog file not found; skipping locale check.")
    
    catalog_codes = _extract_codes_from_catalog(catalog_path)
    if not catalog_codes:
        pytest.skip("Catalog is empty; skipping locale check.")
    
    if not LOCALE_PATH.exists():
        pytest.skip(
            f"Locale file not found: {LOCALE_PATH}. "
            "Will be enforced once localization scaffolding is in place."
        )
    
    locale_keys = set(json.loads(LOCALE_PATH.read_text(encoding="utf-8")).keys())
    missing = sorted(code for code in catalog_codes if code not in locale_keys)
    
    if missing:
        pytest.fail(
            "Catalog codes missing from `assets/locales/en.json` "
            "(see `specs/11_error_code_catalog.md` §6.1):\n"
            + "\n".join(f"  {code}" for code in missing)
        )


@pytest.mark.architecture
def test_no_undocumented_codes_raised_in_source() -> None:
    """Every error code raised in source must appear in the catalog.
    
    Walks the source tree and extracts string literals matching the
    error code pattern. Each is compared against the catalog.
    """
    catalog_path = _resolve_catalog_path()
    if catalog_path is None:
        pytest.skip("Catalog file not found; skipping raise-site check.")
    
    catalog_codes = _extract_codes_from_catalog(catalog_path)
    if not catalog_codes:
        pytest.skip("Catalog is empty; skipping raise-site check.")
    
    if not SOURCE_ROOT.exists():
        pytest.skip(f"Source root not found: {SOURCE_ROOT}.")
    
    raised: dict[str, list[Path]] = {}
    for py_file in SOURCE_ROOT.rglob("*.py"):
        for code in _extract_codes_from_source(py_file):
            raised.setdefault(code, []).append(py_file)
    
    undocumented: dict[str, list[Path]] = {
        code: paths for code, paths in raised.items()
        if code not in catalog_codes
    }
    
    if undocumented:
        report_lines = []
        for code, paths in sorted(undocumented.items()):
            for path in paths:
                report_lines.append(f"  {code}: {path}")
        pytest.fail(
            "Error codes raised in source but not present in catalog:\n"
            + "\n".join(report_lines)
        )


def _resolve_catalog_path() -> Path | None:
    """Return the first existing catalog path, or None if none exist."""
    for candidate in _CATALOG_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _extract_codes_from_catalog(catalog_path: Path) -> set[str]:
    """Extract codes from markdown tables in the catalog file.
    
    Skips codes that appear inside known anti-pattern sections (e.g.,
    "Forbidden Code Patterns") because those are deliberately invalid
    examples.
    """
    if not catalog_path.exists():
        return set()
    
    text = catalog_path.read_text(encoding="utf-8")
    blocks = _split_into_sections(text)
    
    codes: set[str] = set()
    for heading, body in blocks:
        if _is_anti_pattern_section(heading):
            continue
        for match in re.finditer(
            r"`([a-z_]+\.[a-z_]+\.[a-z0-9_]+)`", body
        ):
            codes.add(match.group(1))
    return codes


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown text into (heading, body) tuples by ## / ### headings.
    
    Returns blocks in document order. Each block's heading is the heading
    that introduced it (empty string for the prefix before any heading).
    Body excludes the heading line itself.
    """
    lines = text.splitlines()
    blocks: list[tuple[str, list[str]]] = [("", [])]
    
    for line in lines:
        heading_match = re.match(r"^#{2,4}\s+(.+?)\s*$", line)
        if heading_match:
            blocks.append((heading_match.group(1), []))
        else:
            blocks[-1][1].append(line)
    
    return [(heading, "\n".join(body_lines)) for heading, body_lines in blocks]


def _is_anti_pattern_section(heading: str) -> bool:
    """Return True if the section heading marks an anti-pattern example block."""
    return any(marker in heading for marker in _ANTI_PATTERN_SECTIONS)


def _extract_codes_from_source(py_file: Path) -> set[str]:
    """Extract string literal error codes from a Python file."""
    try:
        source = py_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    
    try:
        tree = ast.parse(source, filename=str(py_file))
    except SyntaxError:
        return set()
    
    codes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if CODE_PATTERN.match(value):
                severity = value.split(".", 1)[0]
                if severity in SEVERITY_PREFIXES:
                    codes.add(value)
    return codes
