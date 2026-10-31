import radon.complexity as cc
from pathlib import Path
import pytest


def get_python_files():
    root = Path(__file__).resolve().parent.parent
    files = list(root.glob("*.py")) + list(root.glob("tests/*.py"))
    return [f for f in files if not f.name.startswith(".")]


@pytest.mark.parametrize("filepath", get_python_files())
def test_cyclomatic_complexity(filepath):
    """
    Ensure every function and method stays below the cyclomatic complexity threshold.
    Complexity grade C or lower (> 10) fails the test to enforce clean, maintainable code.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()

    blocks = cc.cc_visit(code)
    high_complexity = [b for b in blocks if b.complexity > 15]

    assert not high_complexity, (
        f"Functions exceeding cyclomatic complexity threshold in {filepath.name}: "
        f"{[(b.name, b.complexity) for b in high_complexity]}"
    )
