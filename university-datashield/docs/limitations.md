# University DataShield — System Boundaries & Honest Limitations

In the spirit of honest engineering and transparent disclosure, the following architectural boundaries and limitations are documented. University DataShield does **not** claim to be "100% unbreakable" or a full enterprise security suite; rather, it demonstrates that **100% of tested unsafe publication scenarios were blocked** under defined operational conditions.

---

## 1. Identity & Session Management

- **Prototype Role Simulation**: In the demonstration prototype, the actor's role is provided via HTTP request payloads or simulated headers (`X-Actor-Role`). This allows evaluators to seamlessly test RBAC transitions between `SECURITY_ADMIN`, `DATA_ENGINEER`, `ANALYST`, and `FACULTY`.
- **Production Requirement**: A production deployment must integrate with an enterprise Identity Provider (IdP) supporting SAML 2.0, OAuth2/OIDC, or Kerberos, with cryptographically signed JSON Web Tokens (JWT) verified server-side.

---

## 2. Persistence & Multi-Node Scalability

- **Single-Node SQLite**: Persistence uses local asynchronous SQLite with WAL mode (`data/datashield.db`). While fast and self-contained for prototyping and single-server deployments, it is not distributed.
- **Production Requirement**: High-availability production deployments across multiple institutional datacenters require a clustered relational database (e.g. PostgreSQL with streaming replication) and distributed consensus for policy synchronization.

---

## 3. Host-Level & Database Administrator Compromise

- **Host Operating System Takeover**: An attacker with root/administrator access to the underlying server host can inspect process memory or modify SQLite database files directly.
- **Hash-Chain Recomputation**: If an adversary possesses direct write access to the SQLite file and recomputes every SHA-256 hash from the genesis block forward, internal chain verification cannot detect tampering without an external, append-only timestamping authority or immutable transparency ledger.

---

## 4. Privacy Scope & Anonymization Boundaries

- **Masking vs. Formal Differential Privacy**: DataShield applies transformation-based protections (`MASK`, `HASH`, `GENERALIZE`, `SUPPRESS`). While this satisfies typical FERPA and university data release guidelines, transformation-based masking does not mathematically protect against high-dimensional linkage attacks or differential reconstruction.
- **High-Dimensional Quasi-Identifier Linkage**: When multiple generalized demographic attributes (e.g., zip code, gender, birth year) are released together, sophisticated external data linkage attacks remain theoretically possible.

---

## 5. Policy Lifecycle & Branching

- **Linear Policy Versioning**: Policy versioning follows a linear progression (`v1.0` → `v1.1` → `v1.2-rollback`). Complex multi-department branching and merge workflows (similar to Git branches) are not supported.
- **Fail-Closed Default**: Any sensitive classification that lacks an explicit policy configuration is treated as an unmapped rule and fails closed (`BLOCK`). While secure, this requires institutional administrators to maintain clear policy coverage for newly added custom attributes.

---

## 6. Dataset Evaluation Scope

- **Synthetic Data Benchmark**: All evaluations, error analyses, and demonstrations are conducted strictly on synthetic test datasets. While designed to mirror real university records (GPA, student IDs, placement packages, attendance), real-world academic schemas may contain idiosyncratic abbreviations or domain-specific jargon requiring rule customization.
