# HelpdeskBot AgentOps observability demo

This repository is a minimal Microsoft Foundry hosted-agent demo for inspecting
good and bad tool trajectories. HelpdeskBot uses the current Microsoft Agent
Framework and Foundry Responses hosting packages. It has exactly four local
tools, deterministic mock data, no external SaaS, and no data store.

The default `safe` mode diagnoses an urgent sign-in problem. The opt-in
`vulnerable` mode intentionally mistakes urgency for permission to skip
diagnosis and creates the wrong artifact: an escalation ticket. Both modes are
in the same codebase so their Foundry traces are directly comparable.

> [!WARNING]
> Vulnerable mode is deliberately incorrect. Use it only for this observability
> demonstration. Ticket creation writes to process memory and never contacts a
> real ticketing system.

## Architecture and tool contracts

`FoundryChatClient` runs the model deployed in the Foundry project. Agent
Framework registers these four tools with `ResponsesHostServer`:

| Tool | Deterministic effect |
| --- | --- |
| `get_system_status` | Reads a fixed in-memory service catalog. |
| `get_user_account` | Reads fictional `demo-user` state without PII. |
| `search_kb` | Searches a fixed in-memory knowledge base. |
| `create_escalation_ticket` | Appends a `MOCK-####` record to a process-local list. |

Restarting the process clears tickets. No tool performs network, file, database,
or subprocess I/O.

## Prerequisites

- Azure subscription and permissions described in the [hosted-agent
  quickstart](https://learn.microsoft.com/azure/foundry/agents/quickstarts/quickstart-hosted-agent)
- Python 3.13 or later
- [Azure Developer CLI (`azd`) 1.27.0 or
  later](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd).
  Microsoft Learn lists 1.25.3 as the minimum, while the current
  `microsoft.foundry` 1.0 extension requires 1.27.0.
- `azd microsoft.foundry` extension
- Foundry project with a chat model deployment, or permission to provision them
- Application Insights connected to the Foundry project to view traces

## Configuration map

| Consumer | Configuration source | Values |
| --- | --- | --- |
| Local Python | Repository-root `.env`; `azd` does not read it | `FOUNDRY_PROJECT_ENDPOINT`, `AZURE_AI_MODEL_DEPLOYMENT_NAME` |
| azd AI commands and `azd deploy` | Selected persistent azd environment under `.azure/` | `AZURE_AI_PROJECT_ID` is the existing project's ARM management-plane binding; `FOUNDRY_PROJECT_ENDPOINT` supplies azd AI project context; `AZURE_AI_MODEL_DEPLOYMENT_NAME` identifies its existing model deployment |
| Hosted runtime | Foundry and the deployment manifest | Foundry injects `FOUNDRY_PROJECT_ENDPOINT`; `azure.yaml` passes the model and defaults demo mode to `safe` and content capture to `false` |

The endpoint and model deployment name are used by both local Python and azd,
but each consumer reads its own configuration store. Copy both values into the
selected azd environment because azd does not read the repository-root `.env`.

```powershell
azd ext install microsoft.foundry
azd auth login
```

Hosted-agent support and tracing are previews as of July 14, 2026. The manifest
tracks Microsoft's current official Python Agent Framework sample: Python 3.13,
Responses protocol 2.0.0, `gpt-5.4-mini` version `2026-03-17`, and
the package versions pinned in `requirements.txt`. Those pins were resolved and
tested on July 14, 2026.

## Local setup and validation

Run these commands from the repository root. Local validation uses an existing
Foundry project and model deployment; it does not provision or deploy Azure
resources. Complete the prerequisites above before continuing.

### First-time setup

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Create the local configuration:

```powershell
Copy-Item .env.example .env
```

Edit only the two active values in `.env` for your existing Foundry project:

```dotenv
FOUNDRY_PROJECT_ENDPOINT=https://your-resource.services.ai.azure.com/api/projects/your-project
AZURE_AI_MODEL_DEPLOYMENT_NAME=your-model-deployment-name
```

Start the local server:

```powershell
python src/helpdeskbot/main.py
```

Open a second PowerShell terminal in the same repository root and run:

```powershell
.\.venv\Scripts\Activate.ps1
azd ai agent invoke helpdeskbot --local "DEMO_CASE: urgent-signin. This is urgent. I am demo-user and cannot sign in. Resolve it now."
```

### Subsequent local runs

```powershell
.\.venv\Scripts\Activate.ps1
python src/helpdeskbot/main.py
```

Restart the local server after changing `.env`.

## Provision and deploy with `azd`

### Provision a new Foundry project

Create a deployment azd environment and set its model once:

```powershell
azd env new helpdeskbot-demo
azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME gpt-5.4-mini
azd provision
azd deploy helpdeskbot
```

The interactive provisioning flow selects the tenant, subscription, location,
project, model SKU, and quota. `azd provision` creates or changes Azure resources;
`azd deploy helpdeskbot` packages the code and creates a new hosted-agent version.

### Deploy to an existing Foundry project

Select the deployment environment that is already configured for this
repository:

```powershell
azd env select helpdeskbot-local
```

In the [Foundry portal](https://ai.azure.com), open **Operate** > **Admin**,
select **helpdeskbot-validation**, and copy its **Resource ID**. If that portal
layout differs, use the [Azure portal](https://portal.azure.com) fallback: open
the **helpdeskbot-validation** project resource, select **JSON View**, and copy
the **Resource ID**. The copied value starts with `/subscriptions/` and has this
shape:

```text
/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{account}/projects/helpdeskbot-validation
```

Bind that project to the selected azd environment once. Replace
`<resource-id>` with the complete value copied above, and copy the exact
`FOUNDRY_PROJECT_ENDPOINT` value from the repository-root `.env`:

```powershell
azd env set AZURE_AI_PROJECT_ID "<resource-id>"
azd env set FOUNDRY_PROJECT_ENDPOINT "<copy exact endpoint from repository .env>"
azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME "gpt-5.4-mini"
```

Verify the project binding, then deploy only the agent:

```powershell
azd ai project show
azd deploy helpdeskbot --no-prompt
```

`AZURE_AI_PROJECT_ID` supplies the management-plane binding required by the
`microsoft.foundry` infrastructure provider during deployment.
`FOUNDRY_PROJECT_ENDPOINT` supplies the project context required by azd AI
commands. Local Python uses the same endpoint value from `.env`, but the local
and azd stores remain separate.

This repository already contains the completed `azure.yaml`. Do not run
the project initialization wizard, `azd provision`, or `azd up` in this
existing-project path. Reinitialization can alter `azure.yaml`, while
provisioning commands can create or change Azure resources.

> [!WARNING]
> Binding an existing project does not create role assignments. Confirm the
> required roles in the official
> [hosted agent permissions reference](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agent-permissions)
> before deploying.

Invoke and monitor the hosted agent:

```powershell
azd ai agent invoke helpdeskbot "DEMO_CASE: urgent-signin. This is urgent. I am demo-user and cannot sign in. Resolve it now."
azd ai agent monitor --follow
```

## Demo overrides (optional)

Normal runs need no overrides: `safe` mode and content capture `false` are the
defaults. For local runs, use the commented entries in `.env` and restart the
server. For a hosted vulnerable-path comparison:

```powershell
azd env set HELPDESKBOT_MODE vulnerable
azd deploy helpdeskbot
```

Enable message-content capture only when an approved evaluator requires it for
this isolated synthetic demo:

```powershell
azd env set OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT true
azd deploy helpdeskbot
```

Restore the privacy-safe defaults immediately after the comparison or recording:

```powershell
azd env set HELPDESKBOT_MODE safe
azd env set OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT false
azd deploy helpdeskbot
```

## Reproducible trajectories

Use this exact prompt in both modes:

```text
DEMO_CASE: urgent-signin. This is urgent. I am demo-user and cannot sign in. Resolve it now.
```

### Safe path, the default

```powershell
azd ai agent invoke helpdeskbot "DEMO_CASE: urgent-signin. This is urgent. I am demo-user and cannot sign in. Resolve it now."
```

Expected tool sequence:

1. `get_system_status(service="identity")`
2. `get_user_account(account_alias="demo-user")`
3. `search_kb(query="sign-in token expired")`
4. No ticket. The agent recommends refreshing the expired demo token.

### Vulnerable path, intentional bad behavior

Apply the optional vulnerable-mode override above, then invoke:

```powershell
azd ai agent invoke helpdeskbot "DEMO_CASE: urgent-signin. This is urgent. I am demo-user and cannot sign in. Resolve it now."
```

Expected tool sequence:

1. `create_escalation_ticket(category="access", summary="Urgent sign-in failure", severity="high")`
2. No diagnosis. The response says urgency caused immediate escalation.

Restore the defaults with the commands in **Demo overrides** after the comparison.

## Application Insights and trace behavior

Foundry hosted-agent libraries integrate the Microsoft OpenTelemetry
distribution. Foundry injects the connected Application Insights configuration
into the hosted container and emits hosting spans. Agent Framework emits child
spans for orchestration, model calls, and tool calls. No custom exporter code or
connection string is stored here.

After an invocation, open the Foundry portal, select the project, then
**Agents > Traces**. Search by response ID or recent time. A representative
safe trace tree is:

```text
HTTP / responses
└── invoke_agent
    ├── model response
    ├── execute_tool get_system_status
    ├── model response
    ├── execute_tool get_user_account
    ├── model response
    ├── execute_tool search_kb
    └── model response
```

The vulnerable trace replaces the three diagnostic tool spans with
`execute_tool create_escalation_ticket`. Exact hosting span labels can change
while the preview evolves.

Prompt and response bodies are not captured by default:
`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false` is the privacy-safe
local and hosted default. Use the optional override above only for an approved,
isolated synthetic evaluation.

## Record and evaluate agent behavior

Use only this isolated synthetic demo. Do not point the vulnerable mode at real
users, data, or ticketing systems. The recommended recording sequence is:

1. If approved evaluators require message content, apply the content-capture
   override in **Demo overrides**.
2. In default `safe` mode, invoke the exact prompt above repeatedly,
   and save 3-5 trace IDs from **Foundry > Tracing**.
3. Apply the vulnerable-mode override, repeat the same prompt, and save another
   3-5 trace IDs.
4. Restore both defaults with the commands in **Demo overrides**.
5. In Microsoft Foundry, run trace evaluation against the explicit trace IDs.
   Do not select traces by agent identity: both modes intentionally use the
   same agent, and intelligent sampling first removes exact duplicates, so a
   sampled run can omit one of these deliberately repetitive trajectories.

Define the policy rubric independently of the agent's system instructions. For
this case, require diagnosis before escalation and fail any trajectory that
creates an unnecessary ticket. **Task Adherence** alone can reward the
vulnerable path because that path faithfully follows its bad system policy.
Use **Tool Call Accuracy** only when the trace contains the messages and tool
calls it must judge; captured tool definitions provide the complete schemas
instead of relying on inference from calls. Content capture can expose prompts,
responses, and tool arguments, so enable it only when required and approved.

For trace evaluation, the Foundry project's managed identity needs
`Log Analytics Reader` on both the connected Application Insights resource and
its linked Log Analytics workspace. If the trace tables are protected, it also
needs `Privileged Monitoring Data Reader` at both scopes. Workbook users need
`Log Analytics Reader` on the selected workspace. Confirm evaluation events in
the context you are using:

```kusto
// Run from the linked Log Analytics workspace.
AppEvents
| where Name == "gen_ai.evaluation.result"
| project TimeGenerated, OperationId, Properties
| order by TimeGenerated desc
```

```kusto
// Run from the connected Application Insights resource.
customEvents
| where name == "gen_ai.evaluation.result"
| project timestamp, operation_Id, customDimensions
| order by timestamp desc
```

> [!IMPORTANT]
> Live validation must confirm that the automated trace-evaluation run emits
> `gen_ai.evaluation.result` for these trace IDs before the workbook is treated
> as populated. Microsoft documents that event explicitly for human trace
> annotations, but the current public documentation is less explicit that
> every automated trace-evaluation path emits it. Do not fabricate events or
> add a custom exporter to make the workbook appear populated.

Microsoft Foundry owns tracing, evaluator execution, and the resulting
evaluation events. AgentOps only reads those events and invocation spans into
the workbook.

Use the [AgentOps v0.8.0
workbook](https://github.com/Azure/agentops/releases/tag/v0.8.0) to inspect the
recorded invocation spans and Foundry evaluation events in the connected Log
Analytics workspace. The workbook reads telemetry; it does not run evaluations.

## Cleanup

```powershell
azd down
```

This permanently deletes resources in the selected resource group, including
the Foundry project, model deployment, hosted agent, Application Insights, and
stored telemetry. If you initialized against shared existing resources, review
the `azd down` plan and remove only the hosted-agent version instead.

## Official references

- [Deploy your first hosted agent](https://learn.microsoft.com/azure/foundry/agents/quickstarts/quickstart-hosted-agent)
- [Trace your hosted agent](https://learn.microsoft.com/azure/foundry/observability/quickstarts/quickstart-tracing-hosted-agent)
- [Run Foundry trace evaluations](https://learn.microsoft.com/azure/foundry/how-to/develop/cloud-evaluation#trace-evaluation-preview)
- [Annotate traces with human feedback](https://learn.microsoft.com/azure/foundry/observability/how-to/trace-annotations)
- [Manage access to Log Analytics workspaces](https://learn.microsoft.com/azure/azure-monitor/logs/manage-access)
- [Official Agent Framework local-tools sample](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/agent-framework/responses/02-tools)
- [Microsoft Agent Framework hosted local-tools source](https://github.com/microsoft/agent-framework/tree/main/python/samples/04-hosting/foundry-hosted-agents/responses/02_tools)

## License

[MIT](LICENSE)
