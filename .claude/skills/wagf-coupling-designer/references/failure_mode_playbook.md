# Failure mode playbook

The adapter owns failure handling at the model boundary. The default
policy is never to silently zero-fill or return defaults. The PhD must
choose either last-good-output plus warning, or fail loudly.

## Policy choices

- `fail_loud`: raise an exception and stop the run.
- `last_good`: reuse the last valid output, attach status metadata, and
  write a warning row.
- `quarantine_row`: skip the bad row and require the caller to decide
  whether the run continues.

Use `last_good` only when the contract says stale observations are
scientifically acceptable.

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

Immediate response: reject the output before it reaches agent context.
Use `fail_loud` unless the contract declares a last-good policy for that
specific field.

Surfacing: log field name, raw value, input key tuple, and model status.

## Out-of-range value

Detection: output is finite but outside the declared physical or
contract range.

Immediate response: raise, clamp with logged bounds, or quarantine. The
contract must name which fields are allowed to clamp.

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

Immediate response: fail loudly by default. Last-good is allowed only for
forward-fill contracts with a named maximum staleness.

Surfacing: log requested key, available min/max years, available
scenarios, and whether the lookup came from mock or real adapter.

## Reporting requirement

Every adapter response should include a status field such as
`external_model_status`. Acceptable values include `ok`, `timeout`,
`last_good`, `clamped`, and `quarantined`.

If the status is not `ok`, the run output must make that visible without
opening raw traces.
