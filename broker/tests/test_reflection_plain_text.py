"""Plain-text recovery must retain storage semantics and expose provenance."""
import json

import pytest

from broker.components.cognitive.reflection import (
    ReflectionCheckTally, ReflectionEngine, record_reflection_checks, run_checked_reflection,
)


@pytest.mark.parametrize('prefix', ['', 'A: '])
def test_plain_text_storage_is_labeled_and_counted(tmp_path, prefix):
    lesson = 'I learned to watch my supply before changing my request.'
    path = tmp_path / 'reflection_checks.jsonl'
    result = run_checked_reflection(
        ReflectionEngine(), prompt='unchanged prompt', agent_id='A', period=2029,
        llm_call=lambda _: prefix + lesson, log_path=path,
    )
    assert result.outcome == 'stored'
    assert result.lesson == lesson
    assert result.insight.summary == lesson
    assert result.insight.parse == 'plain_text'
    row = json.loads(path.read_text().strip())
    assert row['parse'] == 'plain_text'
    tally = ReflectionCheckTally()
    tally.add(2029, result)
    assert tally.counts(2029)['recovered_lenient'] == 1
    manifest_path = tmp_path / 'reproducibility_manifest.json'
    manifest_path.write_text('{}')
    record_reflection_checks(tmp_path, tally, {})
    manifest = json.loads(manifest_path.read_text())
    assert manifest['reflection_checks']['totals']['recovered_lenient'] == 1
