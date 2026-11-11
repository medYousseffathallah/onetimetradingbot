(() => {
  // Content script for BVMT Intelligence Companion
  // Strictly read-only extraction of visible account values from displayp.aspx and display_histo.aspx.
  // Never extracts passwords, cookies, or personal credentials. Never clicks trading buttons.
  const SCHEMA_VERSION = "2026.11-v2";

  function parseFrenchNumber(str) {
    if (str === null || str === undefined) return null;
    const raw = String(str)
      .replace(/\u00a0/g, "")
      .replace(/\u202f/g, "")
      .replace(/\s+/g, "")
      .replace(/TND/gi, "")
      .replace(/DT/gi, "")
      .replace(/%/g, "")
      .trim();

    if (!raw || raw === "..." || raw === "—" || raw === "--" || raw === "-" || /^n\/?a$/i.test(raw)) {
      return null;
    }

    let normalized = raw;
    const lastComma = normalized.lastIndexOf(",");
    const lastDot = normalized.lastIndexOf(".");
    if (lastComma !== -1 && lastDot !== -1) {
      if (lastComma > lastDot) {
        normalized = normalized.replace(/\./g, "").replace(",", ".");
      } else {
        normalized = normalized.replace(/,/g, "");
      }
    } else if (lastComma !== -1) {
      const commaCount = (normalized.match(/,/g) || []).length;
      normalized = commaCount > 1 ? normalized.replace(/,/g, "") : normalized.replace(",", ".");
    } else if ((normalized.match(/\./g) || []).length > 1) {
      normalized = normalized.replace(/\./g, "");
    }

    if (!/^[+-]?\d+(?:\.\d+)?$/.test(normalized)) {
      return null;
    }
    const num = Number(normalized);
    return Number.isFinite(num) ? num : null;
  }

  function isPlaceholderToken(str) {
    const t = String(str || "").replace(/[\s\u00a0\u202f]+/g, "").trim();
    return t === "" || t === "..." || t === "—" || t === "--" || t === "-" || /^n\/?a$/i.test(t);
  }

  function classifySide(raw) {
    const lower = String(raw || "").trim().toLowerCase();
    if (!lower) return null;
    if (/\b(achat|acheter|buy)\b/.test(lower) || lower === "a") return "BUY";
    if (/\b(vente|vendre|sell)\b/.test(lower) || lower === "v") return "SELL";
    return null;
  }

  function parseMovementTimestamp(raw) {
    const text = String(raw || "").replace(/[\u00a0\u202f]/g, " ").trim();
    if (!text) return new Date().toISOString();
    if (/^\d{4}-\d{2}-\d{2}T/.test(text)) return text;
    const fr = text.match(/^(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?/);
    if (fr) {
      const hh = fr[4] || "12";
      const mm = fr[5] || "00";
      const ss = fr[6] || "00";
      return `${fr[3]}-${fr[2]}-${fr[1]}T${hh}:${mm}:${ss}+01:00`;
    }
    return text;
  }

  function toInstrumentId(sym) {
    return String(sym || "").toUpperCase().replace(/[^A-Z0-9._-]+/g, "_");
  }

  function extractMovements(url, pageText) {
    if (pageText.includes("Mot de passe") && !/historique|op[ée]rations/i.test(pageText)) {
      return {
        success: false,
        error: "AUTH_REQUIRED",
        message: "Please log in to your Tunis Bourse Challenge account.",
        source_schema_version: SCHEMA_VERSION,
        validation_errors: ["Authentication required before reading movement history."],
      };
    }

    const tables = Array.from(document.querySelectorAll("table") || []);
    const validationErrors = [];
    const transactions = [];
    const pendingOrders = [];

    for (const t of tables) {
      const rows = Array.from(t.querySelectorAll("tr") || []);
      let colMap = null;

      for (const row of rows) {
        const headers = Array.from(row.querySelectorAll("th, td")).map(c =>
          String(c.innerText || c.textContent || "").trim().toLowerCase()
        );
        const hasVal = headers.some(h => h.includes("valeur") || h.includes("libell") || h.includes("nom"));
        const hasSens = headers.some(h => /sens|type|op[ée]ration/.test(h));
        const hasQty = headers.some(h => /quantit|nombre|qte/.test(h));
        if (hasVal && (hasSens || hasQty)) {
          const symIdx = headers.findIndex(
            h => h.includes("nom") || h.includes("libell") || h === "valeur" || h.includes("valeur")
          );
          colMap = {
            ref: headers.findIndex(h => /r[ée]f/.test(h) || h.includes("ordre") || h === "id"),
            date: headers.findIndex(h => h.includes("date") || h.includes("heure")),
            sym: symIdx,
            side: headers.findIndex(h => /sens|type|op[ée]ration/.test(h)),
            qty: headers.findIndex(h => /quantit|nombre|qte/.test(h)),
            price: headers.findIndex(h => h.includes("cours") || h.includes("prix")),
            amount: headers.findIndex(h => h.includes("montant")),
            fee: headers.findIndex(h => /commission|frais|courtage/.test(h)),
            status: headers.findIndex(h => /statut|[ée]tat/.test(h)),
          };
          break;
        }
      }

      if (!colMap || colMap.sym === -1) continue;

      for (let rIdx = 0; rIdx < rows.length; rIdx += 1) {
        const row = rows[rIdx];
        const cellEls = Array.from(row.querySelectorAll("td, th") || []);
        if (cellEls.length > 0 && cellEls.every(c => String(c.tagName || "").toUpperCase() === "TH")) {
          continue;
        }
        const cells = cellEls.map(c => String(c.innerText || c.textContent || "").trim());
        if (cells.length <= colMap.sym) continue;
        const headerCheck = cells.join(" ").toLowerCase();
        if (headerCheck.includes("nom de valeur") || headerCheck.includes("quantit")) {
          continue;
        }

        const symRaw = String(cells[colMap.sym] || "").replace(/[\r\n\t]+/g, " ").trim().toUpperCase();
        if (!symRaw || symRaw.includes("AUCUNE")) continue;

        const sideRaw = colMap.side !== -1 && cells[colMap.side] ? cells[colMap.side] : "";
        const side = classifySide(sideRaw);
        const qty = colMap.qty !== -1 && cells[colMap.qty] ? parseFrenchNumber(cells[colMap.qty]) : null;
        const price = colMap.price !== -1 && cells[colMap.price] ? parseFrenchNumber(cells[colMap.price]) : null;
        const amount = colMap.amount !== -1 && cells[colMap.amount] ? parseFrenchNumber(cells[colMap.amount]) : null;
        const fee = colMap.fee !== -1 && cells[colMap.fee] ? parseFrenchNumber(cells[colMap.fee]) : null;
        const statusRaw = colMap.status !== -1 && cells[colMap.status] ? cells[colMap.status] : "EXÉCUTÉ";
        const refRaw = colMap.ref !== -1 && cells[colMap.ref] ? cells[colMap.ref].trim() : `ROW-${rIdx}`;
        const dateIso = parseMovementTimestamp(colMap.date !== -1 && cells[colMap.date] ? cells[colMap.date] : "");

        if (!side || qty === null || qty <= 0) {
          validationErrors.push(`Invalid movement row for ${symRaw} (${refRaw})`);
          continue;
        }

        const resolvedPrice = price !== null && price > 0 ? price : (amount !== null && qty > 0 ? amount / qty : null);
        if (resolvedPrice === null || resolvedPrice <= 0) {
          validationErrors.push(`Missing execution/limit price for ${symRaw} (${refRaw})`);
          continue;
        }

        const isPending = /en\s*cours|attente|ouvert|pending|partiel/i.test(statusRaw);
        const instId = toInstrumentId(symRaw);
        if (isPending) {
          pendingOrders.push({
            order_id: refRaw,
            instrument_id: instId,
            symbol: symRaw,
            side,
            requested_shares: Math.round(qty),
            filled_shares: 0,
            remaining_shares: Math.round(qty),
            limit_price_tnd: resolvedPrice.toFixed(3),
            submitted_at: dateIso,
            status: "PENDING",
          });
        } else {
          transactions.push({
            transaction_id: refRaw,
            order_id: refRaw,
            instrument_id: instId,
            symbol: symRaw,
            side,
            filled_shares: Math.round(qty),
            execution_price_tnd: resolvedPrice.toFixed(3),
            fee_tnd: fee !== null ? fee.toFixed(3) : "0.000",
            executed_at: dateIso,
          });
        }
      }
    }

    if (transactions.length === 0 && pendingOrders.length === 0 && validationErrors.length === 0) {
      return {
        success: false,
        error: "UNKNOWN_LAYOUT",
        message: "No movement rows found on display_histo.aspx.",
        source_schema_version: SCHEMA_VERSION,
        source_page_type: "display_histo.aspx",
        validation_errors: ["No recognizable movement history table or rows found."],
      };
    }

    return {
      success: validationErrors.length === 0,
      url,
      extracted_at: new Date().toISOString(),
      source_schema_version: SCHEMA_VERSION,
      source_page_type: "display_histo.aspx",
      account_equity: null,
      available_cash: null,
      holdings: [],
      transactions,
      pending_orders: pendingOrders,
      competition_ranking: null,
      total_participants: null,
      displayed_overall_performance_pct: null,
      is_reconciled: true,
      reconciliation_gap_tnd: "0.000",
      validation_errors: validationErrors,
    };
  }

  function extractPortfolio() {
    const pageText = (document.body && (document.body.innerText || document.body.textContent)) || "";
    const url = (window.location && window.location.href) || "";

    if (/display_histo\.aspx/i.test(url)) {
      return extractMovements(url, pageText);
    }

    // Check if on login or password page
    if (pageText.includes("Mot de passe") && !/Liquidit[ée]s?/i.test(pageText)) {
      return {
        success: false,
        error: "AUTH_REQUIRED",
        message: "Please log in to your Tunis Bourse Challenge account.",
        source_schema_version: SCHEMA_VERSION,
        validation_errors: ["Authentication required before extracting portfolio."],
      };
    }

    // 1. Extract Cash (Liquidités)
    let cash = null;
    const cashMatch = pageText.match(/Liquidit[ée]s?\s*:?\s*([0-9\s\u00a0\u202f,\.]+)/i);
    if (cashMatch) {
      cash = parseFrenchNumber(cashMatch[1]);
    }

    // 2. Extract Total Equity (Votre portefeuille / Total portefeuille / Totaux)
    let equity = null;
    const eqMatch =
      pageText.match(/(?:Votre\s+portefeuille|Total\s*(?:du\s*)?portefeuille)\s*:?\s*([0-9\s\u00a0\u202f,\.]+)/i) ||
      pageText.match(/Totaux\s+([0-9\s\u00a0\u202f,\.]+)/i);
    if (eqMatch) {
      equity = parseFrenchNumber(eqMatch[1]);
    }

    // 3. Extract Ranking (Votre classement / Rang / Classement)
    let rank = null;
    let participants = null;
    const rankMatch = pageText.match(
      /(?:Votre\s+classement|Rang|Classement)\s*:?\s*#?([0-9\s\u00a0\u202f]+)(?:\s*\/\s*([0-9\s\u00a0\u202f]+))?/i
    );
    if (rankMatch) {
      const parsedRank = parseInt(rankMatch[1].replace(/[\s\u00a0\u202f]/g, ""), 10);
      if (Number.isFinite(parsedRank)) rank = parsedRank;
      if (rankMatch[2]) {
        const parsedPart = parseInt(rankMatch[2].replace(/[\s\u00a0\u202f]/g, ""), 10);
        if (Number.isFinite(parsedPart)) participants = parsedPart;
      }
    }

    // 4. Extract Displayed Overall Performance (%)
    let overallPerf = null;
    const perfMatch = pageText.match(
      /Performance\s+g[ée]n[ée]rale\s*:?\s*([+-]?[0-9\s\u00a0\u202f,\.]+)\s*%/i
    );
    if (perfMatch) {
      overallPerf = parseFrenchNumber(perfMatch[1]);
    }

    // 5. Extract Holdings from Table
    const holdings = [];
    const validationErrors = [];
    const seenSymbols = new Set();
    const tables = Array.from(document.querySelectorAll("table") || []);
    let targetTable =
      document.querySelector("#tab_portefeuille") || document.querySelector(".table_portefeuille");

    if (!targetTable) {
      for (const t of tables) {
        const text = String(t.innerText || t.textContent || "").toLowerCase();
        if (((text.includes("valeur") || text.includes("symbole")) && text.includes("quantit")) || text.includes("vendre")) {
          targetTable = t;
          break;
        }
      }
    }

    if (targetTable) {
      const rows = Array.from(targetTable.querySelectorAll("tr") || []);
      let colMap = null;

      // Identify header columns safely without colliding "Nom de valeur" with Market Value
      for (const row of rows) {
        const headers = Array.from(row.querySelectorAll("th, td")).map(c =>
          String(c.innerText || c.textContent || "").trim().toLowerCase()
        );
        const hasNom = headers.some(
          h => h.includes("nom") || h === "valeur" || h.includes("symbole") || h.includes("libell")
        );
        const hasQty = headers.some(h => h.includes("quantit"));
        if (hasNom && hasQty) {
          const symIdx = headers.findIndex(
            h => h.includes("nom") || h === "valeur" || h.includes("symbole") || h.includes("libell")
          );
          colMap = {
            sym: symIdx,
            qty: headers.findIndex(h => h.includes("quantit")),
            acqPx: headers.findIndex(h => h.includes("prix") || h.includes("achat") || h.includes("pmp")),
            montant: headers.findIndex(h => h.includes("montant")),
            latPx: headers.findIndex(h => h.includes("dernier") || h.includes("cours")),
            mktVal: headers.findIndex(
              (h, idx) =>
                idx !== symIdx &&
                (h.includes("capital") || h.includes("valoris") || h.includes("march") || h === "valeur")
            ),
            gainDt: headers.findIndex(h => h.includes("gain") && h.includes("dt")),
            gainPct: headers.findIndex(h => h.includes("gain") && h.includes("%")),
          };
          break;
        }
      }

      for (const row of rows) {
        const cellEls = Array.from(row.querySelectorAll("td, th") || []);
        if (cellEls.length < 2) continue;

        // Skip genuine HTML <th> header rows unconditionally
        if (cellEls.every(c => String(c.tagName || "").toUpperCase() === "TH")) {
          continue;
        }

        const cells = cellEls.map(c => String(c.innerText || c.textContent || "").trim());
        const first = cells[0].toLowerCase();
        const second = (cells[1] || "").toLowerCase();
        const joinedLower = cells.join(" ").toLowerCase();

        // Capture Liquidités if present inside table
        if (first.includes("liquidit") || joinedLower.includes("liquidit")) {
          if (cash === null) {
            for (let idx = cells.length - 1; idx >= 0; idx -= 1) {
              const maybeCash = parseFrenchNumber(cells[idx]);
              if (maybeCash !== null) {
                cash = maybeCash;
                break;
              }
            }
          }
          continue;
        }

        // Skip header / summary footer rows (avoid matching data stock rows containing "TOTAL TUNISIE")
        if (
          first.includes("nom de valeur") ||
          second.includes("nom de valeur") ||
          first === "valeur" ||
          first.includes("symbole") ||
          first.includes("titre") ||
          first.startsWith("totaux") ||
          first === "total" ||
          second.startsWith("totaux") ||
          joinedLower.includes("quantit")
        ) {
          continue;
        }

        let sym = "";
        let displayedIdentifier = null;
        let qty = null;
        let acqPx = null;
        let latPx = null;
        let mktVal = null;
        let acqAmt = null;
        let gainTnd = null;
        let gainPct = null;

        const tbodyObj = typeof row.closest === "function" ? row.closest("tbody") : null;
        const tbodyCls = String((tbodyObj && tbodyObj.className) || row.className || "").toLowerCase();
        const is12CellAlri =
          cells.length >= 12 &&
          (tbodyCls.includes("alri") || (/^\d+$/.test(cells[2]) && /^[ASV]$/i.test(cells[5])));

        if (is12CellAlri) {
          // 12-cell tbody.alri challenge table layout:
          // [0] vendre | [1] ticker (.no) | [2] id (.no) | [3] name | [4] qty | [5] side(A/S) |
          // [6] acqPx | [7] acqAmt | [8] lastPx | [9] mktVal | [10] gainDt | [11] gain%
          const anchor = cellEls[3] && typeof cellEls[3].querySelector === "function"
            ? cellEls[3].querySelector("a")
            : null;
          sym = String(
            (anchor && (anchor.innerText || anchor.textContent)) || cells[3] || cells[1]
          ).toUpperCase();
          displayedIdentifier = /^\d+$/.test(cells[2]) ? cells[2] : null;
          qty = parseFrenchNumber(cells[4]);
          acqPx = parseFrenchNumber(cells[6]);
          acqAmt = parseFrenchNumber(cells[7]);
          latPx = parseFrenchNumber(cells[8]);
          mktVal = parseFrenchNumber(cells[9]);
          gainTnd = parseFrenchNumber(cells[10]);
          gainPct = parseFrenchNumber(cells[11]);
        } else if (
          colMap &&
          colMap.sym !== -1 &&
          colMap.qty !== -1 &&
          cells.length > Math.max(colMap.sym, colMap.qty)
        ) {
          sym = cells[colMap.sym].toUpperCase();
          const qtyParsed = parseFrenchNumber(cells[colMap.qty]);
          qty = qtyParsed;
          if (qtyParsed === null && !isPlaceholderToken(cells[colMap.qty])) {
            validationErrors.push(`Unparseable quantity '${cells[colMap.qty]}' for ${sym}`);
          }
          acqPx = colMap.acqPx !== -1 && colMap.acqPx < cells.length ? parseFrenchNumber(cells[colMap.acqPx]) : null;
          if (colMap.acqPx !== -1 && acqPx === null && !isPlaceholderToken(cells[colMap.acqPx])) {
            validationErrors.push(`Unparseable acquisition price '${cells[colMap.acqPx]}' for ${sym}`);
          }
          acqAmt = colMap.montant !== -1 && colMap.montant < cells.length ? parseFrenchNumber(cells[colMap.montant]) : null;
          latPx = colMap.latPx !== -1 && colMap.latPx < cells.length ? parseFrenchNumber(cells[colMap.latPx]) : null;
          mktVal = colMap.mktVal !== -1 && colMap.mktVal < cells.length ? parseFrenchNumber(cells[colMap.mktVal]) : null;
          gainTnd = colMap.gainDt !== -1 && colMap.gainDt < cells.length ? parseFrenchNumber(cells[colMap.gainDt]) : null;
          gainPct = colMap.gainPct !== -1 && colMap.gainPct < cells.length ? parseFrenchNumber(cells[colMap.gainPct]) : null;
        } else {
          // Positional fallback without header map
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
            qty = nums[0];
            acqPx = nums[1];
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
        if (!sym || sym === "VENDRE" || sym.length > 50 || sym.includes("LIQUIDIT") || sym.startsWith("TOTAUX")) {
          continue;
        }

        if (seenSymbols.has(sym)) {
          validationErrors.push(`Duplicate holding row for symbol: ${sym}`);
          continue;
        }
        seenSymbols.add(sym);

        const intQty = qty !== null ? Math.round(qty) : null;
        if (intQty === null || intQty <= 0) {
          validationErrors.push(`Invalid or missing quantity for ${sym}`);
          continue;
        }
        if (acqPx === null || acqPx <= 0) {
          validationErrors.push(`Invalid or missing acquisition price for ${sym}`);
          continue;
        }

        // Derive latest price from market value if placeholder ("...") was rendered in Dernier
        if (latPx === null && mktVal !== null && intQty > 0) {
          latPx = mktVal / intQty;
        } else if (latPx === null) {
          latPx = acqPx;
        }
        if (mktVal === null) {
          mktVal = intQty * latPx;
        }
        const resolvedAcqAmt = acqAmt !== null ? acqAmt : intQty * acqPx;
        const resolvedGainTnd = gainTnd !== null ? gainTnd : mktVal - resolvedAcqAmt;

        const holdingItem = {
          symbol: sym,
          instrument_id: toInstrumentId(sym),
          quantity: intQty,
          acquisition_price_tnd: acqPx.toFixed(3),
          acquisition_amount_tnd: resolvedAcqAmt.toFixed(3),
          latest_price_tnd: latPx.toFixed(3),
          market_value_tnd: mktVal.toFixed(3),
          gain_tnd: resolvedGainTnd.toFixed(3),
          gain_pct: gainPct !== null ? gainPct.toFixed(2) : null,
          displayed_name: sym,
        };
        if (displayedIdentifier !== null) {
          holdingItem.displayed_identifier = displayedIdentifier;
        }
        holdings.push(holdingItem);
      }
    }

    // Never fabricate "50000.000" when balances are completely missing
    if (equity === null && cash === null) {
      return {
        success: false,
        error: "MISSING_BALANCES",
        message: "Could not locate account equity (Votre portefeuille) or cash (Liquidités) in DOM.",
        source_schema_version: SCHEMA_VERSION,
        source_page_type: "displayp.aspx",
        account_equity: null,
        available_cash: null,
        holdings,
        validation_errors:
          validationErrors.length > 0
            ? validationErrors
            : ["Missing account equity and available cash balances in page DOM."],
      };
    }

    const holdingsSum = holdings.reduce((sum, h) => sum + Number(h.market_value_tnd), 0);
    if (equity === null && cash !== null) {
      equity = cash + holdingsSum;
    } else if (cash === null && equity !== null) {
      cash = Math.max(0, equity - holdingsSum);
    }

    const reconciliationGap = Math.abs(cash + holdingsSum - equity);
    const isReconciled = reconciliationGap < 0.100;

    return {
      success: validationErrors.length === 0,
      url,
      extracted_at: new Date().toISOString(),
      source_schema_version: SCHEMA_VERSION,
      account_equity: equity.toFixed(3),
      available_cash: cash.toFixed(3),
      holdings,
      competition_ranking: rank,
      total_participants: participants,
      displayed_overall_performance_pct: overallPerf !== null ? overallPerf.toFixed(3) : null,
      source_page_type: "displayp.aspx",
      is_reconciled: isReconciled,
      reconciliation_gap_tnd: reconciliationGap.toFixed(3),
      validation_errors: validationErrors,
    };
  }

  return extractPortfolio();
})();
