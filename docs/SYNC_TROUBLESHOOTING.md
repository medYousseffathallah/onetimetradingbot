# BVMT Synchronization Troubleshooting Guide

Solutions for common portfolio synchronization issues.

---

## 1. Browser Companion Extension Issues

### Error: "Cannot connect to local backend (http://127.0.0.1:8000)"
- **Cause**: The FastAPI backend is not running or running on an unexpected port.
- **Fix**: Run `.\start_bvmt.bat` from PowerShell or CMD, or start FastAPI manually:
  ```powershell
  uv run uvicorn bvmt.api:app --host 127.0.0.1 --port 8000
  ```

### Error: "Unauthorized pairing token (HTTP 401)"
- **Cause**: The token entered in the extension popup does not match `data/portfolio/pairing_token.txt`.
- **Fix**:
  1. Open `http://127.0.0.1:3000/portfolio`.
  2. Click **Copy Pairing Token**.
  3. Open the extension popup, paste the token into the settings, and click **Save Token**.

### Error: "No portfolio values found on active tab"
- **Cause**: The active tab is not on `http://www.tunisbourse.com.tn/displayp.aspx`, or the user is not logged in.
- **Fix**: Log in to Tunis Bourse Challenge, click "Mon Portefeuille", wait for the positions table to load, and click the extension icon again.

---

## 2. Manual Paste / CSV Issues

### Error: "Balance mismatch: Cash + Holdings != Equity"
- **Cause**: The copied text is missing the cash or total equity line, or prices changed during copying.
- **Fix**: Use the **Cash Override** and **Equity Override** inputs in the Manual Import tab to specify the exact figures displayed on your competition screen.

### Error: "CSV parsing failed: invalid number string"
- **Cause**: Numbers use non-standard formatting.
- **Fix**: The parser supports both French commas (`19,095`) and dots (`19.095`), as well as thousand spaces (`19 095,000`). Ensure headers are present (`SYMBOL;QUANTITY;ACQUISITION_PRICE;LATEST_PRICE;MARKET_VALUE`).

---

## 3. Playwright Background Collector Issues

### Error: "Browser session timed out after 180 seconds"
- **Cause**: Manual login in the opened Chromium window was not completed before the timeout.
- **Fix**: Use the **Browser Companion Extension** instead, which eliminates Playwright startup latency entirely.
