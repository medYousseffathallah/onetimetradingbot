# BVMT Browser Companion — Chrome Extension Guide

The **BVMT Browser Companion** is a lightweight, zero-credential Chrome extension (Manifest V3) that enables instant, 1-click synchronization of your Tunis Bourse Challenge portfolio directly from `displayp.aspx` into the local BVMT Trading Intelligence platform.

---

## 1. Architecture & Design Principles

- **Zero Passwords & Cookies**: The extension never inspects, captures, or transmits passwords, session cookies, or login credentials.
- **Strictly Read-Only DOM Extraction**: It only reads visible account numbers (Liquidités, Total portefeuille, Rang) and the active positions table (`#tab_portefeuille`).
- **No Cloud Communication**: Data is transmitted strictly to your local FastAPI backend running on `http://127.0.0.1:8000`.
- **Local Pairing Token**: Transmissions are signed with a 48-character pairing token (`X-BVMT-Pairing-Token`) generated locally in `data/portfolio/pairing_token.txt`.
- **Pre-Reconciliation Balance Check**: Before any snapshot is accepted, the platform verifies that `available_cash + sum(holdings.market_value) == total_equity` within a 0.050 TND tolerance.

---

## 2. Installation (1 Minute)

1. Open Google Chrome (or any Chromium browser: Brave, Edge).
2. Navigate to: `chrome://extensions/`
3. In the top-right corner, toggle **Developer mode** to ON.
4. Click **Load unpacked** in the top-left corner.
5. In the file picker, select the `extension/` folder inside your repository:
   ```
   C:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit\extension
   ```
6. The extension **BVMT Intelligence Companion** will appear in your extension toolbar. Pin it for easy access.

---

## 3. Configuration & Pairing

1. Start the BVMT platform (`.\start_bvmt.bat` or `uv run bvmt dashboard`).
2. Open your dashboard at `http://127.0.0.1:3000/portfolio`.
3. Under the **Account Synchronization Hub** -> **Browser Companion** tab, copy your **Local Pairing Token**.
4. Click the BVMT extension icon in your Chrome toolbar.
5. Paste your pairing token into the **Local Pairing Token** field and click **Save Token**.
6. The extension indicator will turn green: **Connected to Localhost:8000**.

---

## 4. Daily Synchronization Workflow

1. In Chrome, log in to the Tunis Bourse Challenge portal and navigate to your portfolio page:
   `http://www.tunisbourse.com.tn/displayp.aspx`
2. Once the table showing your holdings and liquidity is visible, click the BVMT Companion extension icon.
3. The popup displays extracted numbers:
   - Available Cash (DT)
   - Total Portfolio Equity (DT)
   - Holdings Count & Symbols
   - Competition Rank
4. Click **Sync to Local Platform**.
5. Switch to your BVMT dashboard at `http://127.0.0.1:3000/portfolio`.
6. A yellow banner will appear: **Snapshot captured — awaiting confirmation**.
7. Review the side-by-side reconciliation diff, check the confirmation box, and click **Confirm Snapshot & Reconcile Ledger**.
