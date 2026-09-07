# Requirements – University DataShield

## Phase 1 (CURRENT) – Foundation ✅

| ID | Requirement | Status |
|----|-------------|--------|
| R-001 | React + TypeScript + Vite frontend scaffold | ✅ Done |
| R-002 | Tailwind CSS styling system | ✅ Done |
| R-003 | FastAPI backend with `/health` endpoint | ✅ Done |
| R-004 | SQLite database connection (async) | ✅ Done |
| R-005 | CORS configured for local development | ✅ Done |
| R-006 | Dashboard with KPI cards (demo values) | ✅ Done |
| R-007 | Live backend health indicator | ✅ Done |
| R-008 | Navigation shell (all pages, Dashboard functional) | ✅ Done |
| R-009 | Synthetic data only – no real PII | ✅ Done |
| R-010 | README, architecture docs, requirements docs | ✅ Done |

---

## Phase 2 – Dataset Scanner 🔜

| ID | Requirement | Status |
|----|-------------|--------|
| R-101 | CSV / JSON file upload API | Future |
| R-102 | Column extraction and metadata storage | Future |
| R-103 | Dataset list view in frontend | Future |
| R-104 | Synthetic dataset generator (FERPA-safe) | Future |
| R-105 | Dataset detail page showing column names & types | Future |

---

## Phase 3 – Sensitive Field Detection Engine 🔜

| ID | Requirement | Status |
|----|-------------|--------|
| R-201 | Regex-based PII detector (SSN, email, phone, DOB) | Future |
| R-202 | FERPA-specific field detector (student ID, GPA, grades) | Future |
| R-203 | ML heuristics for column name + value analysis | Future |
| R-204 | Field classification UI (sensitive / non-sensitive) | Future |
| R-205 | Confidence scoring per detected field | Future |
| R-206 | Manual override capability | Future |

---

## Phase 4 – Masking Policy Engine 🔜

| ID | Requirement | Status |
|----|-------------|--------|
| R-301 | Per-field masking rule CRUD (redact, hash, generalise, suppress) | Future |
| R-302 | Policy versioning | Future |
| R-303 | Policy Validator page | Future |
| R-304 | Preview of masked dataset | Future |
| R-305 | Policy export (JSON / YAML) | Future |

---

## Phase 5 – Role Validation & Publication Gate 🔜

| ID | Requirement | Status |
|----|-------------|--------|
| R-401 | RBAC role definitions (researcher, admin, public) | Future |
| R-402 | Access Roles management UI | Future |
| R-403 | Publication Gate workflow (submit → review → approve/reject) | Future |
| R-404 | Publication Blocks counter | Future |
| R-405 | Auto-block on unmasked sensitive fields | Future |

---

## Phase 6 – Audit Trail & Metrics 🔜

| ID | Requirement | Status |
|----|-------------|--------|
| R-501 | Immutable audit log (all decisions recorded) | Future |
| R-502 | Audit Trail UI with filtering & export | Future |
| R-503 | Live metrics dashboard (real counts, not demo) | Future |
| R-504 | Fields Scanned / Sensitive / Protected counters from DB | Future |
| R-505 | Policy Violations tracking | Future |

---

## Non-Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NF-001 | No real student data ever stored or transmitted | Critical |
| NF-002 | FERPA compliance as a design constraint | Critical |
| NF-003 | Modular architecture to enable phase-by-phase delivery | High |
| NF-004 | All API endpoints validated with Pydantic models | High |
| NF-005 | Frontend build must pass TypeScript strict checks | High |
| NF-006 | Async SQLite operations (non-blocking I/O) | Medium |
