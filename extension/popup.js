// Popup script for BVMT Intelligence Companion
const BACKEND_URL = "http://127.0.0.1:8000";

let extractedData = null;

function isAllowedChallengeUrl(url) {
  if (!url || typeof url !== "string") return false;
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.toLowerCase();
    return (
      host === "tunisbourse-challenge.com" ||
      host === "www.tunisbourse-challenge.com" ||
      host === "tunisbourse.com.tn" ||
      host === "www.tunisbourse.com.tn" ||
      host === "localhost" ||
      host === "127.0.0.1"
    );
  } catch {
    return false;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  const tokenInput = document.getElementById("tokenInput");
  const saveTokenBtn = document.getElementById("saveTokenBtn");
  const connectionStatus = document.getElementById("connectionStatus");
  const tabNotice = document.getElementById("tabNotice");
  const extractBtn = document.getElementById("extractBtn");
  const previewCard = document.getElementById("previewCard");
  const prevEquity = document.getElementById("prevEquity");
  const prevCash = document.getElementById("prevCash");
  const prevHoldings = document.getElementById("prevHoldings");
  const prevRank = document.getElementById("prevRank");
  const sendBtn = document.getElementById("sendBtn");
  const msgBox = document.getElementById("msgBox");

  function showMsg(text, isError = false) {
    msgBox.style.display = "block";
    msgBox.className = `alert-box ${isError ? "alert-error" : "alert-success"}`;
    msgBox.innerText = text;
  }

  // 1. Load saved pairing token
  try {
    if (chrome?.storage?.local) {
      const stored = await chrome.storage.local.get(["pairingToken"]);
      if (stored.pairingToken) {
        tokenInput.value = stored.pairingToken;
      }
    }
  } catch (err) {
    console.warn("Could not read local storage:", err);
  }

  saveTokenBtn.addEventListener("click", async () => {
    const val = tokenInput.value.trim();
    if (!val) {
      showMsg("Please enter a valid pairing token.", true);
      return;
    }
    try {
      if (chrome?.storage?.local) {
        await chrome.storage.local.set({ pairingToken: val });
        showMsg("Pairing token saved locally.");
      } else {
        showMsg("Storage API unavailable. Token will be used for this session only.");
      }
    } catch (err) {
      showMsg(`Failed to save token: ${err.message}`, true);
    }
    checkBackend();
  });

  // 2. Check Local Backend Connectivity
  async function checkBackend() {
    try {
      const res = await fetch(`${BACKEND_URL}/api/health`, { method: "GET" });
      if (res.ok) {
        connectionStatus.className = "status-badge status-online";
        connectionStatus.innerText = "● Localhost Ready";
      } else {
        connectionStatus.className = "status-badge status-offline";
        connectionStatus.innerText = "● Backend Error";
      }
    } catch {
      connectionStatus.className = "status-badge status-offline";
      connectionStatus.innerText = "● Backend Offline";
    }
  }
  checkBackend();

  // 3. Inspect Active Tab Safely
  let activeTab = null;
  try {
    if (chrome?.tabs?.query) {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tabs && tabs.length > 0) {
        activeTab = tabs[0];
      }
    }
  } catch (err) {
    console.warn("Failed to query active tab:", err);
  }

  if (!activeTab || typeof activeTab.id !== "number") {
    tabNotice.innerHTML = `<span style="color: #b91c1c;">No active browser tab found. Open Tunis Bourse Challenge and reopen the extension.</span>`;
    extractBtn.disabled = true;
  } else {
    const url = activeTab.url || "";
    const isChallenge = isAllowedChallengeUrl(url);

    if (isChallenge) {
      tabNotice.innerHTML = `Active Tab: <strong style="color: #0f172a;">${activeTab.title || url}</strong>`;
      extractBtn.disabled = false;
    } else {
      tabNotice.innerHTML = `<span style="color: #b91c1c;">Active page is not a Tunis Bourse Challenge portal. Please navigate to <strong>tunisbourse-challenge.com/displayp.aspx</strong>.</span>`;
      extractBtn.disabled = true;
    }
  }

  // 4. Extract Account Data
  extractBtn.addEventListener("click", async () => {
    msgBox.style.display = "none";
    extractBtn.disabled = true;
    extractBtn.innerText = "Extracting DOM...";

    try {
      // Defensive Scripting API check
      if (!chrome?.scripting?.executeScript) {
        throw new Error(
          "Chrome Scripting API unavailable. Check extension permissions and reload the extension."
        );
      }

      // Re-verify current active tab
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const targetTab = tabs && tabs.length > 0 ? tabs[0] : null;

      if (!targetTab || typeof targetTab.id !== "number") {
        throw new Error("No active browser tab detected. Please reopen the extension on the competition tab.");
      }

      const targetUrl = targetTab.url || "";
      if (
        targetUrl.startsWith("chrome://") ||
        targetUrl.startsWith("chrome-extension://") ||
        targetUrl.startsWith("edge://") ||
        targetUrl.startsWith("about:")
      ) {
        throw new Error("Cannot run on internal browser pages. Navigate to tunisbourse-challenge.com/displayp.aspx.");
      }

      if (!isAllowedChallengeUrl(targetUrl)) {
        throw new Error(
          "Active tab is not an authorized Tunis Bourse Challenge domain. Navigate to tunisbourse-challenge.com/displayp.aspx."
        );
      }

      const results = await chrome.scripting.executeScript({
        target: { tabId: targetTab.id },
        files: ["content.js"],
      });

      if (!results || !results[0] || results[0].result === undefined || results[0].result === null) {
        throw new Error("Unable to read content from active tab. Ensure the page is completely loaded.");
      }

      const res = results[0].result;
      if (res.error) {
        throw new Error(res.message || "Failed to extract account data.");
      }

      extractedData = res;
      prevEquity.innerText = `${res.account_equity} TND`;
      prevCash.innerText = `${res.available_cash} TND`;
      prevHoldings.innerText = res.holdings.length.toString();
      prevRank.innerText = res.competition_ranking ? `#${res.competition_ranking}` : "—";
      previewCard.style.display = "block";
      showMsg("Account data extracted successfully! Click 'Transmit to Platform' to stage the snapshot.");
    } catch (err) {
      showMsg(err.message || String(err), true);
    } finally {
      extractBtn.disabled = false;
      extractBtn.innerText = "Extract Account Data";
    }
  });

  // 5. Transmit to Localhost API
  sendBtn.addEventListener("click", async () => {
    if (!extractedData) {
      showMsg("No extracted data available. Click 'Extract Account Data' first.", true);
      return;
    }
    const token = tokenInput.value.trim();
    if (!token) {
      showMsg("Please enter and save your local pairing token before transmitting.", true);
      return;
    }

    sendBtn.disabled = true;
    sendBtn.innerText = "Transmitting to Dashboard...";

    try {
      const payload = {
        source: "CHROME_EXTENSION",
        capture_timestamp: extractedData.extracted_at,
        snapshot_id: `ext_${Date.now()}`,
        account_equity: extractedData.account_equity,
        available_cash: extractedData.available_cash,
        holdings: extractedData.holdings,
        competition_ranking: extractedData.competition_ranking,
        total_participants: extractedData.total_participants,
        source_page_type: extractedData.source_page_type,
        pairing_token: token,
      };

      const res = await fetch(`${BACKEND_URL}/api/sync/extension`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-BVMT-Pairing-Token": token,
        },
        body: JSON.stringify(payload),
      });

      const resData = await res.json();
      if (!res.ok) {
        const errorDetail = resData.detail || resData.error || "Failed to transmit snapshot to localhost.";
        throw new Error(typeof errorDetail === "string" ? errorDetail : JSON.stringify(errorDetail));
      }

      showMsg("✓ Snapshot staged successfully! Switch to the BVMT Dashboard to review reconciliation & confirm.");
      sendBtn.innerText = "Transmitted Successfully";
    } catch (err) {
      showMsg(err.message || String(err), true);
      sendBtn.disabled = false;
      sendBtn.innerText = "Transmit to BVMT Dashboard";
    }
  });
});
