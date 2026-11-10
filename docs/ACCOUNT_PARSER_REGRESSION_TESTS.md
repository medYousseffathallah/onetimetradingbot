# BVMT Trading Intelligence — Account Parser Regression Test Suite
## DOM Extraction Hardening, Header Mapping & Mathematical Invariants

**Milestone**: 12  
**Date**: November 9, 2026  
**Schema Version**: `2026.11-v2`  
**Test Suite**: [`tests/test_manual_import.py`](file:///c:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit/tests/test_manual_import.py), [`extension/content.js`](file:///c:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit/extension/content.js)

---

## 1. Vulnerability Analysis & Root Causes

The early Chrome Companion extension failed on live Tunis Bourse Challenge pages due to three structural flaws:

| Flaw | Mechanism | Manifestation in Previous Implementation | Hardened Fix (`2026.11-v2`) |
|---|---|---|---|
| **Action Column Offset** | Column 0 contains an interactive `<input type="button" value="vendre">` | `sym = cells[0].toUpperCase()` extracted `"VENDRE"` as ticker for all rows. | Action headers/buttons (`"vendre"`, `"action"`) in Column 0 are explicitly excluded; ticker is read from Column 1 (`Nom de valeur`). |
| **"Montant" Column Inversion** | Table has 9 columns: `Vendre \| Nom \| Quantité \| Prix \| Montant \| Dernier \| Capital \| Gain DT \| Gain %` | Old 4-element assumption mapped `Montant` to `latest_price` and `Dernier` to `market_value`, collapsing holdings value to ~149 TND. | Dynamic mathematical identity check disambiguates `Montant` ($Q \times P$) from `Dernier` and `Capital`. |
| **Header Regex Inflexibility** | Top widget uses `"Votre portefeuille : 50061,96 DT"` and table footer uses `"Totaux 50061.96"` | Regex required `"Total portefeuille"` or `"Total du portefeuille"`, returning `equity = null`. | Flexible multi-pattern regex matches both `"Votre portefeuille"` and `"Totaux"` with French decimal commas. |

---

## 2. Mathematical Column Disambiguation Invariant

When reading a numeric row $N = [n_0, n_1, n_2, n_3, n_4, \dots]$ where $n_0 = \text{Quantité}$ and $n_1 = \text{Prix}$:

$$\text{Identity Check: } \Big| (n_0 \cdot n_1) - n_2 \Big| \le \max(0.05 \cdot n_2, 1.000)$$

* If **True**:
  * $n_2$ is confirmed to be **Acquisition Amount (`Montant`)**.
  * $n_3$ is **Latest Price (`Dernier`)**.
  * $n_4$ is **Market Value (`Capital`)**.
  * $n_5$ is **Gain in TND (`Gain (dt)`)**.
  * $n_6$ is **Gain in Percent (`Gain (%)`)**.
* If **False** (table without Montant column):
  * $n_2$ is **Latest Price (`Dernier`)**.
  * $n_3$ is **Market Value (`Capital`)**.

---

## 3. Regression Test Coverage

The test suite in [`tests/test_manual_import.py`](file:///c:/Users/Thinkcenter/Desktop/BVMT/bvmt-starter-kit/tests/test_manual_import.py) covers:

1. `test_parse_real_challenge_displayp_table`:
   * Feeds the exact raw HTML layout captured from the user's live browser.
   * Asserts exact extraction of all 4 securities (`BH BANK`, `DELICE HOLDING`, `NEW BODY LINE`, `STA`).
   * Validates exact quantities ($30, 263, 200, 22$).
   * Validates exact market values ($392.700, 5,020.670, 498.000, 2,527.800\text{ TND}$).
   * Validates exact per-position gains ($+0.750, -1.310, +5.550, -14.850\text{ TND}$).
   * Validates exact percentages ($+0.19\%, -0.03\%, +1.13\%, -0.58\%$).
   * Validates **zero reconciliation gap** ($\text{Cash} + \sum \text{Holdings} = \text{Equity}$).
2. `test_parse_manual_portfolio_paste_duplicate_and_invalid_suppression`:
   * Injects duplicate rows, zero-quantity rows ($Q = 0$), and negative-price rows.
   * Asserts strict rejection of malformed rows while preserving valid entries.
3. `test_parse_manual_portfolio_paste_plain_text`:
   * Tab-separated and space-separated clipboard pastes.
4. `test_parse_manual_portfolio_csv`:
   * Direct CSV uploads with metadata comments.

All 8 tests in `test_manual_import.py` pass in **0.25 seconds**.

