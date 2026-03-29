/**
 * Klippa Content Script
 *
 * Injected into every page. Polls for <video> elements that are actively
 * playing and reports the page title + URL to the background service worker.
 */

const POLL_INTERVAL_MS = 2000;

let lastReportedUrl = null;
let lastReportedPlaying = null;

function cleanTitle(raw) {
  return raw
    .replace(/\s*[-–—|]\s*(YouTube|Vimeo|Twitch|Dailymotion|Google Chrome|Mozilla Firefox|Microsoft Edge).*$/i, "")
    .trim();
}

function hasPlayingVideo() {
  const videos = document.querySelectorAll("video");
  for (const v of videos) {
    if (!v.paused && v.readyState > 2 && v.duration > 0) {
      return true;
    }
  }
  return false;
}

function poll() {
  const playing = hasPlayingVideo();
  const url = window.location.href;

  if (playing && (url !== lastReportedUrl || lastReportedPlaying !== true)) {
    lastReportedUrl = url;
    lastReportedPlaying = true;
    chrome.runtime.sendMessage({
      type: "video_playing",
      title: cleanTitle(document.title),
      url: url,
    });
  } else if (!playing && lastReportedPlaying === true) {
    lastReportedPlaying = false;
    chrome.runtime.sendMessage({
      type: "video_stopped",
      url: url,
    });
  }
}

setInterval(poll, POLL_INTERVAL_MS);
poll();
