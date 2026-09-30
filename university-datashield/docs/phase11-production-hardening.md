# Phase 11: Production Security, Scalability & Deployment

## 1. Overview
Phase 11 strengthens **University DataShield** with enterprise-grade security hardening, multi-format ingestion, asynchronous worker queues, destination connector abstractions, and containerization configuration while keeping the authoritative security publication gate and fail-closed privacy architecture authoritative.

---

## 2. Architecture & Subsystems

```
                                 [ Identity Provider ]
                                           │
                                  (OAuth2 / OIDC JWT)
                                           ▼
                                 [ FastAPI Ingestion Gate ]
                       ┌───────────────────┴───────────────────┐
                       ▼                                       ▼
             [ Security Headers ]                    [ Rate Limiter (429) ]
             [ Payload Limiter (413) ]               [ JWT Validator (401) ]
                       │                                       │
                       └───────────────────┬───────────────────┘
                                           ▼
                                 [ Adapter Registry ]
                 ┌──────────┬──────────┬──────────┬──────────┬──────────┐
                 ▼          ▼          ▼          ▼          ▼          ▼
                CSV        JSON     PARQUET     ARROW       ORC        AVRO
                 └──────────┴──────────┴──────────┴──────────┴──────────┘
                                           │
                                           ▼
                               [ Asynchronous Worker Queue ]
                               (In-Process / Celery-ready)
                                           │
                                           ▼
                           [ AUTHORITATIVE SECURITY PIPELINE ]
                                   Phase 9 Detection
                                           │
                                   Phase 4 Policy Engine
                                           │
                                   Phase 5 RBAC Engine
                                           │
                                 [ Publication Gate ]
                                    /             \
                             ALLOW /               \ BLOCK
                                  ▼                 ▼
                       [ Destination Connectors ] [ Execution Blocked ]
                       • Mock Warehouse           • Fail-Closed Verdict
                       • Snowflake Adapter        • Security Audit Event
                       • BigQuery Adapter         • Zero Raw PII Stored
                       • Databricks Adapter
```

---

## 3. Core Capabilities Implemented

### 3.1 Enterprise Authentication Architecture
- **JWT Cryptographic Verification**: Signature, expiration, issuer (`AUTH_ISSUER`), audience (`AUTH_AUDIENCE`), and role claims validation.
- **Fail-Closed Rejection**: Rejects expired tokens (`TOKEN_EXPIRED`), invalid signatures (`INVALID_SIGNATURE`), unauthorized issuers (`INVALID_ISSUER`), and malformed tokens (`MALFORMED_TOKEN`).
- **Dual-Mode Compatibility**:
  - `development`: Supports `X-Demo-Role` headers for offline evaluation journeys and local demonstrations.
  - `production`: Mandatory Bearer token validation with strict error masking.

### 3.2 API Security & Rate Limiting
- **OWASP Recommended Headers**: Strict HSTS (`max-age=31536000`), CSP (`frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`.
- **Request Tracing**: `X-Request-ID` correlation identifiers generated or preserved on every HTTP request and logged in structured telemetry.
- **Payload Size Limits**: Strict byte rejection (HTTP 413) for oversized payloads exceeding `MAX_UPLOAD_SIZE_MB`.
- **Sliding-Window Rate Limiting**: Per-client rate limit tracker returning HTTP 429 with standard `Retry-After` headers.

### 3.3 Multi-Format Analytical Adapters
- **DatasetReader Abstraction**: Clean modular hierarchy supporting `CSVReader`, `JSONReader`, `ParquetReader`, `ArrowReader`, `ORCReader`, and `AvroReader`.
- **Nesting Depth Protection**: Hardened JSON parser preventing recursive resource exhaustion attacks.
- **Data Minimization**: Analyzes metadata and structural types while discarding raw personal records.

### 3.4 Asynchronous Worker Queue & Job State Machine
- **Non-blocking Worker**: In-process asynchronous queue loop with concurrency control (`WORKER_CONCURRENCY`).
- **Discrete Job States**: `CREATED`, `QUEUED`, `RUNNING`, `SCANNING`, `DETECTED`, `VALIDATING_POLICY`, `VALIDATING_ACCESS`, `READY`, `BLOCKED`, `PUBLISHED`, `FAILED`, `CANCELLED`.
- **Safe Recovery**: Enforces the non-negotiable security invariant that `BLOCKED` jobs cannot bypass validation on retry.

### 3.5 Database Abstraction & Indexes
- **Repository Abstraction**: `DatabaseAdapter` interface supporting SQLite and PostgreSQL migration readiness.
- **Performance Indexes**: High-performance indexes on `pipeline_runs(pipeline_id)`, `pipeline_runs(status)`, `pipeline_runs(created_at)`, and `audit_events(timestamp)`.
- **Anti-SQL Injection**: Parameterized query enforcement across all database operations.

### 3.6 Downstream Destination Connectors
- **Fail-Closed Rule**: Destination publishing is strictly prohibited unless DataShield's publication gate returns `ALLOW`.
- **Connectors**:
  - `MockWarehouseDestination`: In-memory isolated storage for testing.
  - `SnowflakeDestination`: Production configuration-driven warehouse interface.
  - `BigQueryDestination`: Google Cloud dataset interface.
  - `DatabricksDestination`: Delta Lake catalog connector interface.

### 3.7 Health & Readiness Probes
- `/health`: Liveness probe indicating service operational status.
- `/ready`: Orchestration readiness probe reporting database, worker, audit, and auth mode readiness without exposing paths, passwords, or connection strings.

---

## 4. Container Deployment Configuration

- **`Dockerfile`**: Multi-stage minimal Debian/Python runtime with an unprivileged system user (`datashield:datashield`), non-root execution, and internal healthcheck.
- **`docker-compose.yml`**: Full local stack specification with `backend`, `worker`, `frontend`, and persistent volumes.
- **`.env.example`**: Secure template for all environment variables without committed secrets.
