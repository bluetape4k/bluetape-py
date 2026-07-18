# ruff: noqa: RUF043
from __future__ import annotations

import pytest
from bluetape.leader.redis._scripts import (
    ACQUIRE_SCRIPT,
    PROBE_SCRIPT,
    RECONCILE_SCRIPT,
    RELEASE_SCRIPT,
    RENEW_SCRIPT,
    _parse_acquire_response,
    _parse_reconcile_response,
    _parse_status_response,
    _run_reconcile,
    _run_script,
    _run_script_async,
    _validated_script_args,
)
from redis.exceptions import NoScriptError


class FakeCommands:
    def __init__(
        self,
        *,
        evalsha_effects: list[object] | None = None,
        eval_effects: list[object] | None = None,
    ) -> None:
        self.evalsha_effects = list(evalsha_effects or [])
        self.eval_effects = list(eval_effects or [])
        self.calls: list[tuple[object, ...]] = []

    def evalsha(self, sha1: str, numkeys: int, *values: bytes) -> object:
        self.calls.append(("evalsha", sha1, numkeys, *values))
        return self._next(self.evalsha_effects)

    def eval(self, source: str, numkeys: int, *values: bytes) -> object:
        self.calls.append(("eval", source, numkeys, *values))
        return self._next(self.eval_effects)

    async def async_evalsha(self, sha1: str, numkeys: int, *values: bytes) -> object:
        return self.evalsha(sha1, numkeys, *values)

    async def async_eval(self, source: str, numkeys: int, *values: bytes) -> object:
        return self.eval(source, numkeys, *values)

    @staticmethod
    def _next(effects: list[object]) -> object:
        effect = effects.pop(0)
        if isinstance(effect, BaseException):
            raise effect
        return effect


class AsyncFakeCommands:
    def __init__(self, wrapped: FakeCommands) -> None:
        self.wrapped = wrapped

    async def evalsha(self, sha1: str, numkeys: int, *values: bytes) -> object:
        return self.wrapped.evalsha(sha1, numkeys, *values)

    async def eval(self, source: str, numkeys: int, *values: bytes) -> object:
        return self.wrapped.eval(source, numkeys, *values)


def test_noscript_falls_back_once_without_script_load() -> None:
    commands = FakeCommands(evalsha_effects=[NoScriptError()], eval_effects=[[b"ACQUIRED", b"7"]])

    result = _run_script(
        commands,
        ACQUIRE_SCRIPT,
        (b"lease", b"fence"),
        (b"A" * 32, b"1000"),
    )

    assert result == [b"ACQUIRED", b"7"]
    assert [call[0] for call in commands.calls] == ["evalsha", "eval"]
    assert commands.calls[0][1] == ACQUIRE_SCRIPT.sha1
    assert commands.calls[1][1] == ACQUIRE_SCRIPT.source
    assert all(call[0] != "script_load" for call in commands.calls)


@pytest.mark.asyncio
async def test_noscript_async_falls_back_once_without_script_load() -> None:
    wrapped = FakeCommands(evalsha_effects=[NoScriptError()], eval_effects=[[b"HELD"]])

    result = await _run_script_async(
        AsyncFakeCommands(wrapped), PROBE_SCRIPT, (b"lease",), (b"record",)
    )

    assert result == [b"HELD"]
    assert [call[0] for call in wrapped.calls] == ["evalsha", "eval"]


def test_noscript_non_noscript_error_never_redispatches() -> None:
    marker = TimeoutError("response lost")
    commands = FakeCommands(evalsha_effects=[marker])

    with pytest.raises(TimeoutError) as caught:
        _run_script(commands, PROBE_SCRIPT, (b"lease",), (b"record",))

    assert caught.value is marker
    assert [call[0] for call in commands.calls] == ["evalsha"]


def test_acquire_parses_string_safe_fence_above_lua_integer_precision() -> None:
    assert _parse_acquire_response([b"ACQUIRED", b"9007199254740993"]) == (
        "ACQUIRED",
        9_007_199_254_740_993,
    )
    assert _parse_acquire_response([b"CONTENDED"]) == ("CONTENDED", None)
    assert _parse_acquire_response([b"CORRUPT"]) == ("CORRUPT", None)


def test_acquire_accepts_redis_signed_maximum_fence() -> None:
    assert _parse_acquire_response([b"ACQUIRED", b"9223372036854775807"]) == (
        "ACQUIRED",
        9_223_372_036_854_775_807,
    )


@pytest.mark.parametrize(
    "value",
    [
        [b"ACQUIRED", b"0"],
        [b"ACQUIRED", b"01"],
        [b"ACQUIRED", b"9223372036854775808"],
        [b"ACQUIRED", 1],
        [b"OTHER"],
    ],
)
def test_acquire_rejects_malformed_response(value: object) -> None:
    with pytest.raises(ValueError, match="^invalid Redis script response$"):
        _parse_acquire_response(value)


def test_acquire_source_keeps_fence_as_canonical_string() -> None:
    source = ACQUIRE_SCRIPT.source
    assert "redis.call('INCR', KEYS[2])" in source
    assert "local fence = redis.call('GET', KEYS[2])" in source
    assert "tonumber" not in source
    assert "'PX', ARGV[2]" in source


def test_probe_accepts_only_atomic_contract_statuses() -> None:
    allowed = frozenset({"HELD", "NOT_HELD", "CORRUPT"})
    assert _parse_status_response([b"HELD"], allowed) == "HELD"
    assert _parse_status_response([b"NOT_HELD"], allowed) == "NOT_HELD"
    assert _parse_status_response([b"CORRUPT"], allowed) == "CORRUPT"
    assert "redis.call('PTTL', KEYS[1])" in PROBE_SCRIPT.source


def test_reconcile_uses_one_direct_read_only_eval() -> None:
    commands = FakeCommands(eval_effects=[[b"PRESENT", b"v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:9"]])

    raw = _run_reconcile(commands, b"lease")
    status, record = _parse_reconcile_response(raw)

    assert status == "PRESENT"
    assert record is not None and record.fencing_token == 9
    assert [call[0] for call in commands.calls] == ["eval"]
    assert commands.calls[0][1] == RECONCILE_SCRIPT.source
    assert "redis.call('PTTL', KEYS[1])" in RECONCILE_SCRIPT.source


@pytest.mark.parametrize("value", [[b"PRESENT", b"bad"], [b"PRESENT"], [b"OTHER"]])
def test_reconcile_rejects_malformed_response(value: object) -> None:
    with pytest.raises(ValueError, match="^invalid Redis script response$"):
        _parse_reconcile_response(value)


def test_renew_source_never_creates_or_redispatches() -> None:
    assert "redis.call('PEXPIRE', KEYS[1], ARGV[2])" in RENEW_SCRIPT.source
    assert "redis.call('SET'" not in RENEW_SCRIPT.source
    allowed = frozenset({"RENEWED", "NOT_HELD", "CORRUPT"})
    assert _parse_status_response([b"RENEWED"], allowed) == "RENEWED"


def test_release_source_is_exact_owner_conditional_and_never_unconditional_delete() -> None:
    source = RELEASE_SCRIPT.source
    assert "if current ~= ARGV[1] then return {'NOT_HELD'} end" in source
    assert "if ARGV[2] == '0' then" in source
    assert "redis.call('DEL', KEYS[1])" in source
    assert "redis.call('PEXPIRE', KEYS[1], ARGV[2])" in source
    allowed = frozenset({"DELETED", "MIN_TTL_APPLIED", "NOT_HELD", "CORRUPT"})
    assert _parse_status_response([b"MIN_TTL_APPLIED"], allowed) == "MIN_TTL_APPLIED"


def test_script_arguments_validate_before_dispatch() -> None:
    assert _validated_script_args("A" * 32, 1) == (b"A" * 32, b"1")
    with pytest.raises(ValueError, match="^Redis script argument is invalid$"):
        _validated_script_args("short", 1)
    with pytest.raises(ValueError, match="^Redis script argument is invalid$"):
        _validated_script_args("A" * 32, 0)
