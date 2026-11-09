// Content script for BVMT Intelligence Companion
// Strictly read-only extraction of visible account values from displayp.aspx and display_histo.aspx
// Never extracts passwords, cookies, or personal credentials. Never clicks trading buttons.

(() => {
  const SCHEMA_VERSION = "2026.11-v2";

  function parseFrenchNumber(str) {
    if (!str) return null;
    const clean = str
      .replace(/\xa0/g, "")
      .replace(/\s/g, "")
      .replace(/DT/gi, "")
      .replace(/dt/gi, "")
      .replace(/%/g, "")
      .replace(/,/g, ".");
    const num = parseFloat(clean);
    return isNaN(num) ? null : num;
  }

  function extractPortfolio() {
    const pageText = document.body.innerText || "";
    const url = window.location.href;

    // Check if on login or password page
    if (pageText.includes("Mot de passe") && !pageText.includes("Liquidités")) {
      return {
        success: false,
        error: "AUTH_REQUIRED",
        message: "Please log in to your Tunis Bourse Challenge account.",
        source_schema_version: SCHEMA_VERSION,
      };
    }

    // 1. Extract Cash (Liquidités)
    let cash = null;
    const cashMatch = pageText.match(/Liquidit[ée]s?\s*:?\s*([0-9\s,\.]+)/i);
    if (cashMatch) {
      cash = parseFrenchNumber(cashMatch[1]);
    }

    // 2. Extract Total Equity (Votre portefeuille / Total portefeuille / Totaux)
    let equity = null;
    const eqMatch =
      pageText.match(/(?:Votre\s+portefeuille|Total\s*(?:du)?\s*portefeuille)\s*:?\s*([0-9\s,\.]+)/i) ||
      pageText.match(/Totaux\s+([0-9\s,\.]+)/i);
    if (eqMatch) {
      equity = parseFrenchNumber(eqMatch[1]);
    }

    // 3. Extract Ranking (Votre classement / Rang / Classement)
    let rank = null;
    let participants = null;
    const rankMatch = pageText.match(/(?:Votre\s+classement|Rang|Classement)\s*:?\s*#?([0-9\s]+)(?:\s*\/\s*([0-9\s]+))?/i);
    if (rankMatch) {
      rank = parseInt(rankMatch[1].replace(/\s/g, ""), 10);
      if (rankMatch[2]) {
        participants = parseInt(rankMatch[2].replace(/\s/g, ""), 10);
      }
    }

    // 4. Extract Holdings from Table
    const holdings = [];
    const validationErrors = [];
    const seenSymbols = new Set();
    const tables = document.querySelectorAll("table");
    let targetTable = document.querySelector("#tab_portefeuille") || document.querySelector(".table_portefeuille");

    if (!targetTable) {
      for (const t of tables) {
        const text = t.innerText.toLowerCase();
        if ((text.includes("valeur") || text.includes("symbole")) && text.includes("quantit")) {
          targetTable = t;
          break;
        }
      }
    }

    if (targetTable) {
      const rows = Array.from(targetTable.querySelectorAll("tr"));
      let colMap = null;

      // Identify header columns if present
      for (const row of rows) {
        const headers = Array.from(row.querySelectorAll("th, td")).map(c => c.innerText.trim().toLowerCase());
        const hasNom = headers.some(h => h.includes("nom") || h.includes("valeur") || h.includes("symbole"));
        const hasQty = headers.some(h => h.includes("quantit"));
        if (hasNom && hasQty) {
          colMap = {
            sym: headers.findIndex(h => h.includes("nom") || h.includes("valeur") || h.includes("symbole")),
            qty: headers.findIndex(h => h.includes("quantit")),
            acqPx: headers.findIndex(h => h.includes("prix") || h.includes("achat") || h.includes("pmp")),
            montant: headers.findIndex(h => h.includes("montant")),
            latPx: headers.findIndex(h => h.includes("dernier") || h.includes("cours")),
            mktVal: headers.findIndex(h => h.includes("capital") || h.includes("valeur")),
            gainDt: headers.findIndex(h => h.includes("gain") && h.includes("dt")),
            gainPct: headers.findIndex(h => h.includes("gain") && h.includes("%")),
          };
          break;
        }
      }

      for (const row of rows) {
        const cells = Array.from(row.querySelectorAll("td, th")).map(c => c.innerText.trim());
        if (cells.length < 2) continue;

        const first = cells[0].toLowerCase();
        // Skip header or summary footer rows
        if (
          first.includes("valeur") ||
          first.includes("symbole") ||
          first.includes("titre") ||
          first.includes("totaux") ||
          first.includes("total") ||
          first.includes("liquidit")
        ) {
          continue;
        }

        let sym = "";
        let qty = 0;
        let acqPx = 0;
        let latPx = 0;
        let mktVal = 0;
        let acqAmt = null;
        let gainTnd = null;
        let gainPct = null;

        if (colMap && colMap.sym !== -1 && colMap.qty !== -1 && cells.length > Math.max(colMap.sym, colMap.qty)) {
          // Exact header-mapped row
          sym = cells[colMap.sym].toUpperCase();
          qty = Math.round(parseFrenchNumber(cells[colMap.qty]) || 0);
          acqPx = parseFrenchNumber(cells[colMap.acqPx]) || 0;
          acqAmt = colMap.montant !== -1 ? parseFrenchNumber(cells[colMap.montant]) : null;
          latPx = colMap.latPx !== -1 ? (parseFrenchNumber(cells[colMap.latPx]) || acqPx) : acqPx;
          mktVal = colMap.mktVal !== -1 ? (parseFrenchNumber(cells[colMap.mktVal]) || (qty * latPx)) : (qty * latPx);
          gainTnd = colMap.gainDt !== -1 ? parseFrenchNumber(cells[colMap.gainDt]) : null;
          gainPct = colMap.gainPct !== -1 ? parseFrenchNumber(cells[colMap.gainPct]) : null;
        } else {
          // Resilient positional fallback:
          // In challenge table, Column 0 is "Vendre" button and Column 1 is "Nom de valeur"
          let numCells = [];
          if (first === "vendre" || first === "" || first.includes("action")) {
            if (cells.length >= 3) {
              sym = cells[1].toUpperCase();
              numCells = cells.slice(2);
            }
          } else {
            sym = cells[0].toUpperCase();
            numCells = cells.slice(1);
          }

          const nums = [];
          for (const c of numCells) {
            const val = parseFrenchNumber(c);
            if (val !== null) nums.push(val);
          }

          if (nums.length >= 2) {
            qty = Math.round(nums[0]);
            acqPx = nums[1];
            latPx = acqPx;
            mktVal = qty * latPx;

            // Identity: montant ~= qty * acqPx
            if (nums.length >= 4 && Math.abs(qty * acqPx - nums[2]) < Math.max(0.05 * nums[2], 1.0)) {
              acqAmt = nums[2];
              latPx = nums[3];
              mktVal = nums.length >= 5 ? nums[4] : qty * latPx;
              gainTnd = nums.length >= 6 ? nums[5] : null;
              gainPct = nums.length >= 7 ? nums[6] : null;
            } else if (nums.length >= 3) {
              latPx = nums[2];
              mktVal = nums.length >= 4 ? nums[3] : qty * latPx;
              gainTnd = nums.length >= 5 ? nums[4] : null;
              gainPct = nums.length >= 6 ? nums[5] : null;
            }
          }
        }

        // Clean and validate symbol
        sym = sym.replace(/[\r\n\t]+/g, " ").trim();
        if (!sym || sym === "VENDRE" || sym.length > 50 || sym.includes("LIQUIDIT") || sym.includes("TOTAUX")) {
          continue;
        }

        if (seenSymbols.has(sym)) {
          validationErrors.push(`Duplicate holding row for symbol: ${sym}`);
          continue;
        }
        seenSymbols.add(sym);

        // Row-level sanity checks
        if (qty <= 0) {
          validationErrors.push(`Invalid quantity ${qty} for ${sym}`);
          continue;
        }
        if (acqPx <= 0) {
          validationErrors.push(`Invalid acquisition price ${acqPx} for ${sym}`);
          continue;
        }

        holdings.push({
          symbol: sym,
          instrument_id: sym.replace(/[^A-Z0-9._-]+/g, "_"),
          quantity: qty,
          acquisition_price_tnd: acqPx.toFixed(3),
          acquisition_amount_tnd: acqAmt !== null ? acqAmt.toFixed(3) : (qty * acqPx).toFixed(3),
          latest_price_tnd: latPx.toFixed(3),
          market_value_tnd: mktVal.toFixed(3),
          gain_tnd: gainTnd !== null ? gainTnd.toFixed(3) : (mktVal - (acqAmt || (qty * acqPx))).toFixed(3),
          gain_pct: gainPct !== null ? gainPct.toFixed(2) : "0.00",
          displayed_name: sym,
        });
      }
    }

    // Auto-calculate equity or cash if only one was parsed
    const holdingsSum = holdings.reduce((sum, h) => sum + parseFloat(h.market_value_tnd), 0);
    if (equity === null && cash !== null) {
      equity = cash + holdingsSum;
    } else if (cash === null && equity !== null) {
      cash = Math.max(0, equity - holdingsSum);
    }

    if (equity === null && cash === null && holdings.length === 0) {
      return {
        success: false,
        error: "UNKNOWN_LAYOUT",
        message: "Could not identify Tunis Bourse Challenge portfolio table or account balances.",
        source_schema_version: SCHEMA_VERSION,
        validation_errors: ["No recognizable portfolio data found in active DOM"],
      };
    }

    const reconciliationGap = Math.abs((cash || 0) + holdingsSum - (equity || 0));
    const isReconciled = reconciliationGap < 0.100;

    return {
      success: true,
      url: url,
      extracted_at: new Date().toISOString(),
      source_schema_version: SCHEMA_VERSION,
      account_equity: equity !== null ? equity.toFixed(3) : "50000.000",
      available_cash: cash !== null ? cash.toFixed(3) : "50000.000",
      holdings: holdings,
      competition_ranking: rank,
      total_participants: participants,
      source_page_type: "displayp.aspx",
      is_reconciled: isReconciled,
      reconciliation_gap_tnd: reconciliationGap.toFixed(3),
      validation_errors: validationErrors,
    };
  }

  // Execute and return directly
  return extractPortfolio();
})();
