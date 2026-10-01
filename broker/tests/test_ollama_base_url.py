"""Unit tests for broker.utils.llm_utils.get_ollama_base_url / is_mock_model.

Review round 2 (W1): the helper must default the port to 11434 when
OLLAMA_HOST gives none, map the two "every interface" wildcard addresses
(0.0.0.0, ::) to loopback the way Ollama's own OLLAMA_HOST parsing does, and
keep a full URL (one that already carries a scheme) exactly as given. The
unset/blank case must stay byte-identical to the pre-review string, since
that is what every existing caller already depends on.

Review round 3 (W1 follow-up): the wildcard-to-loopback mapping ALSO applies
inside a full, scheme-prefixed URL (a bare "keep it as given" was too broad
-- ``http://0.0.0.0:11434`` is not a safe literal connect target on every
platform either), and a leading/trailing matching quote pair is stripped
from OLLAMA_HOST before parsing (a common copy-paste artifact from a shell
assignment).

None of these tests touch the network: get_ollama_base_url is a pure string
function of the OLLAMA_HOST environment variable.
"""
from __future__ import annotations

import pytest

from broker.utils import llm_utils


@pytest.fixture(autouse=True)
def _clear_ollama_host(monkeypatch):
    """Every test starts with OLLAMA_HOST unset, regardless of the shell
    this suite happens to run under."""
    monkeypatch.delenv("OLLAMA_HOST", raising=False)


class TestUnsetStaysExactlyTheOldString:
    def test_unset_matches_pre_review_default_exactly(self):
        assert llm_utils.get_ollama_base_url() == "http://localhost:11434"

    def test_blank_matches_pre_review_default_exactly(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_HOST", "   ")
        assert llm_utils.get_ollama_base_url() == "http://localhost:11434"

    def test_default_generate_url_is_pinned(self):
        """The URL _invoke_ollama_direct actually posts to, with OLLAMA_HOST
        unset, must stay the exact pre-review string."""
        assert f"{llm_utils.get_ollama_base_url()}/api/generate" == "http://localhost:11434/api/generate"


class TestFullUrlKeptAsIs:
    @pytest.mark.parametrize("value,expected", [
        ("http://127.0.0.1:9", "http://127.0.0.1:9"),
        ("https://example.com:1234/", "https://example.com:1234"),
    ])
    def test_scheme_prefixed_value_is_unchanged_except_trailing_slash(self, monkeypatch, value, expected):
        monkeypatch.setenv("OLLAMA_HOST", value)
        assert llm_utils.get_ollama_base_url() == expected

    @pytest.mark.parametrize("value,expected", [
        # Round 3: a wildcard host is rewritten EVEN inside a full URL, since
        # a bare "keep it as given" was too broad -- see the module docstring.
        ("http://0.0.0.0:11434", "http://127.0.0.1:11434"),
        ("http://0.0.0.0:5555", "http://127.0.0.1:5555"),
        ("https://[::]:11434/", "https://[::1]:11434"),
        ("https://[::]:5555", "https://[::1]:5555"),
    ])
    def test_wildcard_host_is_rewritten_even_inside_a_full_url(self, monkeypatch, value, expected):
        monkeypatch.setenv("OLLAMA_HOST", value)
        assert llm_utils.get_ollama_base_url() == expected

    @pytest.mark.parametrize("value,expected", [
        # Round 4, should-fix 6: rewriting the wildcard host must not drop
        # a user:pw@ (or bare user@) prefix.
        ("http://user:pw@0.0.0.0:11434", "http://user:pw@127.0.0.1:11434"),
        ("http://user@0.0.0.0:11434", "http://user@127.0.0.1:11434"),
        ("http://user:pw@[::]:11434/", "http://user:pw@[::1]:11434"),
    ])
    def test_wildcard_rewrite_keeps_userinfo(self, monkeypatch, value, expected):
        monkeypatch.setenv("OLLAMA_HOST", value)
        assert llm_utils.get_ollama_base_url() == expected


class TestQuoteStripping:
    @pytest.mark.parametrize("value,expected", [
        ('"127.0.0.1:11500"', "http://127.0.0.1:11500"),
        ("'127.0.0.1:11500'", "http://127.0.0.1:11500"),
        ('"http://host:1234"', "http://host:1234"),
        ("'http://host:1234/'", "http://host:1234"),
    ])
    def test_surrounding_quotes_are_stripped(self, monkeypatch, value, expected):
        monkeypatch.setenv("OLLAMA_HOST", value)
        assert llm_utils.get_ollama_base_url() == expected

    def test_mismatched_quotes_are_not_stripped(self, monkeypatch):
        """Only a MATCHING leading/trailing pair counts as quoting; a lone
        or mismatched quote character is part of the (unsupported) value."""
        monkeypatch.setenv("OLLAMA_HOST", '"127.0.0.1:11500')
        # Not stripped: falls through to bare-host parsing with the quote
        # character still attached to the host portion.
        assert llm_utils.get_ollama_base_url() == 'http://"127.0.0.1:11500'


class TestDefaultPortInjection:
    @pytest.mark.parametrize("value,expected", [
        ("127.0.0.1", "http://127.0.0.1:11434"),
        ("example.com", "http://example.com:11434"),
        ("127.0.0.1:9999", "http://127.0.0.1:9999"),  # explicit port untouched
    ])
    def test_missing_port_defaults_to_11434(self, monkeypatch, value, expected):
        monkeypatch.setenv("OLLAMA_HOST", value)
        assert llm_utils.get_ollama_base_url() == expected


class TestAnyInterfaceMapsToLoopback:
    @pytest.mark.parametrize("value,expected", [
        ("0.0.0.0", "http://127.0.0.1:11434"),
        ("0.0.0.0:11434", "http://127.0.0.1:11434"),
        ("0.0.0.0:5555", "http://127.0.0.1:5555"),
        ("::", "http://[::1]:11434"),
        ("[::]:11434", "http://[::1]:11434"),
        ("[::]:5555", "http://[::1]:5555"),
    ])
    def test_wildcard_address_maps_to_loopback(self, monkeypatch, value, expected):
        monkeypatch.setenv("OLLAMA_HOST", value)
        assert llm_utils.get_ollama_base_url() == expected

    def test_actual_loopback_ipv6_is_left_as_loopback(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_HOST", "[::1]:11434")
        assert llm_utils.get_ollama_base_url() == "http://[::1]:11434"


class TestIsMockModel:
    @pytest.mark.parametrize("model,expected", [
        ("mock", True),
        ("MOCK", True),
        ("mock-v2", True),
        ("gemma3:4b", False),
        ("openai:gpt-4", False),
        ("scripted-test", False),
        (None, False),
        (123, False),
    ])
    def test_is_mock_model(self, model, expected):
        assert llm_utils.is_mock_model(model) is expected
