# CR-087: Identity Doctor / Rotation Status

Added read-only identity health checks for active and historical agent identity material. The doctor reports ERROR/WARNING/OK findings for missing active keys, malformed key material, fingerprint mismatches, multiple active identities, missing archived material, and rotation metadata gaps. The rotation-status alias routes to the same doctor handler. Tests verify healthy state, corrupted key material, missing/multiple active keys, missing archived key warnings, alias behavior, and byte-for-byte read-only guarantees. Full suite: 631 passed.
