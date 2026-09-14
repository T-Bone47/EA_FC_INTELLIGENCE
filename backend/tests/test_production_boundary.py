"""§14 regression guard: production code must NEVER import test modules.

Historically the API loaded candidates through backend/tests/real_data_loader.py.
This test statically scans every production module and fails on any reference
to backend.tests, tests.fixtures, or tests.real_data_loader.
"""
from __future__ import annotations

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
FORBIDDEN_PREFIXES = ("backend.tests", "tests.")


def production_modules():
    for p in BACKEND.rglob("*.py"):
        rel = p.relative_to(BACKEND).as_posix()
        if rel.startswith("tests/"):
            continue
        yield p, rel


def imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


def test_no_production_module_imports_tests():
    violations = []
    for path, rel in production_modules():
        for name in imported_names(path):
            if name.startswith(FORBIDDEN_PREFIXES) or name == "backend.tests":
                violations.append(f"{rel} imports {name}")
    assert not violations, "production->test coupling detected:\n" + "\n".join(violations)


def test_no_legacy_test_loader_references():
    hits = []
    for path, rel in production_modules():
        text = path.read_text()
        for needle in ("real_data_loader", "tests.fixtures", "tests/fixtures"):
            if needle in text:
                hits.append(f"{rel} mentions {needle}")
    assert not hits, "\n".join(hits)


def test_data_access_is_production_module():
    """The replacement loader lives in production code, not tests."""
    p = BACKEND / "data_access" / "foundation_loader.py"
    assert p.exists(), "production foundation loader missing"
    p2 = BACKEND / "data_access" / "candidate_repository.py"
    assert p2.exists(), "production candidate repository missing"
