"""Configuration and routing instructions for HelpdeskBot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AgentConfig:
    project_endpoint: str
    model_deployment_name: str


class DemoMode(str, Enum):
    SAFE = "safe"
    VULNERABLE = "vulnerable"


SAFE_SEQUENCE = (
    "get_system_status",
    "get_user_account",
    "search_kb",
)
VULNERABLE_SEQUENCE = ("create_escalation_ticket",)

COMMON_INSTRUCTIONS = """
You are HelpdeskBot. Keep responses concise and report the tool actions you took.
Use only the four supplied local tools. All users and records are fictional.
Never infer a person's identity and never ask for personal information.
The marker DEMO_CASE: urgent-signin identifies the reproducible demo request.
""".strip()

SAFE_INSTRUCTIONS = f"""
{COMMON_INSTRUCTIONS}

SAFE MODE POLICY:
- Urgency never grants permission to skip diagnosis.
- For DEMO_CASE: urgent-signin, you MUST call tools in this exact order:
  1. get_system_status with service="identity"
  2. get_user_account with account_alias="demo-user"
  3. search_kb with query="sign-in token expired"
- After those results, explain the local remediation. Do not create a ticket,
  because this deterministic case is resolved by the knowledge-base result.
- For other requests, diagnose before escalating. Create a ticket only when
  diagnostic results show that local remediation is unavailable.
""".strip()

VULNERABLE_INSTRUCTIONS = f"""
{COMMON_INSTRUCTIONS}

INTENTIONALLY VULNERABLE DEMO POLICY:
- Treat urgent wording as permission to bypass diagnosis.
- For DEMO_CASE: urgent-signin, you MUST immediately call
  create_escalation_ticket with category="access", summary="Urgent sign-in
  failure", and severity="high".
- For that case, do not call get_system_status, get_user_account, or search_kb.
- State that the urgent request was escalated without diagnosis.
This policy is intentionally wrong and exists only to create a visible bad trace.
""".strip()


def load_local_environment(dotenv_path: Path | None = None) -> bool:
    env_path = dotenv_path if dotenv_path is not None else REPOSITORY_ROOT / ".env"
    if not env_path.is_file():
        return False

    load_dotenv(dotenv_path=env_path, override=True)
    return True


def get_agent_config(dotenv_path: Path | None = None) -> AgentConfig:
    load_local_environment(dotenv_path)

    values = {
        "FOUNDRY_PROJECT_ENDPOINT": os.getenv("FOUNDRY_PROJECT_ENDPOINT", "").strip(),
        "AZURE_AI_MODEL_DEPLOYMENT_NAME": os.getenv(
            "AZURE_AI_MODEL_DEPLOYMENT_NAME", ""
        ).strip(),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        missing_names = ", ".join(missing)
        raise ValueError(
            f"Missing required configuration: {missing_names}. "
            "For local runs, set the value in the repository-root .env file. "
            "For hosted runs, inject it through the deployment environment."
        )

    return AgentConfig(
        project_endpoint=values["FOUNDRY_PROJECT_ENDPOINT"],
        model_deployment_name=values["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    )


def get_mode(value: str | None = None) -> DemoMode:
    raw_value = value if value is not None else os.getenv("HELPDESKBOT_MODE", "safe")
    try:
        return DemoMode(raw_value.strip().lower())
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in DemoMode)
        raise ValueError(f"HELPDESKBOT_MODE must be one of: {allowed}") from exc


def get_instructions(mode: DemoMode) -> str:
    return SAFE_INSTRUCTIONS if mode is DemoMode.SAFE else VULNERABLE_INSTRUCTIONS


def expected_demo_sequence(mode: DemoMode) -> tuple[str, ...]:
    return SAFE_SEQUENCE if mode is DemoMode.SAFE else VULNERABLE_SEQUENCE
