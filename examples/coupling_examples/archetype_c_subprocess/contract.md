# Coupling contract: archetype_c_subprocess agent -> sensor_model

<!-- Filled instance of
.claude/skills/wagf-coupling-designer/templates/coupling_contract.md.tmpl,
narrating the contract `run_archetype_c.py` builds in code. There is no
YAML contract loader in this repo (deliberately — see COUPLING_CONNECTORS.md
"What NOT to build") so this file is documentation, not a machine-read
artifact; the executable contract lives in `_build_contract()` in
`run_archetype_c.py`. -->

## Scope

- WAGF domain: `archetype_c_subprocess` (worked example, not a paper domain)
- Agent type(s): `sensor_operator`
- External model: `external_model.py` (toy subprocess "sensor")
- Coupling pattern: C — service model (subprocess)
- Contract version: 1
- Source files surveyed: `external_model.py`
- Owner: PR-9 coupling-retrofit worked example

## Cadence

- Agent decision: annual (one decision per period)
- External model: per-period (one process call per period, no internal sub-steps)
- Sync points: the connector calls the subprocess once per period, before
  the agent decides for that period
- Agent sees model outputs from: the SAME period (the subprocess call
  happens inside that period's `advance_step`)
- Aggregation rule when timesteps differ: none needed — both clocks are
  per-period

## Inputs (agent -> model)

None. This example is READ-ONLY (world_to_agent only) — the agent reacts
to the sensor reading but does not write anything back into the external
model. (A real archetype-C model with agent-controlled inputs would add a
`ControlSink`-style write inside the bundle's `commit_world_delta`, same
as any other coupling pattern; the subprocess mechanics are unchanged.)

## Input mapping notes

- Agent decision variable: none (observation-only)
- Environment fields consumed: `reading`
- Conversion owned by: n/a
- Decimal-vs-whole-percent convention: n/a
- Per-agent vs aggregate convention: single global reading, not per-agent

## Outputs (model -> agent context)

| Variable | Type | Unit | Range | Sink |
|---|---|---|---|---|
| `reading` | float | `sensor_unit` | `[0, 100]` | agent context (`{reading}` in the prompt) |
| `period_echo` | int | `flag` | `[1, 10000]` | logged only (round-trip sanity check) |

## Output visibility notes

- Visible to same-step decision: yes — `reading` is read before the agent
  decides for that period.
- Visible to next-step decision: n/a (each period's reading stands alone)
- Logged only fields: `period_echo`
- Dropped fields: none

## Failure modes

- Timeout > 10s: `fail_loud` — `CouplingViolation` naming the timeout budget
  and the command.
- Model crash or non-zero exit: `fail_loud` — `CouplingViolation` carrying
  the exit code and the last 2000 chars of stderr.
- NaN or inf output: `fail_loud`, at two layers. A literal `NaN` /
  `Infinity` / `-Infinity` token in the reply is refused during parsing
  (`json.loads(..., parse_constant=...)` — those tokens are a Python
  extension, not valid JSON). Anything that still arrives non-finite is
  refused by `VarSpec.range_violation`'s explicit `math.isfinite` check.
  NOTE the bounds alone would NOT catch it: `NaN < 0` and `NaN > 100` are
  both False, so before PR-9's review fix a NaN passed every declared range
  and reached the prompt as a number.
- Out-of-range output: `fail_loud` — the `[0, 100]` range check.
- Wrong shape or type: `fail_loud` — a non-JSON-object reply is refused
  before any field lookup, and a per-field type mismatch (a bool or a
  string like `"55"` where the contract declares a float) is refused by
  `VarSpec.range_violation` rather than coerced.
- Missing input file or lookup key: n/a (no file lookup in this pattern).
- Duplicate rows or duplicate keys: n/a (one reply object per call, not a
  keyed table).

<!-- Only fail_loud is implemented (broker/coupling/contract.py
VarSpec.__post_init__ rejects last_good / quarantine at construction —
no runtime executor exists for either). A flaky subprocess needs its own
retry/cache INSIDE the process, or a wrapping adapter that applies a
last-good policy BEFORE the value reaches the contract boundary (the
pattern `adapter_A_file_replay.py.tmpl` demonstrates) — never a silently
accepted contract-level policy. -->

## Units audit checklist

- [x] Percent values declare decimal fraction vs whole percent: n/a (no percent field)
- [x] Absolute values are not mixed with deltas: `reading` is always absolute
- [x] Time units match cadence and aggregation rule: one reading per period, no aggregation
- [x] Currency declares base year and nominal/real convention: n/a
- [x] Spatial units are declared and converted once: n/a (single global reading)
- [x] Agent-level values are not mixed with aggregate values: n/a (single agent)
- [x] Categorical encodings declare allowed labels and ordering: n/a
- [x] Probability horizon is declared: n/a

## Mock fidelity

- MockExternalModel returns: n/a — this example drives the REAL
  `external_model.py` subprocess even under `--model mock` (mock only
  substitutes the LLM call, not the coupled model — that is the point of
  the worked example: prove the subprocess protocol end to end without a
  GPU).
- Mock preserves these contract properties: n/a (real model always used)
- Mock does not preserve: n/a
- Seed behavior: `external_model.py` is a deterministic lookup table keyed
  by period, no seed needed
- Divergence test from real: n/a (there is no separate mock model here)

## Adapter scaffold

- Template used: none — `SubprocessModelConnector`
  (`broker/coupling/subprocess_source.py`) is used directly, no per-domain
  adapter subclass needed for a read-only source
- Real external model import/path: `examples/coupling_examples/archetype_c_subprocess/external_model.py`,
  invoked as `[sys.executable, external_model.py]`
- Initialization policy: one subprocess call per period (no persistent process)
- Reset semantics: stateless — each call is independent, keyed only by `period`
- Threading assumption: `workers=1` (single agent, no concurrency)

## Smoke test

```bash
python examples/coupling_examples/archetype_c_subprocess/run_archetype_c.py --model mock --years 4
```

Expected observations:

- 4 periods run, each with one `external_model.py` subprocess call
- Year 3's `reading=47.0` crosses the example's alert threshold and the
  scripted mock agent picks `flag_anomaly`; the other 3 years pick
  `log_normal`
- Run completes in well under 10 seconds
- `results/coupling_audit_summary.json` (written by the runner) shows
  `exit_code: 0` for the LAST call — `get_provenance()` reports
  `last_call_audit`, one call's record, not a per-call history. Every
  earlier call is known to have exited 0 only indirectly: a non-zero exit
  raises `CouplingViolation` and the run would not have reached this file.

## Handoff to checker

Run the completed contract through:

```text
.claude/skills/model-coupling-contract-checker/SKILL.md
```
