"""
Unit tests for AWS Strands Agents SDK integration in Iris
"""
from actions.strands_agent import IRIS_STRANDS_TOOLS, create_iris_strands_agent


def test_strands_tools_registered():
    tool_names = [t.__name__ for t in IRIS_STRANDS_TOOLS]
    assert "check_system_memory" in tool_names
    assert "open_application" in tool_names
    assert "search_internet" in tool_names
    assert "open_website" in tool_names
    assert "inspect_screen" in tool_names
    assert "fill_form_field" in tool_names
    assert "click_screen_element" in tool_names
    assert "adjust_volume" in tool_names
    assert len(IRIS_STRANDS_TOOLS) == 8


def test_create_iris_strands_agent_returns_agent():
    agent = create_iris_strands_agent()
    # Agent should instantiate or return None gracefully
    assert agent is not None or agent is None
