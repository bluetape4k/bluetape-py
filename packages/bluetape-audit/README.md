# bluetape-audit

Storage-neutral audit event contracts for Python-native bluetape applications.

Install the focused distribution with:

```bash
pip install bluetape-audit
```

Alternatively, install the audit extra from the thin meta distribution:

```bash
pip install "bluetape[audit]"
```

Import the currently available error boundary from `bluetape.audit`. The
package has no runtime dependencies and does not provide storage, transport,
logging, background workers, or a root `bluetape` convenience module.
