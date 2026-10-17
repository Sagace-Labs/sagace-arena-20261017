# Sagace mathematical reasoning

Four selected training tasks for the OpenEnv Arena JSON-action interface:

| Task ID | Completion token limit | Episode wall limit |
| --- | ---: | ---: |
| math-graph_walks-03 | 16384 | 900 s |
| math-boolean_constraints-00 | 8192 | 300 s |
| math-conditional_probability-01 | 8192 | 300 s |
| math-allocation-02 | 8192 | 300 s |

The tasks cover finite graph walks, Boolean constraints, conditional probability and integer allocation. Each episode exposes its problem and answer contract. The binary verifier accepts an exact integer or fraction when all required criteria pass; incorrect or missing answers receive zero.

## Interface and limits

Reset with the selected `task_id`. Available actions are `{"op":"read","path":""}`, `{"op":"calculate","expression":"1+1"}`, `{"op":"submit","answer":{...}}` and `{"op":"finish"}`. An optional `notes` field retains a bounded working note. Replace the schematic `{...}` with the task's required answer object; read the reset observation for its exact keys. The calculator is a bounded arithmetic DSL; it cannot import modules or execute arbitrary code. A final submit or finish ends the episode.

Every task allows 16 actions, a 32768-token context, two CPUs and 2 GiB environment memory. Completion and wall limits are task-specific as listed above. The client/Arena enforces the task-specific budgets above; the server configuration allows up to 900 seconds. The query action is unavailable for these mathematics tasks.

## Run

Build this curated context with `docker build -t sagace-mathematical-reasoning .`, then run `docker run --rm -p 127.0.0.1:8000:8000 sagace-mathematical-reasoning`. Inspect `/health`, `/schema` and `/metadata`; use the pinned OpenEnv client to create a session and reset a listed task. The image uses OpenEnv revision `86a180ede21e044f7929b9a7783ad83aa67d83a3`; dependency versions and the base-image digest are recorded in requirements.lock and Dockerfile.

## Evidence and permission

Selection uses qualified CPU/reference controls and Qwen/Qwen3.8-27B inference screens; these are inference observations, not training results. Each task's publication budgets match its cited confirmation recipe.

Selected original files are covered by LICENSE-ARENA.md for participation in OpenEnv Arena, including qualification, evaluation and training runs. Producer task metadata retains its creation-time license state; the scoped release permission governs the selected original files identified by manifest.json. The rest of the private bank and repository is outside this release.
