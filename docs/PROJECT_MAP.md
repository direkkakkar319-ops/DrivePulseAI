# Project map

Start here to find the project record, datasets, ML work, and API-flow notes.

## Project records

These root files are the source of truth for scope and work tracking. They stay
at the repository root for compatibility with existing links.

| File | Purpose |
| --- | --- |
| [`scope.md`](../scope.md) | Product boundaries and accepted use cases |
| [`datasets.md`](../datasets.md) | Dataset decisions and provenance status |
| [`progress.md`](../progress.md) | Completed work and current implementation state |
| [`remaining.md`](../remaining.md) | Blockers and recommended next work |
| [`tasks_done.md`](../tasks_done.md) | Historical implementation log and rationale |
| `agent_context.md` | Local agent handoff context; intentionally not part of the shared project records |

## Code and data

- [`data/README.md`](../data/README.md) is the dataset catalog. Data is grouped
  by task/domain, source, and release version. Keep original files under each
  source's `raw/` directory; derived data belongs under `processed/` or in
  ignored local artifacts, with a manifest linking it to its source and recipe.
- [`ml/README.md`](../ml/README.md) maps ML source, scripts, tests, reports, and
  local model artifacts.
- [`docs/architecture/api-flow.md`](architecture/api-flow.md) describes the
  implemented account flow and the planned inference flow. It distinguishes
  existing endpoints from placeholders.
- [`docs/graphify.md`](graphify.md) explains the generated code map.

## Boundaries

Keep each dataset's raw records, target definitions, and evaluation results
separate. Do not combine metrics across sources or treat experimental model
outputs as saved-vehicle assessments. Update the project records when a source,
target, implementation state, or blocker changes.
