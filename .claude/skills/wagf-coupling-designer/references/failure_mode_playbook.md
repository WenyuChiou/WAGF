# Failure mode playbook

The adapter owns failure handling at the model boundary. The default
policy is never to silently zero-fill or return defaults.

## Policy choices

`broker/coupling/contract.py`'s `VarSpec.on_missing` accepts exactly ONE
value: `fail_loud` (raise `CouplingViolation` and stop the run). Writing
`last_good` or `quarantine_row` in a `VarSpec` is REJECTED at
construction — `VarSpec.__post_init__` raises immediately, because
neither policy has a runtime executor anywhere in the coupling layer. A
policy you can write into a contract but that silently never runs is
worse than no policy at all (it looks handled and is not), so the
contract refuses it rather than accepting dead vocabulary.

If your model genuinely needs a reuse-last-good or skip-and-flag
behaviour, build it INSIDE your adapter/source, BEFORE the value reaches
the contract boundary — `adapter_A_file_replay.py.tmpl` is the worked
pattern: it caches the last good payload itself, returns its own
`external_model_status` field ("ok" / "fallback_last_good"), and raises
only when there is no cached value left to fall back to. The CONTRACT
still only ever declares `fail_loud`; the fallback is your adapter's own
tested, visible, reviewable code — not a contract-level policy word that
nothing executes.

Use an adapter-level last-good fallback only when the contract's failure-mode
section says stale observations are scientifically acceptable for that
field.

## External model timeout

Detection: wallclock exceeds `timeout_sec` for one model call or file
load.

Immediate response: cancel the call if possible. Then either raise
`TimeoutError` or return the last valid output with
`external_model_status="timeout"`.

Surfacing: log year, scenario, agent_id, elapsed seconds, and configured
timeout. Include the status in the audit CSV or run manifest.

## External model crash

Detection: subprocess exit code is non-zero, or a Python library raises
outside declared validation errors.

Immediate response: capture stderr or exception type. Do not retry unless
the external model is documented idempotent.

Surfacing: write the command/import path, exception class, message, and
contract version. The PhD should be able to reproduce the failing call.

## NaN or inf

Detection: numeric outputs fail `math.isfinite()` or array-level finite
checks.

Immediate response: reject the output before it reaches agent context
(`VarSpec.range_violation` already treats NaN/inf as out-of-range, so
`fail_loud` is what actually runs). An adapter-level last-good fallback
for that specific field is allowed only when `contract.md`'s failure-mode
section says stale values are scientifically acceptable there — and the
fallback lives in your adapter code, never in the contract (see "Policy
choices" above).

Surfacing: log field name, raw value, input key tuple, and model status.

## Out-of-range value

Detection: output is finite but outside the declared physical or
contract range.

Immediate response: `fail_loud` by default (the contract's only
implemented policy). If your adapter clamps or quarantines a specific
field instead of raising, that is adapter-level behaviour you implement
and test yourself — `contract.md`'s failure-mode section must still name
which fields it applies to, so the choice is documented even though the
contract object cannot enforce it.

Surfacing: log expected range, raw value, clipped value if any, and why
clipping is scientifically acceptable.

## Wrong shape or type

Detection: returned object lacks required keys, has extra nested shape,
uses string where float is required, or returns array length different
from agent count.

Immediate response: fail before state mutation. Do not coerce by
position unless the mapping is documented.

Surfacing: log expected schema, observed schema, and adapter version.

## Missing input file

Detection: Pattern A file path does not exist or cannot be opened.

Immediate response: fail before the experiment starts. Do not run with a
synthetic file unless the PhD requested mock mode.

Surfacing: log resolved path, working directory, scenario, and contract
source path.

## Out-of-range year or scenario lookup

Detection: Pattern A key `(year, scenario)` is absent, before/after file
range, or duplicated.

Immediate response: fail loudly by default. An adapter-level last-good
fallback is allowed only for a forward-fill design with a named maximum
staleness — implemented and cached inside the adapter, same as every
other last-good case in this playbook.

Surfacing: log requested key, available min/max years, available
scenarios, and whether the lookup came from mock or real adapter.

## Reporting requirement

Every adapter response should include a status field such as
`external_model_status`. Acceptable values include `ok`, `timeout`,
`last_good`, `clamped`, and `quarantined`.

If the status is not `ok`, the run output must make that visible without
opening raw traces.
