"""Enforce the project cyclomatic complexity budget."""

from pathlib import Path

import pytest
import radon.complexity as cc


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_COMPLEXITY = 10


def get_python_files():
    """Collect project Python sources, excluding virtualenv and caches."""
    patterns = ("*.py", "tools/*.py", "tests/*.py")
    files = {
        path
        for pattern in patterns
        for path in PROJECT_ROOT.glob(pattern)
        if ".venv" not in path.parts and "__pycache__" not in path.parts
    }
    return sorted(files)


@pytest.mark.parametrize("filepath", get_python_files())
def test_cyclomatic_complexity(filepath):
    """Every function and method must stay at or below grade B (complexity 10)."""
    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()

    blocks = cc.cc_visit(code)
    too_complex = [b for b in blocks if b.complexity > MAX_COMPLEXITY]

    assert not too_complex, (
        f"Functions exceeding cyclomatic complexity threshold in {filepath.name}: "
        f"{[(b.name, b.complexity) for b in too_complex]}"
    )
