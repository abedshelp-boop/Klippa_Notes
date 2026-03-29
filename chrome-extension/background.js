/**
 * Klippa Background Service Worker
 *
 * Receives video state messages from content scripts across all tabs,
 * deduplicates, and POSTs the current video context to the Python service.
 */

const API_BASE = "http://127.0.0.1:8765";

// tabId -> { title, url }  — tracks which tabs have a playing video
const activeTabs = new Map();

let lastSentUrl = null;

function pickActiveVideo() {
  if (activeTabs.size === 0) return null;
  // If multiple tabs have playing videos, pick the most recently updated one.
  // Map iteration order is insertion/update order, so the last entry is newest.
  let latest = null;
  for (const entry of activeTabs.values()) {
    latest = entry;
  }
  return latest;
}

async function sendContext(video) {
  const url = video ? video.url : null;

  if (url === lastSentUrl) return;
  lastSentUrl = url;

  const body = video
    ? { title: video.title, url: video.url }
    : { title: null, url: null };

  try {
    await fetch(`${API_BASE}/video-context`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (_) {
    // Python service may not be running; silently ignore.
  }
}

chrome.runtime.onMessage.addListener((msg, sender) => {
  const tabId = sender.tab?.id;
  if (!tabId) return;

  if (msg.type === "video_playing") {
    activeTabs.set(tabId, { title: msg.title, url: msg.url });
    sendContext(pickActiveVideo());
  } else if (msg.type === "video_stopped") {
    activeTabs.delete(tabId);
    sendContext(pickActiveVideo());
  }
});

// Clean up when a tab is closed or navigates away.
chrome.tabs.onRemoved.addListener((tabId) => {
  if (activeTabs.has(tabId)) {
    activeTabs.delete(tabId);
    sendContext(pickActiveVideo());
  }
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.url && activeTabs.has(tabId)) {
    activeTabs.delete(tabId);
    sendContext(pickActiveVideo());
  }
});
