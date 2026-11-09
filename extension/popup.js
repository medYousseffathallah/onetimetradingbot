// Popup script for BVMT Intelligence Companion
const BACKEND_URL = "http://127.0.0.1:8000";

let extractedData = null;

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
  const stored = await chrome.storage.local.get(["pairingToken"]);
  if (stored.pairingToken) {
    tokenInput.value = stored.pairingToken;
  }

  saveTokenBtn.addEventListener("click", async () => {
    const val = tokenInput.value.trim();
    await chrome.storage.local.set({ pairingToken: val });
    showMsg("Pairing token saved locally.");
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

  // 3. Check Active Tab URL
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const isChallenge = tab && tab.url && (tab.url.includes("tunisbourse-challenge.com") || tab.url.includes("localhost") || tab.url.includes("127.0.0.1"));

  if (isChallenge) {
    tabNotice.innerHTML = `Active Tab: <strong style="color: #0f172a;">${tab.title || "Tunis Bourse Challenge"}</strong>`;
    extractBtn.disabled = false;
  } else {
    tabNotice.innerHTML = `<span style="color: #b91c1c;">Please navigate to <strong>tunisbourse-challenge.com</strong> in this browser window.</span>`;
    extractBtn.disabled = true;
  }

  // 4. Extract Account Data
  extractBtn.addEventListener("click", async () => {
    msgBox.style.display = "none";
    extractBtn.disabled = true;
    extractBtn.innerText = "Extracting DOM...";

    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ["content.js"]
      });

      if (!results || !results[0] || !results[0].result) {
        throw new Error("Unable to read content from active tab.");
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
      showMsg("Account data extracted successfully. Click Transmit to sync.");
    } catch (err) {
      showMsg(err.message, true);
    } finally {
      extractBtn.disabled = false;
      extractBtn.innerText = "Extract Account Data";
    }
  });

  // 5. Transmit to Localhost API
  sendBtn.addEventListener("click", async () => {
    if (!extractedData) return;
    const token = tokenInput.value.trim();
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
        pairing_token: token
      };

      const res = await fetch(`${BACKEND_URL}/api/sync/extension`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-BVMT-Pairing-Token": token
        },
        body: JSON.stringify(payload)
      });

      const resData = await res.json();
      if (!res.ok) {
        throw new Error(resData.detail || resData.error || "Failed to transmit snapshot to localhost.");
      }

      showMsg("✓ Snapshot transmitted to local dashboard! Switch to BVMT Intelligence to review & confirm.");
      sendBtn.innerText = "Transmitted Successfully";
    } catch (err) {
      showMsg(err.message, true);
      sendBtn.disabled = false;
      sendBtn.innerText = "Transmit to BVMT Dashboard";
    }
  });
});
