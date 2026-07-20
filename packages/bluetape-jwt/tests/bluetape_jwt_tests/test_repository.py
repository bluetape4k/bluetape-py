from __future__ import annotations

import logging
import threading
import traceback
from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import bluetape.jwt._repository as repository_module
import pytest
from bluetape.jwt import (
    InMemoryKeyRepository,
    JWSAlgorithm,
    JWTConfigurationError,
    JWTKey,
    JWTKeyStateError,
    KeyEntry,
    KeySnapshot,
    KeyStatus,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def hmac_key(
    kid: str,
    algorithm: JWSAlgorithm = JWSAlgorithm.HS256,
) -> JWTKey:
    return JWTKey.from_hmac_secret(
        kid,
        algorithm,
        b"s" * (algorithm._minimum_key_bits // 8),
    )


@pytest.fixture(scope="module")
def rsa_pems() -> tuple[bytes, bytes]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def algorithm_key(
    kid: str,
    algorithm: JWSAlgorithm,
    rsa_pems: tuple[bytes, bytes],
    *,
    signing: bool,
) -> JWTKey:
    if algorithm.value.startswith("HS"):
        return hmac_key(kid, algorithm)
    if signing:
        return JWTKey.from_rsa_private(kid, algorithm, rsa_pems[0])
    return JWTKey.from_rsa_public(kid, algorithm, rsa_pems[1])


def test_entry_requires_exact_status_and_matching_material() -> None:
    key = hmac_key("active")

    assert KeyEntry(KeyStatus.ACTIVE, key).key is key
    assert KeyEntry(KeyStatus.RETIRED, key).key is key
    assert KeyEntry(KeyStatus.REVOKED, None).key is None

    for status, material in (
        (KeyStatus.ACTIVE, None),
        (KeyStatus.RETIRED, None),
        (KeyStatus.REVOKED, key),
        ("active", key),
        (KeyStatus.ACTIVE, object()),
    ):
        with pytest.raises(JWTKeyStateError) as caught:
            KeyEntry(status, material)  # type: ignore[arg-type]
        assert str(caught.value) == "JWT key state transition is invalid"


def test_snapshot_defensively_copies_and_enforces_invariants() -> None:
    active = hmac_key("active")
    retired = hmac_key("retired")
    source = {
        "active": KeyEntry(KeyStatus.ACTIVE, active),
        "retired": KeyEntry(KeyStatus.RETIRED, retired),
    }
    snapshot = KeySnapshot(source, 2)
    source.clear()

    assert list(snapshot.entries) == ["active", "retired"]
    assert snapshot.active == snapshot.entries["active"]
    with pytest.raises(TypeError):
        snapshot.entries["new"] = KeyEntry(KeyStatus.RETIRED, retired)  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        snapshot.epoch = 3  # type: ignore[misc]

    invalid_entries: list[tuple[dict[object, object], object]] = [
        ({"wrong": KeyEntry(KeyStatus.RETIRED, retired)}, 0),
        (
            {
                "one": KeyEntry(KeyStatus.ACTIVE, active),
                "two": KeyEntry(KeyStatus.ACTIVE, retired),
            },
            0,
        ),
        ({1: KeyEntry(KeyStatus.RETIRED, retired)}, 0),
        ({"retired": object()}, 0),
        ({}, -1),
        ({}, True),
        ({}, 1.0),
    ]
    for entries, epoch in invalid_entries:
        with pytest.raises(JWTConfigurationError):
            KeySnapshot(entries, epoch)  # type: ignore[arg-type]


def test_constructor_bootstrap_and_failure_are_atomic(
    rsa_pems: tuple[bytes, bytes],
    caplog: pytest.LogCaptureFixture,
) -> None:
    rsa_public_key = algorithm_key(
        "rsa-public",
        JWSAlgorithm.RS256,
        rsa_pems,
        signing=False,
    )
    empty = InMemoryKeyRepository()
    assert empty.snapshot() == KeySnapshot({}, 0)

    active = hmac_key("active")
    retired = hmac_key("retired")
    repository = InMemoryKeyRepository(active=active, verification_keys=[retired])
    snapshot = repository.snapshot()
    assert snapshot.epoch == 0
    assert snapshot.active == KeyEntry(KeyStatus.ACTIVE, active)
    assert snapshot.entries["retired"] == KeyEntry(KeyStatus.RETIRED, retired)

    public_repository = InMemoryKeyRepository(verification_keys=[rsa_public_key])
    assert public_repository.snapshot().entries["rsa-public"].status is KeyStatus.RETIRED

    def broken_iterable() -> Iterator[JWTKey]:
        yield retired
        raise RuntimeError("ITERABLE-CANARY")

    caplog.set_level(logging.DEBUG, logger=repository_module.__name__)
    invalid_factories = (
        lambda: InMemoryKeyRepository(active=rsa_public_key),
        lambda: InMemoryKeyRepository(active=active, verification_keys=[active]),
        lambda: InMemoryKeyRepository(active=active, verification_keys=[rsa_public_key]),
        lambda: InMemoryKeyRepository(verification_keys=[object()]),
        lambda: InMemoryKeyRepository(verification_keys=broken_iterable()),
    )
    for factory in invalid_factories:
        with pytest.raises((JWTConfigurationError, JWTKeyStateError)) as caught:
            factory()
        assert "CANARY" not in str(caught.value)
    assert caplog.records == []


def test_algorithm_binding_is_exact_and_failures_do_not_bind_or_publish() -> None:
    repository = InMemoryKeyRepository()
    initial = repository.snapshot()

    with pytest.raises(JWTConfigurationError):
        repository.add_verification_key(object())  # type: ignore[arg-type]
    # A capability failure must not bind the empty repository.
    assert repository.snapshot() is initial

    first = hmac_key("first", JWSAlgorithm.HS384)
    repository.rotate(first)
    bound = repository.snapshot()
    with pytest.raises(JWTConfigurationError):
        repository.add_verification_key(hmac_key("other", JWSAlgorithm.HS256))
    assert repository.snapshot() is bound

    repository.add_verification_key(hmac_key("same", JWSAlgorithm.HS384))
    assert repository.snapshot().epoch == 2


@pytest.mark.parametrize("algorithm", list(JWSAlgorithm))
def test_exact_algorithm_lifetime_matrix(
    algorithm: JWSAlgorithm,
    rsa_pems: tuple[bytes, bytes],
) -> None:
    repository = InMemoryKeyRepository()
    signing = algorithm_key("signing", algorithm, rsa_pems, signing=True)
    verification = algorithm_key("verification", algorithm, rsa_pems, signing=False)
    repository.rotate(signing)
    repository.add_verification_key(verification)

    snapshot = repository.snapshot()
    assert snapshot.entries["signing"].status is KeyStatus.ACTIVE
    assert snapshot.entries["verification"].status is KeyStatus.RETIRED

    incompatible_algorithm = next(
        candidate for candidate in JWSAlgorithm if candidate is not algorithm
    )
    incompatible = algorithm_key(
        "incompatible",
        incompatible_algorithm,
        rsa_pems,
        signing=False,
    )
    before = repository.snapshot()
    with pytest.raises(JWTConfigurationError):
        repository.add_verification_key(incompatible)
    assert repository.snapshot() is before


def test_failed_public_only_rotation_does_not_bind_empty_repository(
    rsa_pems: tuple[bytes, bytes],
) -> None:
    repository = InMemoryKeyRepository()
    initial = repository.snapshot()
    public = algorithm_key("public", JWSAlgorithm.RS256, rsa_pems, signing=False)

    with pytest.raises(JWTKeyStateError):
        repository.rotate(public)
    assert repository.snapshot() is initial

    repository.rotate(hmac_key("hmac", JWSAlgorithm.HS512))
    assert repository.snapshot().active is not None


def test_successful_lifecycle_transitions_publish_once_and_never_reuse() -> None:
    first = hmac_key("first")
    second = hmac_key("second")
    third = hmac_key("third")
    repository = InMemoryKeyRepository(active=first)
    initial = repository.snapshot()

    repository.add_verification_key(second)
    added = repository.snapshot()
    assert added is not initial and added.epoch == 1
    assert added.entries["second"].status is KeyStatus.RETIRED
    assert initial.entries == {"first": KeyEntry(KeyStatus.ACTIVE, first)}

    repository.rotate(third)
    rotated = repository.snapshot()
    assert rotated.epoch == 2
    assert rotated.entries["first"].status is KeyStatus.RETIRED
    assert rotated.entries["third"].status is KeyStatus.ACTIVE

    repository.retire("third")
    retired = repository.snapshot()
    assert retired.epoch == 3 and retired.active is None

    repository.revoke("second")
    revoked = repository.snapshot()
    assert revoked.epoch == 4
    assert revoked.entries["second"] == KeyEntry(KeyStatus.REVOKED, None)
    assert second.kid == "second" and not hasattr(second, "status")

    for mutation in (
        lambda: repository.add_verification_key(second),
        lambda: repository.rotate(second),
    ):
        before = repository.snapshot()
        with pytest.raises(JWTKeyStateError):
            mutation()
        assert repository.snapshot() is before

    active_repository = InMemoryKeyRepository(active=hmac_key("revoke-active"))
    active_repository.revoke("revoke-active")
    assert active_repository.snapshot().entries["revoke-active"] == KeyEntry(
        KeyStatus.REVOKED,
        None,
    )


def test_invalid_transitions_preserve_identity_and_emit_one_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = InMemoryKeyRepository(active=hmac_key("active"))
    repository.add_verification_key(hmac_key("retired"))
    repository.revoke("retired")
    caplog.set_level(logging.INFO, logger=repository_module.__name__)

    mutations = (
        lambda: repository.retire("missing"),
        lambda: repository.retire("retired"),
        lambda: repository.revoke("missing"),
        lambda: repository.revoke("retired"),
        lambda: repository.retire(" bad "),
        lambda: repository.add_verification_key(object()),
    )
    for mutation in mutations:
        caplog.clear()
        before = repository.snapshot()
        with pytest.raises((JWTConfigurationError, JWTKeyStateError)):
            mutation()
        assert repository.snapshot() is before
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.WARNING
        assert caplog.records[0].exc_info is None


def test_success_logging_is_one_value_free_info_per_mutation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    canaries = ("SECRET-KID-CANARY", "OTHER-KID-CANARY")
    repository = InMemoryKeyRepository(active=hmac_key(canaries[0]))
    caplog.set_level(logging.INFO, logger=repository_module.__name__)

    operations = (
        lambda: repository.add_verification_key(hmac_key(canaries[1])),
        lambda: repository.rotate(hmac_key("THIRD-KID-CANARY")),
        lambda: repository.retire("THIRD-KID-CANARY"),
        lambda: repository.revoke(canaries[1]),
    )
    expected = ("add_verification_key", "rotate", "retire", "revoke")
    for operation, name in zip(operations, expected, strict=True):
        caplog.clear()
        operation()
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == logging.INFO
        assert record.getMessage() == "jwt_repository_transition"
        assert record.event == "jwt_repository_transition"  # type: ignore[attr-defined]
        assert record.operation == name  # type: ignore[attr-defined]
        assert record.outcome == "success"  # type: ignore[attr-defined]
        rendered = f"{record.__dict__!r}\n{record.getMessage()}"
        assert not any(canary in rendered for canary in (*canaries, "THIRD-KID-CANARY"))


def test_failure_logs_and_exceptions_never_expose_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    canary = "REPOSITORY-SECRET-CANARY"
    repository = InMemoryKeyRepository(active=hmac_key("active"))
    caplog.set_level(logging.WARNING, logger=repository_module.__name__)

    try:
        repository.retire(canary)
    except JWTKeyStateError as error:
        rendered_exception = "".join(traceback.format_exception_only(error))
    else:
        pytest.fail("expected a redacted public error")

    assert canary not in rendered_exception
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.getMessage() == "jwt_repository_transition"
    assert record.event == "jwt_repository_transition"  # type: ignore[attr-defined]
    assert record.outcome == "failure"  # type: ignore[attr-defined]
    assert record.error_category == "key_state"  # type: ignore[attr-defined]
    assert record.exc_info is None
    assert canary not in repr(record.__dict__)


def test_readers_observe_only_complete_snapshots_at_publish_barrier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = InMemoryKeyRepository(active=hmac_key("old"))
    old = repository.snapshot()
    ready = threading.Event()
    release = threading.Event()
    original_freeze = repository_module._freeze_snapshot

    def blocked_freeze(entries: dict[str, KeyEntry], epoch: int) -> KeySnapshot:
        candidate = original_freeze(entries, epoch)
        ready.set()
        assert release.wait(timeout=5)
        return candidate

    monkeypatch.setattr(repository_module, "_freeze_snapshot", blocked_freeze)
    worker = threading.Thread(target=repository.rotate, args=(hmac_key("new"),))
    worker.start()
    assert ready.wait(timeout=5)

    observed: list[KeySnapshot] = []
    reader = threading.Thread(target=lambda: observed.append(repository.snapshot()))
    reader.start()
    assert reader.is_alive()
    release.set()
    worker.join(timeout=5)
    reader.join(timeout=5)
    assert not worker.is_alive()
    assert not reader.is_alive()

    new = repository.snapshot()
    assert new is not old
    assert observed == [new]
    assert new.epoch == 1
    assert new.entries["old"].status is KeyStatus.RETIRED
    assert new.entries["new"].status is KeyStatus.ACTIVE
    assert old.epoch == 0
    assert list(old.entries) == ["old"]
    assert old.entries["old"].status is KeyStatus.ACTIVE
