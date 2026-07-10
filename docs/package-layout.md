# Package Layout Policy

## Goals

- Keep public packages small, Python-native, and independently useful.
- Avoid catch-all utility packages.
- Keep the default `bluetape` install thin.
- Prefer the Python standard library and focused optional dependencies before
  adding broad wrappers.
- Keep implementation details private until there is a clear public contract.

## Public Distributions

Distributions live under `packages/` and should map to focused import paths.

Current public distributions:

- `bluetape`
- `bluetape-collections`
- `bluetape-core`
- `bluetape-logging`
- `bluetape-testing`

The `bluetape` distribution is a meta package. It should not create a root
`bluetape/__init__.py` import surface. Focused packages own focused import paths
such as `bluetape.core`, `bluetape.logging`, and `bluetape.testing`.
The collections package owns `bluetape.collections`.

## Future Packages

Create a new distribution only when it has:

- a clear domain boundary;
- package README documentation;
- tests for success, failure, and boundary behavior;
- explicit dependency and extras impact;
- root README and WIP visibility when it affects user-facing scope.

Avoid adding optional integrations to the default `bluetape` dependency list.
Use extras or direct focused distribution installs for heavier capabilities.

## Internal Code

Use package-local private modules for implementation details that are not public
API. Good candidates:

- shared validation internals;
- serializer/compressor implementation details;
- fixture helpers not intended for users;
- compatibility shims while public APIs are still settling.

If users must import it, it belongs in a public package with docs and tests.

## Package Documentation

Every public package should have package documentation before it is considered
release-ready:

- package purpose;
- primary API examples;
- sync/async ownership rules when relevant;
- exception and error semantics;
- dependency and optional-extra notes;
- compatibility notes for sibling bluetape4k, bluetape-go, or bluetape-rs
  behavior when applicable.

## Examples

Prefer examples that solve real backend problems:

- validation at API boundaries;
- request/task log context;
- eventual consistency waits in tests;
- cache loading and invalidation;
- resilience policy wrapping;
- Testcontainers-backed integration fixtures;
- SQL transaction and outbox handoff patterns.
