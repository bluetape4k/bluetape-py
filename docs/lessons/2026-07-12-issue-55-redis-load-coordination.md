# Issue #55 Redis Load Coordination Lessons

## Context and decision

The feature coordinates cold loads across independent processes without
turning Redis into an L2 cache. A local cache remains authoritative for local
hits and in-process flight ownership; Redis contributes a short lease, one
bounded atomic snapshot, and an owner-checked atomic publication.

The public contract keeps serialization caller-owned through
`ResultEnvelopeCodec`, uses digest-only Redis keys, rejects unbounded provider
policies, and provides matching sync/async surfaces. Lease loss returns the
caller-loaded value locally but never claims distributed publication success.

## What the implementation proved

- Check the wall deadline immediately before each backend command, not only at
  loop boundaries. Token generation and poll sleep are work that can cross it.
- Bounding poll count is insufficient if backoff math itself can overflow;
  cap the exponent by the configured interval ratio.
- Socket timeouts do not bound blocking connection-pool admission. Reject a
  pool whose acquisition wait is outside the command policy.
- Async parity is a failure-contract obligation, not just a happy-path API
  obligation. Loader, codec, provider, artifact, cleanup, cancellation, and
  invalid-input paths need direct evidence.
- Primary failure or cancellation must survive cleanup failure. A static note
  and low-cardinality `cleanup_failed` signal are safer than replacing or
  leaking backend details.
- ACL success proof should use exactly the commands the coordinator requires;
  teardown must attempt provider close, user deletion, and admin close even
  when an earlier cleanup step fails.

## Surprises and future guards

An atomic snapshot necessarily reads a bounded result prefix even while the
marker is active. This is acceptable under the approved bounded contract but
should be revisited before production capacity claims.

`CLEANUP_FAILURE` has no natural standalone state because every safe cleanup
follows an existing primary. Keep it reserved or remove/deprecate it before API
stabilization; do not invent a misleading cleanup-only failure path.

Keep the closeout ladder: focused unit and README tests, serial real Redis,
repeated contention/cancellation, full pytest, Ruff, all-package build,
actionlint, diff check, six-perspective P0/P1 convergence, then PR CI. Merge is
allowed only after every required check succeeds.
