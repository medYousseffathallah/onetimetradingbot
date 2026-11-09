// Content script for BVMT Intelligence Companion
// Strictly read-only extraction of visible account values from displayp.aspx and display_histo.aspx
// Never extracts passwords, cookies, or personal credentials. Never clicks trading buttons.

(() => {
  function parseFrenchNumber(str) {
    if (!str) return null;
    const clean = str.replace(/\xa0/g, "").replace(/\s/g, "").replace(/DT/gi, "").replace(/,/g, ".");
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

    // 2. Extract Total Equity (Total portefeuille)
    let equity = null;
    const eqMatch = pageText.match(/Total\s*(?:du)?\s*portefeuille\s*:?\s*([0-9\s,\.]+)/i);
    if (eqMatch) {
      equity = parseFrenchNumber(eqMatch[1]);
    }

    // 3. Extract Ranking
    let rank = null;
    let participants = null;
    const rankMatch = pageText.match(/(?:Rang|Classement)\s*:?\s*#?([0-9\s]+)(?:\s*\/\s*([0-9\s]+))?/i);
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
        if (cells.length < 3) continue;
        const first = cells[0].toLowerCase();
        if (first.includes("valeur") || first.includes("titre") || first.includes("symbole") || first.includes("total") || first.includes("liquidit")) {
          continue;
        }

        const sym = cells[0].toUpperCase();
        if (!sym || sym.length > 40) continue;

        // Find numbers in remaining cells
        const nums = [];
        for (let i = 1; i < cells.length; i++) {
          const val = parseFrenchNumber(cells[i]);
          if (val !== null) nums.push(val);
        }

        if (nums.length >= 2) {
          const qty = Math.round(nums[0]);
          const acqPx = nums[1];
          const latPx = nums.length >= 3 ? nums[2] : acqPx;
          const mktVal = nums.length >= 4 ? nums[3] : (qty * latPx);

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

