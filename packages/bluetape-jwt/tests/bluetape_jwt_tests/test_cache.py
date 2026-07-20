"""Bounded verified-result cache tests."""

from __future__ import annotations

import hashlib
import logging
import threading
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import bluetape.jwt as jwt
import bluetape.jwt._provider as provider_module
import pytest
from bluetape.cache import TTLCache
from bluetape.jwt._cache import _VerifiedTokenCache

NOW = datetime(2025, 1, 1, tzinfo=UTC)


class MutableWallClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return self.now


class MonotonicClock:
    def __init__(self) -> None:
        self.now_ns = 0

    def __call__(self) -> int:
        return self.now_ns


def make_claims(**overrides: object) -> jwt.TokenClaims:
    values = {
        "issuer": "issuer",
        "audience": ("api",),
        "issued_at": NOW,
        "custom": {"scope": "read"},
    }
    values.update(overrides)
    return jwt.TokenClaims(**values)


def make_profile(clock: Callable[[], datetime], **overrides: object) -> jwt.ValidationProfile:
    values = {
        "token_type": "access+jwt",
        "allowed_issuers": frozenset({"issuer"}),
        "accepted_audiences": frozenset({"api"}),
        "required_claims": frozenset({"scope"}),
        "clock": clock,
    }
    values.update(overrides)
    return jwt.ValidationProfile(**values)


def make_provider(
    clock: Callable[[], datetime],
    *,
    cache: jwt.VerifiedTokenCacheOptions | None,
    profile_overrides: dict[str, object] | None = None,
) -> tuple[jwt.JWSProvider, jwt.InMemoryKeyRepository]:
    key = jwt.JWTKey.from_hmac_secret(
        "current-key",
        jwt.JWSAlgorithm.HS256,
        b"s" * 32,
    )
    repository = jwt.InMemoryKeyRepository(active=key)
    provider = jwt.JWSProvider(
        jwt.JWSAlgorithm.HS256,
        repository,
        make_profile(clock, **(profile_overrides or {})),
        cache=cache,
    )
    return provider, repository


def make_verified(**overrides: object) -> jwt.VerifiedToken:
    values = {
        "kid": "current-key",
        "algorithm": jwt.JWSAlgorithm.HS256,
        "token_type": "access+jwt",
        "issuer": "issuer",
        "subject": None,
        "audience": ("api",),
        "expires_at": None,
        "not_before": None,
        "issued_at": NOW,
        "jwt_id": None,
        "custom": {"scope": "read"},
        "headers": {},
    }
    values.update(overrides)
    return jwt.VerifiedToken(**values)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"default_ttl": timedelta(0), "max_size": 1},
        {"default_ttl": timedelta(seconds=-1), "max_size": 1},
        {"default_ttl": 1, "max_size": 1},
        {"default_ttl": timedelta(seconds=1), "max_size": 0},
        {"default_ttl": timedelta(seconds=1), "max_size": True},
    ],
)
def test_cache_options_require_positive_finite_ttl_and_capacity(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(jwt.JWTConfigurationError):
        jwt.VerifiedTokenCacheOptions(**kwargs)


def test_cache_options_are_frozen() -> None:
    options = jwt.VerifiedTokenCacheOptions(timedelta(seconds=10), 2)

    with pytest.raises(FrozenInstanceError):
        options.max_size = 3


def test_cache_key_is_digest_policy_and_epoch_without_raw_token() -> None:
    backend = RecordingCache()
    adapter = _VerifiedTokenCache(
        jwt.VerifiedTokenCacheOptions(timedelta(seconds=10), 2),
        cache_factory=lambda **kwargs: backend,
    )
    profile = make_profile(lambda: NOW)
    snapshot = jwt.InMemoryKeyRepository().snapshot()
    token = "raw.canary.token"

    assert adapter.get(token, profile, snapshot) is None
    adapter.set(
        token,
        profile,
        snapshot,
        make_verified(),
        now=NOW,
        live_epoch=snapshot.epoch,
    )

    expected = (hashlib.sha256(token.encode("utf-8")).digest(), profile.fingerprint, 0)
    assert backend.get_calls == [expected]
    assert backend.set_calls[0][0] == expected
    assert token not in repr(adapter)
    assert all(token not in repr(item) for item in backend.get_calls + backend.set_calls)


def test_adapter_uses_lru_and_configured_ttl() -> None:
    clock = MonotonicClock()
    created: list[TTLCache[tuple[bytes, str, int], jwt.VerifiedToken]] = []

    def factory(**kwargs: object) -> TTLCache[tuple[bytes, str, int], jwt.VerifiedToken]:
        cache = TTLCache(**kwargs, clock=clock)
        created.append(cache)
        return cache

    adapter = _VerifiedTokenCache(
        jwt.VerifiedTokenCacheOptions(timedelta(seconds=10), 2),
        cache_factory=factory,
    )
    profile = make_profile(lambda: NOW)
    snapshot = jwt.InMemoryKeyRepository().snapshot()
    value = make_verified()
    for token in ("a.a.a", "b.b.b"):
        adapter.set(token, profile, snapshot, value, now=NOW, live_epoch=0)
    assert adapter.get("a.a.a", profile, snapshot) is value
    adapter.set("c.c.c", profile, snapshot, value, now=NOW, live_epoch=0)

    assert adapter.get("b.b.b", profile, snapshot) is None
    assert adapter.get("a.a.a", profile, snapshot) is value
    clock.now_ns = 10_000_000_000
    assert adapter.get("a.a.a", profile, snapshot) is None
    assert len(created) == 1


def test_effective_ttl_is_limited_by_expiration_remaining() -> None:
    clock = MonotonicClock()

    def factory(**kwargs: object) -> TTLCache[tuple[bytes, str, int], jwt.VerifiedToken]:
        return TTLCache(**kwargs, clock=clock)

    adapter = _VerifiedTokenCache(
        jwt.VerifiedTokenCacheOptions(timedelta(seconds=10), 2),
        cache_factory=factory,
    )
    profile = make_profile(lambda: NOW)
    snapshot = jwt.InMemoryKeyRepository().snapshot()
    value = make_verified(expires_at=NOW + timedelta(seconds=3))

    adapter.set("a.a.a", profile, snapshot, value, now=NOW, live_epoch=0)
    clock.now_ns = 2_999_999_999
    assert adapter.get("a.a.a", profile, snapshot) is value
    clock.now_ns = 3_000_000_000
    assert adapter.get("a.a.a", profile, snapshot) is None


def test_disabled_cache_revalidates_signature_every_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, _ = make_provider(lambda: NOW, cache=None)
    token = provider.issue(make_claims(expires_at=NOW + timedelta(hours=1)))
    original_decode = provider_module.jwt.decode
    calls = 0

    def counting_decode(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original_decode(*args, **kwargs)

    monkeypatch.setattr(provider_module.jwt, "decode", counting_decode)
    provider.verify(token)
    provider.verify(token)

    assert calls == 2


def test_cache_hit_skips_signature_but_rechecks_expiration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = MutableWallClock()
    provider, _ = make_provider(
        clock,
        cache=jwt.VerifiedTokenCacheOptions(timedelta(minutes=5), 2),
    )
    token = provider.issue(make_claims(expires_at=NOW + timedelta(seconds=1)))
    original_decode = provider_module.jwt.decode
    calls = 0

    def counting_decode(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original_decode(*args, **kwargs)

    monkeypatch.setattr(provider_module.jwt, "decode", counting_decode)
    assert provider.verify(token).issuer == "issuer"
    clock.now = NOW + timedelta(seconds=2)

    with pytest.raises(jwt.JWTExpiredError):
        provider.verify(token)

    assert calls == 1
    assert clock.calls == 2


@pytest.mark.parametrize(
    ("claims", "profile_overrides", "next_now", "error"),
    [
        (
            make_claims(not_before=NOW),
            {},
            NOW - timedelta(seconds=1),
            jwt.JWTNotYetValidError,
        ),
        (
            make_claims(issued_at=NOW),
            {},
            NOW - timedelta(seconds=1),
            jwt.JWTNotYetValidError,
        ),
        (
            make_claims(issued_at=NOW),
            {"max_token_age": timedelta(seconds=1)},
            NOW + timedelta(seconds=2),
            jwt.JWTExpiredError,
        ),
    ],
)
def test_cache_hit_rechecks_all_temporal_policy(
    claims: jwt.TokenClaims,
    profile_overrides: dict[str, object],
    next_now: datetime,
    error: type[jwt.JWTError],
) -> None:
    clock = MutableWallClock()
    provider, _ = make_provider(
        clock,
        cache=jwt.VerifiedTokenCacheOptions(timedelta(minutes=5), 2),
        profile_overrides=profile_overrides,
    )
    token = provider.issue(claims)
    provider.verify(token)
    clock.now = next_now

    with pytest.raises(error):
        provider.verify(token)


@pytest.mark.parametrize("operation", ["rotate", "retire", "revoke"])
def test_epoch_change_clears_cache_and_rechecks_key_state(
    operation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, repository = make_provider(
        lambda: NOW,
        cache=jwt.VerifiedTokenCacheOptions(timedelta(minutes=5), 2),
    )
    token = provider.issue(make_claims())
    original_decode = provider_module.jwt.decode
    calls = 0

    def counting_decode(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original_decode(*args, **kwargs)

    monkeypatch.setattr(provider_module.jwt, "decode", counting_decode)
    provider.verify(token)
    provider.verify(token)
    assert calls == 1

    if operation == "rotate":
        repository.rotate(
            jwt.JWTKey.from_hmac_secret(
                "new-key",
                jwt.JWSAlgorithm.HS256,
                b"n" * 32,
            )
        )
    elif operation == "retire":
        repository.retire("current-key")
    else:
        repository.revoke("current-key")

    if operation == "revoke":
        with pytest.raises(jwt.JWTKeyUnavailableError):
            provider.verify(token)
        assert calls == 1
    else:
        assert provider.verify(token).kid == "current-key"
        assert provider.verify(token).kid == "current-key"
        assert calls == 2


def test_invalid_signature_is_never_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, _ = make_provider(
        lambda: NOW,
        cache=jwt.VerifiedTokenCacheOptions(timedelta(minutes=5), 2),
    )
    token = provider.issue(make_claims())
    header, payload, signature = token.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    invalid = f"{header}.{payload}.{replacement}{signature[1:]}"
    original_decode = provider_module.jwt.decode
    calls = 0

    def counting_decode(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original_decode(*args, **kwargs)

    monkeypatch.setattr(provider_module.jwt, "decode", counting_decode)
    for _ in range(2):
        with pytest.raises(jwt.JWTSignatureError):
            provider.verify(invalid)

    assert calls == 2


def test_claim_failure_is_never_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, _ = make_provider(
        lambda: NOW,
        cache=jwt.VerifiedTokenCacheOptions(timedelta(minutes=5), 2),
    )
    token = provider.issue(make_claims(issuer="other"))
    original_decode = provider_module.jwt.decode
    calls = 0

    def counting_decode(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original_decode(*args, **kwargs)

    monkeypatch.setattr(provider_module.jwt, "decode", counting_decode)
    for _ in range(2):
        with pytest.raises(jwt.JWTClaimError):
            provider.verify(token)

    assert calls == 2


class RecordingCache:
    def __init__(self, *, failure: str | None = None) -> None:
        self.failure = failure
        self.values: dict[object, object] = {}
        self.get_calls: list[object] = []
        self.set_calls: list[tuple[object, object, float | None]] = []
        self.clear_calls = 0

    def get(self, key: object) -> object:
        self.get_calls.append(key)
        if self.failure == "get":
            raise RuntimeError("canary-secret")
        if key not in self.values:
            raise KeyError(key)
        return self.values[key]

    def set(self, key: object, value: object, *, ttl: float | None = None) -> None:
        self.set_calls.append((key, value, ttl))
        if self.failure == "set":
            raise RuntimeError("canary-secret")
        self.values[key] = value

    def clear(self) -> None:
        self.clear_calls += 1
        if self.failure == "clear":
            raise RuntimeError("canary-secret")
        self.values.clear()


@pytest.mark.parametrize("operation", ["get", "set", "clear"])
def test_cache_terminal_failure_is_logged_once_and_redacted(
    operation: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    backend = RecordingCache(failure=operation)
    adapter = _VerifiedTokenCache(
        jwt.VerifiedTokenCacheOptions(timedelta(seconds=10), 2),
        cache_factory=lambda **kwargs: backend,
    )
    profile = make_profile(lambda: NOW)
    repository = jwt.InMemoryKeyRepository()
    snapshot = repository.snapshot()
    if operation == "clear":
        assert adapter.get("warm.cache.entry", profile, snapshot) is None
    caplog.set_level(logging.ERROR, logger="bluetape.jwt._cache")

    with pytest.raises(jwt.JWTCacheError) as captured:
        if operation == "get":
            adapter.get("raw.canary.token", profile, snapshot)
        elif operation == "set":
            adapter.set(
                "raw.canary.token",
                profile,
                snapshot,
                make_verified(),
                now=NOW,
                live_epoch=snapshot.epoch,
            )
        else:
            repository.rotate(
                jwt.JWTKey.from_hmac_secret(
                    "new-key",
                    jwt.JWSAlgorithm.HS256,
                    b"n" * 32,
                )
            )
            adapter.get("raw.canary.token", profile, repository.snapshot())

    assert "canary-secret" not in str(captured.value)
    assert captured.value.__cause__ is None
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.message == "jwt_cache_operation"
    assert (record.event, record.operation, record.outcome, record.error_category) == (
        "jwt_cache_operation",
        operation,
        "failure",
        "cache",
    )
    assert "raw.canary.token" not in repr(record.__dict__)
    assert "canary-secret" not in repr(record.__dict__)


def test_revoke_race_never_publishes_current_epoch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, repository = make_provider(
        lambda: NOW,
        cache=jwt.VerifiedTokenCacheOptions(timedelta(minutes=5), 2),
    )
    backend = RecordingCache()
    provider._cache = _VerifiedTokenCache(
        jwt.VerifiedTokenCacheOptions(timedelta(minutes=5), 2),
        cache_factory=lambda **kwargs: backend,
    )
    token = provider.issue(make_claims())
    original_decode = provider_module.jwt.decode
    entered = threading.Event()
    release = threading.Event()
    results: list[jwt.VerifiedToken] = []
    errors: list[BaseException] = []

    def blocking_decode(*args: object, **kwargs: object) -> object:
        entered.set()
        assert release.wait(2)
        return original_decode(*args, **kwargs)

    def verify() -> None:
        try:
            results.append(provider.verify(token))
        except BaseException as error:
            errors.append(error)

    monkeypatch.setattr(provider_module.jwt, "decode", blocking_decode)
    thread = threading.Thread(target=verify)
    thread.start()
    assert entered.wait(2)
    repository.revoke("current-key")
    release.set()
    thread.join(2)

    assert not thread.is_alive()
    assert errors == []
    assert len(results) == 1
    assert backend.set_calls == []
    with pytest.raises(jwt.JWTKeyUnavailableError):
        provider.verify(token)
