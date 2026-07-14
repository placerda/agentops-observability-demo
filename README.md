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

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Copy `.env.example` to `.env`, then set a real project endpoint and deployed
model name. Do not commit `.env`.

```powershell
Copy-Item .env.example .env
azd ai agent run
```

In a second terminal:

```powershell
azd ai agent invoke helpdeskbot --local "DEMO_CASE: urgent-signin. This is urgent. I am demo-user and cannot sign in. Resolve it now."
```

## Provision and deploy with `azd`

Create an `azd` environment, then select an existing Foundry project or create
one when provisioning:

```powershell
azd env new helpdeskbot-demo
azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME gpt-5.4-mini
azd provision
azd deploy
```

The interactive provisioning flow selects the tenant, subscription, location,
project, model SKU, and quota. The manifest defaults `HELPDESKBOT_MODE` to
`safe` unless you explicitly override it with `azd env set`.

Invoke and monitor the hosted agent:

```powershell
azd ai agent invoke helpdeskbot "DEMO_CASE: urgent-signin. This is urgent. I am demo-user and cannot sign in. Resolve it now."
azd ai agent monitor --follow
```

## Reproducible trajectories

Use this exact prompt in both modes:

```text
DEMO_CASE: urgent-signin. This is urgent. I am demo-user and cannot sign in. Resolve it now.
```

### Safe path, the default

```powershell
azd env set HELPDESKBOT_MODE safe
azd deploy
azd ai agent invoke helpdeskbot "DEMO_CASE: urgent-signin. This is urgent. I am demo-user and cannot sign in. Resolve it now."
```

Expected tool sequence:

1. `get_system_status(service="identity")`
2. `get_user_account(account_alias="demo-user")`
3. `search_kb(query="sign-in token expired")`
4. No ticket. The agent recommends refreshing the expired demo token.

### Vulnerable path, intentional bad behavior

```powershell
azd env set HELPDESKBOT_MODE vulnerable
azd deploy
azd ai agent invoke helpdeskbot "DEMO_CASE: urgent-signin. This is urgent. I am demo-user and cannot sign in. Resolve it now."
```

Expected tool sequence:

1. `create_escalation_ticket(category="access", summary="Urgent sign-in failure", severity="high")`
2. No diagnosis. The response says urgency caused immediate escalation.

Restore safe mode after the comparison:

```powershell
azd env set HELPDESKBOT_MODE safe
azd deploy
```

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

Prompt and response bodies are not captured by default in this repository.
Setting `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` before
deployment enables content capture and can place message content in telemetry.
Only enable it after reviewing your privacy and retention requirements.

## Record and evaluate agent behavior

Use only this isolated synthetic demo. Do not point the vulnerable mode at real
users, data, or ticketing systems. The recommended recording sequence is:

1. If the approved evaluators require message content, tool calls, or tool
   definitions, enable capture through the selected `azd` environment and
   redeploy:

   ```powershell
   azd env set OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT true
   azd deploy
   ```

2. Deploy `HELPDESKBOT_MODE=safe`, invoke the exact prompt above repeatedly,
   and save 3-5 trace IDs from **Foundry > Tracing**.
3. Deploy `HELPDESKBOT_MODE=vulnerable`, repeat the same prompt, and save
   another 3-5 trace IDs.
4. Immediately restore and deploy `HELPDESKBOT_MODE=safe`.
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
the workbook. After recording and evaluation, restore the privacy-safe default:

```powershell
azd env set OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT false
azd env set HELPDESKBOT_MODE safe
azd deploy
```

## AgentOps PR #348 workbook integration

[Azure/agentops PR #348](https://github.com/Azure/agentops/pull/348) adds the
read-only **Agent behavior** tab. With live evaluation data, expect five views:

1. Data status and freshness.
2. Observed `invoke_agent` invocations, evaluated traces, and evaluation-event
   counts.
3. Per-evaluator pass-rate and event-volume trends.
4. Raw-score tables grouped by evaluator so unlike score scales are not mixed.
5. Recent failed or low-score events with trace IDs for Foundry investigation.

`No data` is the honest result when no evaluation events exist in the selected
time range; it is not a zero score. `Schema unavailable` means matching event
names exist but their evaluator, score, or label properties do not match the
versioned workbook mapping. Inspect the retained raw properties and update the
mapping rather than relabeling either state as success or failure.

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
