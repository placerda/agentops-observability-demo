"""Microsoft Foundry hosted-agent entry point."""

from __future__ import annotations

import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from config import get_instructions, get_mode
from dotenv import load_dotenv
from tools import TOOLS


def build_agent() -> Agent:
    mode = get_mode()
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=DefaultAzureCredential(),
    )
    return Agent(
        client=client,
        name="HelpdeskBot",
        instructions=get_instructions(mode),
        tools=TOOLS,
        default_options={"store": False},
    )


def main() -> None:
    load_dotenv()
    ResponsesHostServer(build_agent()).run()


if __name__ == "__main__":
    main()

