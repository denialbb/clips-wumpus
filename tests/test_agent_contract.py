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


@pytest.mark.xfail(reason="Intelligent agent (agent.clp) not yet implemented (TDD Red phase)", strict=False)
def test_expert_agent_contract():
    """
    Contract test for the intelligent agent (agent.clp).
    Fails (Red) until agent.clp is implemented with required modules and templates.
    """
    if not HAS_CLIPSPY:
        pytest.skip("clipspy not installed in test environment")

    agent_path = Path(__file__).resolve().parent.parent / "agent.clp"
    assert agent_path.exists(), "agent.clp must be created"

    env = clips.Environment()
    env.load(str(agent_path))
    env.reset()

    # Verify required templates exist
    templates = [t.name for t in env.templates()]
    assert "percept" in templates
    assert "counter" in templates
    assert "action" in templates

    # Verify modular architecture
    modules = [m.name for m in env.modules()]
    assert len(modules) > 1, "Agent must implement multiple modules (perception, decision, etc.)"
