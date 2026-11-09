// Background service worker for BVMT Intelligence Companion
// Manifest V3 lifecycle listener
chrome.runtime.onInstalled.addListener(() => {
  console.log("BVMT Intelligence Companion extension installed.");
});
