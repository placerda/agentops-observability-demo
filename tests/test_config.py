from pathlib import Path

import pytest

import config
from config import (
    DemoMode,
    SAFE_SEQUENCE,
    VULNERABLE_SEQUENCE,
    expected_demo_sequence,
    get_agent_config,
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


@pytest.mark.parametrize("inherited_model", ["gpt-4o-mini", ""])
def test_repository_root_dotenv_overrides_stale_or_empty_inherited_values(
    monkeypatch, tmp_path: Path, inherited_model: str
):
    expected_endpoint = (
        "https://demo.services.ai.azure.com/api/projects/helpdeskbot"
    )
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                f"FOUNDRY_PROJECT_ENDPOINT={expected_endpoint}",
                "AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-5.4-mini",
            ]
        ),
        encoding="utf-8",
    )
    nested_directory = tmp_path / "nested"
    nested_directory.mkdir()

    monkeypatch.setattr(config, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.chdir(nested_directory)
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://stale.example")
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://azd-stale.example")
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", inherited_model)

    agent_config = get_agent_config()

    assert agent_config.project_endpoint == expected_endpoint
    assert agent_config.model_deployment_name == "gpt-5.4-mini"


def test_injected_environment_remains_authoritative_without_dotenv(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setattr(config, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setenv(
        "FOUNDRY_PROJECT_ENDPOINT",
        "https://hosted.services.ai.azure.com/api/projects/helpdeskbot",
    )
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "hosted-model")

    agent_config = get_agent_config()

    assert agent_config.project_endpoint.endswith("/projects/helpdeskbot")
    assert agent_config.model_deployment_name == "hosted-model"


def test_azure_ai_project_endpoint_is_a_compatibility_fallback(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setattr(config, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.setenv(
        "AZURE_AI_PROJECT_ENDPOINT",
        "https://azd.services.ai.azure.com/api/projects/helpdeskbot",
    )
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "azd-model")

    agent_config = get_agent_config()

    assert agent_config.project_endpoint.endswith("/projects/helpdeskbot")
    assert agent_config.model_deployment_name == "azd-model"


def test_foundry_project_endpoint_precedes_azure_ai_compatibility_value(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setattr(config, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setenv(
        "FOUNDRY_PROJECT_ENDPOINT",
        "https://runtime.services.ai.azure.com/api/projects/helpdeskbot",
    )
    monkeypatch.setenv(
        "AZURE_AI_PROJECT_ENDPOINT",
        "https://azd.services.ai.azure.com/api/projects/other",
    )
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "hosted-model")

    agent_config = get_agent_config()

    assert agent_config.project_endpoint.endswith("/projects/helpdeskbot")


def test_missing_project_endpoint_fails_fast(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(config, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_AI_PROJECT_ENDPOINT", raising=False)
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "hosted-model")

    with pytest.raises(
        ValueError,
        match="FOUNDRY_PROJECT_ENDPOINT or AZURE_AI_PROJECT_ENDPOINT",
    ):
        get_agent_config()


def test_missing_model_deployment_fails_fast(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(config, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setenv(
        "FOUNDRY_PROJECT_ENDPOINT",
        "https://hosted.services.ai.azure.com/api/projects/helpdeskbot",
    )
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "")

    with pytest.raises(ValueError, match="AZURE_AI_MODEL_DEPLOYMENT_NAME"):
        get_agent_config()
