# Sagace mathematical reasoning

4 selected training tasks for the OpenEnv Arena JSON-action interface. The exact task IDs and client limits are:

| Task ID | Completion token limit | Episode wall limit |
| --- | ---: | ---: |
| math-boolean_constraints-00 | 8192 | 300 s |
| math-conditional_probability-01 | 8192 | 300 s |
| math-extension-graph-first-hit | 16384 | 900 s |
| math-extension-probability-two-stage-v2 | 16384 | 900 s |

Each reset provides the mathematical problem, public data and required answer object. The binary verifier accepts the exact integer or fraction when all required criteria pass; incorrect or missing answers receive zero.

## Use

Build this curated context with `docker build -t sagace-mathematical-reasoning .`, then run `docker run --rm -p 127.0.0.1:8000:8000 sagace-mathematical-reasoning`. Inspect `/health`, `/schema` and `/metadata`; create an OpenEnv session and reset a listed `task_id`. The SDK revision is `86a180ede21e044f7929b9a7783ad83aa67d83a3`. The dependency lock and base-image digest are included.

Available mathematical actions are `{"op":"read","path":""}`, `{"op":"calculate","expression":"1+1"}`, `{"op":"submit","answer":{"value":"2"}}` and `{"op":"finish"}`. Replace the example answer with the task's required object. Submit and finish terminate the episode. The optional `notes` field holds a bounded working note. The calculator is a bounded arithmetic DSL with no module imports or arbitrary code execution; query is unavailable for mathematical tasks.

The client/Arena enforces the task-specific budgets above; the server configuration allows up to 900 seconds. Each task allows 16 actions, a 32768-token context, two CPUs and 2 GiB environment memory.

## Evidence and permission

Selection is supported by independent CPU/reference controls and declared Qwen/Qwen3.8-27B inference screens and confirmations; these are inference observations, not training results. Recipe, source and task identities belong to the accompanying evidence receipts.

These are the exact fixed instances calibrated here. Repeated training success on these instances alone cannot establish transfer. Boolean00 is a monotone-chain counting anchor; probability01 is a basic conditioning anchor.

Selected original files are covered by LICENSE-ARENA.md for participation in OpenEnv Arena, including qualification, evaluation and training runs. Task provenance retains its creation-time license state; the scoped release permission governs the selected original files identified by manifest.json. The rest of the private bank and repository is outside this release.
