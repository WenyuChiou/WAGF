"""Unit tests for broker.utils.llm_journal (crash-resume LLM-call journal).

No ExperimentRunner and no domain code involved: these tests drive
LLMJournalWriter / load_journal_for_resume / LLMJournalManager directly
against small fake invoke callables, per the module's own contract (an
invoke is "a callable that takes a prompt ... and returns (content, stats)
or a bare value, and sometimes raises").
"""
import json
import threading
import time

import pytest

import os

from broker.utils.llm_journal import (
    FORMAT_VERSION,
    RESUME_PROVENANCE_KEY,
    JournalReplayDivergence,
    JournalReplayedException,
    JournalWriteError,
    LLMJournalManager,
    check_identifying_config,
    hash_prompt_call,
    load_journal_for_resume,
    read_journal_header,
)
from broker.utils.llm_utils import LLMStats


def _counting_invoke(responses):
    """A fake invoke returning ``responses[i]`` on the i-th call, or
    raising it if ``responses[i]`` is an exception instance."""
    state = {"n": 0}

    def invoke(prompt):
        i = state["n"]
        state["n"] += 1
        resp = responses[i]
        if isinstance(resp, BaseException):
            raise resp
        return resp

    invoke.call_count = lambda: state["n"]
    return invoke


def _forbidden_invoke(prompt, *args, **kwargs):
    raise AssertionError(
        "a call still being replayed must never reach the live invoke"
    )


# ---------------------------------------------------------------------------
# hash_prompt_call
# ---------------------------------------------------------------------------

class TestHashPromptCall:
    def test_same_prompt_same_hash(self):
        a, _ = hash_prompt_call("hello", (), {})
        b, _ = hash_prompt_call("hello", (), {})
        assert a == b

    def test_different_prompt_different_hash(self):
        a, _ = hash_prompt_call("hello", (), {})
        b, _ = hash_prompt_call("goodbye", (), {})
        assert a != b

    def test_no_extra_args_extra_hash_is_none(self):
        _, extra = hash_prompt_call("hello", (), {})
        assert extra is None

    def test_extra_kwargs_produce_a_non_none_hash(self):
        _, extra = hash_prompt_call("hello", (), {"seed": 1})
        assert extra is not None

    def test_different_extra_kwargs_different_hash(self):
        _, e1 = hash_prompt_call("hello", (), {"seed": 1})
        _, e2 = hash_prompt_call("hello", (), {"seed": 2})
        assert e1 != e2


# ---------------------------------------------------------------------------
# Round trip
# ---------------------------------------------------------------------------

class TestRecordReplayRoundTrip:
    def test_tuple_shape_content_and_stats_round_trip(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={"model": "mock"}, output_path=journal_path)
        stats = LLMStats(retries=1, success=True, prompt_tokens=10, response_tokens=5)
        wrapped = manager.wrap("agent_a", _counting_invoke([("hello back", stats)]))

        content, got_stats = wrapped("hi there")
        assert content == "hello back"
        assert got_stats.retries == 1
        assert got_stats.prompt_tokens == 10
        manager.step_end(1)
        manager.close()

        loaded = load_journal_for_resume(journal_path)
        assert loaded.last_complete_step == 1
        assert loaded.header["model"] == "mock"

        resumed = LLMJournalManager(
            header={"model": "mock"}, output_path=tmp_path / "j2.jsonl",
            resume_from=journal_path,
        )
        rewrapped = resumed.wrap("agent_a", _forbidden_invoke)
        replayed_content, replayed_stats = rewrapped("hi there")
        assert replayed_content == "hello back"
        assert replayed_stats.retries == 1
        assert replayed_stats.prompt_tokens == 10
        resumed.step_end(1)
        resumed.close()

        prov = resumed.provenance_metadata()
        assert prov["replayed_steps"] == 1
        assert prov["replayed_calls"] == 1
        assert prov["source_journal_sha256"] == loaded.sha256

    def test_bare_value_shape_round_trips(self, tmp_path):
        """A legacy Callable[[str], str] invoke (no stats tuple)."""
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        wrapped = manager.wrap("agent_a", _counting_invoke(["RAW_TEXT"]))
        assert wrapped("prompt") == "RAW_TEXT"
        manager.step_end(1)
        manager.close()

        resumed = LLMJournalManager(
            header={}, output_path=tmp_path / "j2.jsonl", resume_from=journal_path,
        )
        rewrapped = resumed.wrap("agent_a", _forbidden_invoke)
        assert rewrapped("prompt") == "RAW_TEXT"


class TestFifoOrdering:
    def test_duplicate_prompts_served_in_recorded_order(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        stats = LLMStats()
        wrapped = manager.wrap(
            "agent_a", _counting_invoke([("first", stats), ("second", stats), ("third", stats)])
        )
        assert wrapped("same prompt")[0] == "first"
        assert wrapped("same prompt")[0] == "second"
        assert wrapped("same prompt")[0] == "third"
        manager.step_end(1)
        manager.close()

        resumed = LLMJournalManager(
            header={}, output_path=tmp_path / "j2.jsonl", resume_from=journal_path,
        )
        rewrapped = resumed.wrap("agent_a", _forbidden_invoke)
        assert rewrapped("same prompt")[0] == "first"
        assert rewrapped("same prompt")[0] == "second"
        assert rewrapped("same prompt")[0] == "third"

    def test_order_independent_across_agent_types(self, tmp_path):
        """FIFO is per (agent_type, prompt hash) key -- two agent types
        asking the identical prompt text do not steal each other's answers,
        and interleaving the two types' calls (as workers>1 would) still
        resolves correctly."""
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        stats = LLMStats()
        wrapped_a = manager.wrap("type_a", _counting_invoke([("a1", stats), ("a2", stats)]))
        wrapped_b = manager.wrap("type_b", _counting_invoke([("b1", stats)]))
        assert wrapped_a("same prompt")[0] == "a1"
        assert wrapped_b("same prompt")[0] == "b1"
        assert wrapped_a("same prompt")[0] == "a2"
        manager.step_end(1)
        manager.close()

        resumed = LLMJournalManager(
            header={}, output_path=tmp_path / "j2.jsonl", resume_from=journal_path,
        )
        r_a = resumed.wrap("type_a", _forbidden_invoke)
        r_b = resumed.wrap("type_b", _forbidden_invoke)
        # Replayed in a DIFFERENT order than recorded -- still resolves
        # correctly because matching is per (agent_type, prompt hash), FIFO
        # within that key only.
        assert r_b("same prompt")[0] == "b1"
        assert r_a("same prompt")[0] == "a1"
        assert r_a("same prompt")[0] == "a2"


class TestTruncatedFinalLine:
    def test_truncated_final_line_is_tolerated(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        wrapped = manager.wrap("agent_a", _counting_invoke([("ok", LLMStats())]))
        wrapped("p1")
        manager.step_end(1)
        manager.close()

        # Simulate a crash mid-write: a non-JSON trailing partial line.
        with open(journal_path, "a", encoding="utf-8") as fh:
            fh.write('{"type": "call", "step": 2, "agent_type": "agent_a", "trunc')

        loaded = load_journal_for_resume(journal_path)
        assert loaded.last_complete_step == 1

    def test_mid_file_corruption_is_not_tolerated(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        wrapped = manager.wrap("agent_a", _counting_invoke([("ok", LLMStats())]))
        wrapped("p1")
        manager.step_end(1)
        manager.close()

        lines = journal_path.read_text(encoding="utf-8").splitlines()
        lines.insert(1, "NOT JSON AT ALL")
        journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        with pytest.raises(ValueError):
            load_journal_for_resume(journal_path)

    def test_format_version_mismatch_raises(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        with open(journal_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "header", "format_version": 999}) + "\n")
        with pytest.raises(ValueError):
            load_journal_for_resume(journal_path)


class TestPartialStepDropped:
    def test_records_after_last_step_end_are_dropped(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        stats = LLMStats()
        wrapped = manager.wrap("agent_a", _counting_invoke([("y1", stats), ("y2a", stats)]))
        wrapped("year1 prompt")
        manager.step_end(1)
        wrapped("year2 prompt")  # step 2 never reaches its own step_end
        manager.close()

        loaded = load_journal_for_resume(journal_path)
        assert loaded.last_complete_step == 1
        assert 2 not in loaded.pools


class TestDivergence:
    def test_missing_record_raises(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        wrapped = manager.wrap("agent_a", _counting_invoke([("y1", LLMStats())]))
        wrapped("year1 prompt")
        manager.step_end(1)
        manager.close()

        resumed = LLMJournalManager(
            header={}, output_path=tmp_path / "j2.jsonl", resume_from=journal_path,
        )
        rewrapped = resumed.wrap("agent_a", _forbidden_invoke)
        with pytest.raises(JournalReplayDivergence) as excinfo:
            rewrapped("a DIFFERENT prompt never recorded")
        assert excinfo.value.step == 1
        assert excinfo.value.agent_type == "agent_a"

    def test_leftover_records_at_step_boundary_raises(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        stats = LLMStats()
        wrapped = manager.wrap("agent_a", _counting_invoke([("y1a", stats), ("y1b", stats)]))
        wrapped("prompt A")
        wrapped("prompt B")
        manager.step_end(1)
        manager.close()

        resumed = LLMJournalManager(
            header={}, output_path=tmp_path / "j2.jsonl", resume_from=journal_path,
        )
        rewrapped = resumed.wrap("agent_a", _forbidden_invoke)
        rewrapped("prompt A")  # consumes only one of the two recorded calls
        with pytest.raises(JournalReplayDivergence):
            resumed.step_end(1)

    def test_never_falls_back_to_a_live_call(self, tmp_path):
        """A missing record raises; it must NOT silently call the live
        invoke instead (that would hide a non-reproducible rebuild)."""
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        wrapped = manager.wrap("agent_a", _counting_invoke([("y1", LLMStats())]))
        wrapped("recorded prompt")
        manager.step_end(1)
        manager.close()

        resumed = LLMJournalManager(
            header={}, output_path=tmp_path / "j2.jsonl", resume_from=journal_path,
        )
        live_calls = {"n": 0}

        def live_invoke(prompt):
            live_calls["n"] += 1
            return "LIVE", LLMStats()

        rewrapped = resumed.wrap("agent_a", live_invoke)
        with pytest.raises(JournalReplayDivergence):
            rewrapped("an unrecorded prompt")
        assert live_calls["n"] == 0


class TestConcurrentRecording:
    def test_several_threads_record_without_corruption(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)

        def invoke(prompt):
            time.sleep(0.001)
            return f"resp:{prompt}", LLMStats()

        wrapped = manager.wrap("agent_a", invoke)

        def worker(i):
            wrapped(f"prompt-{i}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        manager.step_end(1)
        manager.close()

        loaded = load_journal_for_resume(journal_path)
        total = sum(len(dq) for per_step in loaded.pools.values() for dq in per_step.values())
        assert total == 20
        # Every line must be valid JSON -- no interleaved/corrupted writes
        # from the concurrent fsync'd appends.
        for line in journal_path.read_text(encoding="utf-8").splitlines():
            json.loads(line)

    def test_concurrent_replay_each_call_served_exactly_once(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        stats = LLMStats()
        wrapped = manager.wrap(
            "agent_a", _counting_invoke([(f"resp-{i}", stats) for i in range(20)])
        )
        for i in range(20):
            wrapped("same prompt for all 20 calls")
        manager.step_end(1)
        manager.close()

        resumed = LLMJournalManager(
            header={}, output_path=tmp_path / "j2.jsonl", resume_from=journal_path,
        )
        rewrapped = resumed.wrap("agent_a", _forbidden_invoke)
        results = []
        lock = threading.Lock()

        def worker():
            content, _ = rewrapped("same prompt for all 20 calls")
            with lock:
                results.append(content)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # FIFO under concurrency is not guaranteed to preserve a specific
        # thread-to-answer mapping, but every one of the 20 recorded
        # answers must be served EXACTLY once -- no duplicate, no drop.
        assert sorted(results) == sorted(f"resp-{i}" for i in range(20))


class TestExceptionReplay:
    def test_builtin_exception_replayed_as_same_type(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        wrapped = manager.wrap("agent_a", _counting_invoke([RuntimeError("boom")]))
        with pytest.raises(RuntimeError, match="boom"):
            wrapped("p1")
        manager.step_end(1)
        manager.close()

        resumed = LLMJournalManager(
            header={}, output_path=tmp_path / "j2.jsonl", resume_from=journal_path,
        )
        rewrapped = resumed.wrap("agent_a", _forbidden_invoke)
        with pytest.raises(RuntimeError, match="boom"):
            rewrapped("p1")

    def test_unresolvable_exception_type_falls_back_to_journal_replayed_exception(self, tmp_path):
        """A journal from a build with a custom exception class this
        process does not have cannot reconstruct that exact class; replay
        raises JournalReplayedException instead, naming the original."""
        journal_path = tmp_path / "j.jsonl"
        with open(journal_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "header", "format_version": FORMAT_VERSION}) + "\n")
            fh.write(json.dumps({
                "type": "call", "step": 1, "agent_type": "agent_a",
                "prompt_sha256": hash_prompt_call("p1", (), {})[0], "extra_sha256": None,
                "raised": True, "shape": "tuple", "content": None, "stats": None,
                "exception_type": "TotallyMadeUpDomainException",
                "exception_message": "custom failure",
            }) + "\n")
            fh.write(json.dumps({"type": "step_end", "step": 1}) + "\n")

        resumed = LLMJournalManager(header={}, resume_from=journal_path)
        rewrapped = resumed.wrap("agent_a", _forbidden_invoke)
        with pytest.raises(JournalReplayedException, match="TotallyMadeUpDomainException"):
            rewrapped("p1")


class TestResumeWithoutOutputPath:
    def test_replay_works_with_no_new_journal(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        wrapped = manager.wrap("agent_a", _counting_invoke([("y1", LLMStats())]))
        wrapped("p1")
        manager.step_end(1)
        manager.close()

        resumed = LLMJournalManager(header={}, resume_from=journal_path)  # no output_path
        rewrapped = resumed.wrap("agent_a", _forbidden_invoke)
        assert rewrapped("p1")[0] == "y1"


class TestIdentifyingConfig:
    def test_identical_configs_pass(self):
        check_identifying_config({"a": 1, "b": 2}, {"a": 1, "b": 2})

    def test_differing_value_raises(self):
        with pytest.raises(ValueError, match="a"):
            check_identifying_config({"a": 1}, {"a": 2})

    def test_allowed_to_differ_key_is_ignored(self):
        check_identifying_config(
            {"workers": 1, "a": 1}, {"workers": 4, "a": 1}, allowed_to_differ=("workers",),
        )

    def test_key_absent_on_one_side_raises(self):
        with pytest.raises(ValueError):
            check_identifying_config({"a": 1}, {"a": 1, "b": 2})


class TestReadJournalHeader:
    def test_reads_header_without_parsing_the_rest(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(
            header={"model": "mock", "seed": 42}, output_path=journal_path,
        )
        manager.close()
        with open(journal_path, "a", encoding="utf-8") as fh:
            fh.write("GARBAGE NOT JSON, NEVER PARSED BY read_journal_header\n")

        header = read_journal_header(journal_path)
        assert header["model"] == "mock"
        assert header["seed"] == 42
        assert "format_version" not in header
        assert "type" not in header

    def test_format_version_mismatch_raises_before_any_data_load(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        with open(journal_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "header", "format_version": 999, "model": "mock"}) + "\n")
            fh.write("THIS WOULD BLOW UP load_journal_for_resume IF REACHED, NOT JSON\n")
        with pytest.raises(ValueError, match="format_version"):
            read_journal_header(journal_path)


class TestResumeProvenanceNesting:
    """Review fix: a resumed run's OWN header must not become impossible
    to resume again just because it carries resume provenance."""

    def test_resumed_header_nests_provenance_under_one_key(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={"model": "mock"}, output_path=journal_path)
        manager.step_end(1)
        manager.close()

        resumed_path = tmp_path / "j2.jsonl"
        resumed = LLMJournalManager(
            header={"model": "mock"}, output_path=resumed_path, resume_from=journal_path,
        )
        resumed.close()

        resumed_header = read_journal_header(resumed_path)
        assert RESUME_PROVENANCE_KEY in resumed_header
        assert resumed_header[RESUME_PROVENANCE_KEY]["resumed_from"] == str(journal_path)
        assert resumed_header["model"] == "mock"
        # A FRESH identifying-config dict (as a CLI preflight would build,
        # with no provenance key at all) still compares equal once that
        # one key is excluded.
        check_identifying_config(
            resumed_header, {"model": "mock"}, allowed_to_differ=(RESUME_PROVENANCE_KEY,),
        )  # must not raise

    def test_a_resumed_runs_header_can_itself_be_a_resume_source(self, tmp_path):
        """The core bug this fixes: resuming a run whose own header
        already carries resume_provenance must not be refused merely
        because a fresh identifying-config dict has no such key, and
        constructing a THIRD manager from the twice-resumed journal must
        not raise either."""
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={"model": "mock"}, output_path=journal_path)
        wrapped = manager.wrap("agent_a", _counting_invoke([("y1", LLMStats())]))
        wrapped("p1")
        manager.step_end(1)
        manager.close()

        resumed_path = tmp_path / "j2.jsonl"
        resumed = LLMJournalManager(
            header={"model": "mock"}, output_path=resumed_path, resume_from=journal_path,
        )
        resumed.close()

        resumed_header = read_journal_header(resumed_path)
        check_identifying_config(
            resumed_header, {"model": "mock"}, allowed_to_differ=(RESUME_PROVENANCE_KEY,),
        )  # must not raise
        third = LLMJournalManager(
            header={"model": "mock"}, output_path=tmp_path / "j3.jsonl", resume_from=resumed_path,
        )
        third.close()


class TestOutputPathCollision:
    """Review fix: opening the source journal for writing (output_path ==
    resume_from) would destroy it before -- or while -- it is read."""

    def test_output_path_equal_to_resume_from_raises(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        manager.step_end(1)
        manager.close()

        with pytest.raises(ValueError, match="both resolve to"):
            LLMJournalManager(header={}, output_path=journal_path, resume_from=journal_path)

    def test_equal_via_different_spelling_still_raises(self, tmp_path):
        """Resolved-path comparison, not a literal string one."""
        sub = tmp_path / "sub"
        sub.mkdir()
        journal_path = sub / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        manager.step_end(1)
        manager.close()

        equivalent_spelling = tmp_path / "sub" / ".." / "sub" / "j.jsonl"
        with pytest.raises(ValueError):
            LLMJournalManager(
                header={}, output_path=equivalent_spelling, resume_from=journal_path,
            )

    def test_source_journal_survives_a_refused_attempt(self, tmp_path):
        """The ValueError must fire BEFORE anything opens the path for
        writing -- the source journal's bytes must be untouched."""
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        wrapped = manager.wrap("agent_a", _counting_invoke([("y1", LLMStats())]))
        wrapped("p1")
        manager.step_end(1)
        manager.close()
        original_bytes = journal_path.read_bytes()

        with pytest.raises(ValueError):
            LLMJournalManager(header={}, output_path=journal_path, resume_from=journal_path)

        assert journal_path.read_bytes() == original_bytes


class TestStickyDivergence:
    """Review fix: a caller of the wrapped invoke with its own broad
    ``except Exception`` (a batch-reflection loop, an advisory pass) can
    swallow a JournalReplayDivergence; it must still stop the run at the
    next step_end."""

    def test_survives_a_swallowing_caller_even_with_no_leftovers(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        stats = LLMStats()
        wrapped = manager.wrap("agent_a", _counting_invoke([("r1", stats), ("r2", stats)]))
        wrapped("prompt A")
        wrapped("prompt B")
        manager.step_end(1)
        manager.close()

        resumed = LLMJournalManager(
            header={}, output_path=tmp_path / "j2.jsonl", resume_from=journal_path,
        )
        rewrapped = resumed.wrap("agent_a", _forbidden_invoke)
        assert rewrapped("prompt A")[0] == "r1"
        try:
            rewrapped("an unrecorded prompt C")  # no match -> raises; caller swallows it
        except JournalReplayDivergence:
            pass
        # Drains the LAST remaining recorded call too -- the pool for this
        # step is now fully empty, so the (separate, still-correct)
        # leftover-only check would see nothing wrong on its own.
        assert rewrapped("prompt B")[0] == "r2"
        with pytest.raises(JournalReplayDivergence):
            resumed.step_end(1)

    def test_only_the_first_divergence_is_remembered(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        wrapped = manager.wrap("agent_a", _counting_invoke([("y1", LLMStats())]))
        wrapped("p1")
        manager.step_end(1)
        manager.close()

        resumed = LLMJournalManager(
            header={}, output_path=tmp_path / "j2.jsonl", resume_from=journal_path,
        )
        rewrapped = resumed.wrap("agent_a", _forbidden_invoke)
        first_exc = None
        try:
            rewrapped("unrecorded A")
        except JournalReplayDivergence as exc:
            first_exc = exc
        try:
            rewrapped("unrecorded B")
        except JournalReplayDivergence:
            pass
        with pytest.raises(JournalReplayDivergence) as excinfo:
            resumed.step_end(1)
        assert excinfo.value is first_exc


class TestJournalWriteErrorSticky:
    """Review fix: a journal write failure (disk full) must not surface at
    the invoke call site, where a caller's own retry loop would mistake it
    for the MODEL call failing."""

    def test_write_failure_does_not_surface_at_the_call_site(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)

        def failing_record_call(**kwargs):
            raise OSError("simulated disk full")
        manager._writer.record_call = failing_record_call

        wrapped = manager.wrap("agent_a", _counting_invoke([("ok content", LLMStats())]))
        content, stats = wrapped("p1")
        assert content == "ok content"
        assert stats.success is True

        with pytest.raises(JournalWriteError, match="disk full"):
            manager.step_end(1)

    def test_sticky_across_further_successful_calls(self, tmp_path):
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)

        original_record_call = manager._writer.record_call
        state = {"n": 0}

        def flaky_record_call(**kwargs):
            state["n"] += 1
            if state["n"] == 1:
                raise OSError("simulated disk full")
            return original_record_call(**kwargs)
        manager._writer.record_call = flaky_record_call

        wrapped = manager.wrap(
            "agent_a", _counting_invoke([("first", LLMStats()), ("second", LLMStats())])
        )
        assert wrapped("p1")[0] == "first"
        assert wrapped("p2")[0] == "second"
        with pytest.raises(JournalWriteError):
            manager.step_end(1)


class TestFsyncBatching:
    """Review fix: mirroring replayed records into a resumed run's new
    journal must fsync once per step, not once per record."""

    def test_mirroring_fsyncs_once_per_step_not_per_record(self, tmp_path, monkeypatch):
        # Two steps, 10 records each: if mirroring fsync'd per record this
        # would be 20 (records) + 2 (step_end markers) = 22 fsyncs for the
        # mirrored data; batched per step it is 2 (one per step_end).
        journal_path = tmp_path / "j.jsonl"
        manager = LLMJournalManager(header={}, output_path=journal_path)
        stats = LLMStats()
        wrapped = manager.wrap(
            "agent_a", _counting_invoke([(f"r{i}", stats) for i in range(20)])
        )
        for i in range(10):
            wrapped(f"prompt step1 {i}")
        manager.step_end(1)
        for i in range(10):
            wrapped(f"prompt step2 {i}")
        manager.step_end(2)
        manager.close()

        import broker.utils.llm_journal as journal_mod
        fsync_calls = []
        real_fsync = os.fsync

        def counting_fsync(fd):
            fsync_calls.append(fd)
            return real_fsync(fd)

        monkeypatch.setattr(journal_mod.os, "fsync", counting_fsync)

        resumed = LLMJournalManager(
            header={}, output_path=tmp_path / "j2.jsonl", resume_from=journal_path,
        )
        resumed.close()
        # 1 fsync for the new journal's own header (unrelated to mirroring,
        # always fsync'd) + exactly 2 for mirroring (one per step_end, each
        # covering that step's 10 call records written with fsync=False) --
        # NOT 1 + 22.
        assert len(fsync_calls) == 3
