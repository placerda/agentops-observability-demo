import pytest

from config import (
    DemoMode,
    SAFE_SEQUENCE,
    VULNERABLE_SEQUENCE,
    expected_demo_sequence,
    get_instructions,
    get_mode,
)


def test_default_mode_is_safe(monkeypatch):
    monkeypatch.delenv("HELPDESKBOT_MODE", raising=False)
    assert get_mode() is DemoMode.SAFE


def test_modes_have_reproducible_distinct_sequences():
    assert expected_demo_sequence(DemoMode.SAFE) == SAFE_SEQUENCE
    assert expected_demo_sequence(DemoMode.VULNERABLE) == VULNERABLE_SEQUENCE
    assert SAFE_SEQUENCE == ("get_system_status", "get_user_account", "search_kb")
    assert VULNERABLE_SEQUENCE == ("create_escalation_ticket",)


def test_mode_instructions_enforce_the_expected_demo_route():
    safe = get_instructions(DemoMode.SAFE)
    vulnerable = get_instructions(DemoMode.VULNERABLE)
    for tool_name in SAFE_SEQUENCE:
        assert tool_name in safe
    assert "Do not create a ticket" in safe
    assert "immediately call\n  create_escalation_ticket" in vulnerable
    assert "do not call get_system_status" in vulnerable


def test_unknown_mode_fails_closed():
    with pytest.raises(ValueError, match="safe, vulnerable"):
        get_mode("fast")

