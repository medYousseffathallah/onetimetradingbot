// Background service worker for BVMT Intelligence Companion
// Manifest V3 lifecycle listener & async upload relay (survives popup close)
chrome.runtime.onInstalled.addListener(() => {
  console.log("BVMT Intelligence Companion extension installed.");
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.type !== "BVMT_SYNC_UPLOAD") {
    return false;
  }

  (async () => {
    try {
      const headers = {
        "Content-Type": "application/json",
      };
      if (message.pairingToken) {
        headers["X-BVMT-Pairing-Token"] = message.pairingToken;
      }

      const res = await fetch(message.endpointUrl, {
        method: "POST",
        headers,
        body: JSON.stringify(message.payload),
      });

      let data = {};
      try {
        data = await res.json();
      } catch {
        data = {};
      }

      const detail =
        data && typeof data.detail === "string"
          ? data.detail
          : data && data.detail
            ? JSON.stringify(data.detail)
            : (data && data.error) || `HTTP ${res.status}`;

      sendResponse({
        ok: Boolean(res.ok),
        status: res.status,
        data,
        error: res.ok ? null : detail,
      });
    } catch (err) {
      sendResponse({
        ok: false,
        status: 0,
        data: null,
        error: err && err.message ? err.message : String(err),
      });
    }
  })();

  return true;
});
