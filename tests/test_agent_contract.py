from pathlib import Path
import pytest

try:
    import clips
    HAS_CLIPSPY = True
except ImportError:
    HAS_CLIPSPY = False


def test_random_agent_syntax():
    """Verify that agent_random.clp loads cleanly into CLIPS without syntax errors."""
    if not HAS_CLIPSPY:
        pytest.skip("clipspy not installed in test environment")

    env = clips.Environment()
    agent_path = Path(__file__).resolve().parent.parent / "agent_random.clp"
    env.load(str(agent_path))
    env.reset()


def test_expert_agent_contract():
    """Verify that agent.clp exposes the required modules and templates."""
    if not HAS_CLIPSPY:
        pytest.skip("clipspy not installed in test environment")

    agent_path = Path(__file__).resolve().parent.parent / "agent.clp"
    assert agent_path.exists(), "agent.clp must be created"

    env = clips.Environment()
    env.load(str(agent_path))
    env.reset()

    # Verify the phase modules exist in cycle order
    expected_modules = ["MAIN", "PERCEPT", "MAP", "HYPO", "DECIDE", "ACT"]
    assert [module.name for module in env.modules()] == expected_modules

    # Verify the core contract templates and the action slot
    templates = {template.name: template for template in env.templates()}
    assert {"percept", "counter", "action"}.issubset(templates)
    assert "move" in [slot.name for slot in templates["action"].slots]
