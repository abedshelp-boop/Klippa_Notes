// @ts-check
/**
 * ID generators for canvas entities. Every id MUST come from here —
 * no inline string concat — so collisions are impossible by construction
 * and prefix-based routing in validators stays sound.
 */

/**
 * 12-byte random suffix, base64url-encoded. crypto.randomUUID would also work
 * but produces longer ids; this stays short enough to read in dev console.
 * @returns {string}
 */
function randomSuffix() {
  const bytes = new Uint8Array(9);
  // crypto.getRandomValues exists in Node 19+ (the project's runtime) and all browsers.
  globalThis.crypto.getRandomValues(bytes);
  let s = '';
  for (let i = 0; i < bytes.length; i += 1) s += String.fromCharCode(bytes[i]);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** @returns {string} */
export function cardId() { return `card_${randomSuffix()}`; }

/** @returns {string} */
export function frameId() { return `frame_${randomSuffix()}`; }

/** @returns {string} */
export function connectorId() { return `conn_${randomSuffix()}`; }

/** @returns {string} */
export function noteCardId() { return `ncard_${randomSuffix()}`; }
