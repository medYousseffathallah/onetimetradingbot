// Content script for BVMT Intelligence Companion
// Strictly read-only extraction of visible account values from displayp.aspx and display_histo.aspx
// Never extracts passwords, cookies, or personal credentials. Never clicks trading buttons.

(() => {
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
      return { error: "AUTH_REQUIRED", message: "Please log in to your Tunis Bourse Challenge account." };
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
    const tables = document.querySelectorAll("table");
    let targetTable = document.querySelector("#tab_portefeuille") || document.querySelector(".table_portefeuille");

    if (!targetTable) {
      // Find table with Valeur / Quantité / Total headers
      for (const t of tables) {
        const text = t.innerText.toLowerCase();
        if ((text.includes("valeur") || text.includes("symbole")) && text.includes("quantit")) {
          targetTable = t;
          break;
        }
      }
    }

    if (targetTable) {
      const rows = targetTable.querySelectorAll("tr");
      for (const row of rows) {
        const cells = Array.from(row.querySelectorAll("td, th")).map(c => c.innerText.trim());
        if (cells.length < 2) continue;

        const first = cells[0].toLowerCase();
        // Skip header or footer rows
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

        // Determine symbol column:
        // On challenge table, Column 0 is "Vendre" button and Column 1 is "Nom de valeur"
        let sym = "";
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

        if (!sym || sym === "VENDRE" || sym.length > 50 || sym.includes("LIQUIDIT") || sym.includes("TOTAUX")) {
          continue;
        }

        // Extract numbers from subsequent cells
        const nums = [];
        for (const c of numCells) {
          const val = parseFrenchNumber(c);
          if (val !== null) nums.push(val);
        }

        if (nums.length >= 2) {
          const qty = Math.round(nums[0]);
          const acqPx = nums[1];
          let latPx = acqPx;
          let mktVal = qty * latPx;

          // Check if table contains Montant column:
          // [qty, acqPx, montant, dernier, capital, gain, gain%]
          // Identity: montant ~= qty * acqPx
          if (nums.length >= 4 && Math.abs(qty * acqPx - nums[2]) < 1.0) {
            latPx = nums[3];
            mktVal = nums.length >= 5 ? nums[4] : qty * latPx;
          } else if (nums.length >= 3) {
            latPx = nums[2];
            mktVal = nums.length >= 4 ? nums[3] : qty * latPx;
          }

          holdings.push({
            symbol: sym,
            instrument_id: sym.replace(/[^A-Z0-9._-]+/g, "_"),
            quantity: qty,
            acquisition_price_tnd: acqPx.toFixed(3),
            latest_price_tnd: latPx.toFixed(3),
            market_value_tnd: mktVal.toFixed(3),
            displayed_name: sym
          });
        }
      }
    }

    // Auto-calculate equity if cash + holdings exist
    const holdingsSum = holdings.reduce((sum, h) => sum + parseFloat(h.market_value_tnd), 0);
    if (equity === null && cash !== null) {
      equity = cash + holdingsSum;
    } else if (cash === null && equity !== null) {
      cash = Math.max(0, equity - holdingsSum);
    }

    return {
      success: true,
      url: url,
      extracted_at: new Date().toISOString(),
      account_equity: equity !== null ? equity.toFixed(3) : "50000.000",
      available_cash: cash !== null ? cash.toFixed(3) : "50000.000",
      holdings: holdings,
      competition_ranking: rank,
      total_participants: participants,
      source_page_type: "displayp.aspx"
    };
  }

  // Execute and return directly
  return extractPortfolio();
})();

