import logging

import pytest
from bluetape.logging import ContextLogFilter, get_log_context, log_context, redact


def test_log_context_is_scoped_and_restored() -> None:
    assert get_log_context() == {}

    with log_context(request_id="req-1", user_id="u-1"):
        assert get_log_context() == {"request_id": "req-1", "user_id": "u-1"}

    assert get_log_context() == {}


def test_nested_log_context_overrides_and_restores_values() -> None:
    with log_context(request_id="outer", tenant="blue"):
        with log_context(request_id="inner"):
            assert get_log_context() == {"request_id": "inner", "tenant": "blue"}

        assert get_log_context() == {"request_id": "outer", "tenant": "blue"}


def test_log_context_rejects_duplicate_keys_without_override() -> None:
    with log_context(request_id="outer"):
        with pytest.raises(KeyError, match="request_id already exists in log context"):
            with log_context(request_id="inner", override=False):
                pass

        assert get_log_context() == {"request_id": "outer"}


def test_context_log_filter_adds_context_to_record() -> None:
    record = logging.LogRecord("test", logging.INFO, __file__, 10, "hello", (), None)

    with log_context(request_id="req-1"):
        assert ContextLogFilter().filter(record)

    assert record.request_id == "req-1"


def test_redact_masks_sensitive_mapping_values() -> None:
    assert redact({"token": "secret", "name": "visible"}, keys={"token"}) == {
        "token": "***",
        "name": "visible",
    }


def test_redact_matches_keys_case_insensitively_by_default() -> None:
    assert redact({"Authorization": "secret", "name": "visible"}, keys={"authorization"}) == {
        "Authorization": "***",
        "name": "visible",
    }
