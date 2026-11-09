# BVMT Account Synchronization Security Model

This document outlines the security architecture and privacy guarantees of the Tunis Bourse Challenge synchronization system.

---

## 1. Zero Credential Exposure Guarantee

Traditional scraping solutions require users to store cleartext or encrypted passwords and cookies. This architecture eliminates that vulnerability:

- **No Stored Credentials**: The system stores zero passwords, session tokens, or authentication cookies.
- **User-Supervised Authentication**: The user logs in to Tunis Bourse Challenge directly in their normal browser.
- **Read-Only Scrape Boundary**: The extension extracts only numerical and table text from `#tab_portefeuille` and metadata paragraphs on `displayp.aspx`.

---

## 2. Localhost Authentication & Pairing Tokens

To prevent unauthorized external web pages from sending forged portfolio states to the local FastAPI daemon, the platform implements a local pairing token mechanism:

1. **Token Generation**: Upon initial boot, `CanonicalSyncService` generates a cryptographically secure 48-character hex token (`secrets.token_hex(24)`).
2. **Local Persistence**: Stored exclusively at `data/portfolio/pairing_token.txt` (excluded from git via `.gitignore`).
3. **Transmission Requirement**: Every extension POST request to `/api/sync/extension` must supply the header:
   ```http
   X-BVMT-Pairing-Token: <48-char-hex>
   ```
4. **Digest Comparison**: The backend validates the token using `secrets.compare_digest` to prevent timing attacks. Requests without a valid token receive `HTTP 401 Unauthorized`.

---

## 3. Strict Balance Validation (Anti-Fabrication Gate)

Before staging any snapshot, the `CanonicalSyncService` validates the fundamental accounting equation:

$$\text{Available Cash} + \sum_{i} \left(\text{Quantity}_i \times \text{Latest Price}_i\right) = \text{Total Account Equity}$$

- **Tolerance**: Maximum allowable deviation is `0.050 TND` (to account for millime rounding across positions).
- **Enforcement**: If the equation fails, the snapshot is rejected with `ValidationStatus.BALANCE_MISMATCH` and `HTTP 422 Unprocessable Content`. No snapshot file is created, and the active ledger is untouched.

---

## 4. Confirmation-Gated Reconciliation Boundary

A snapshot capture NEVER mutates the active trading ledger directly.

1. **Ingestion**: Produces an immutable, content-hashed snapshot JSON in `data/portfolio/snapshots/sync_*.json`.
2. **Preview**: The platform computes a dry-run diff against the last confirmed state (`cash_before`, `cash_after`, `equity_before`, `equity_after`, position share deltas).
3. **Explicit Confirmation**: The user must review the diff in the UI and submit `POST /api/sync/confirm` with `confirmed_by_user=true`.
