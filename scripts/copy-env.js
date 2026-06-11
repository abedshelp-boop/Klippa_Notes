// Copies repo-root .env into python-service/.env so it ships inside the
// electron-builder extraResources bundle. Personal-use installer only.
// DO NOT commit python-service/.env (it's in .gitignore).
const fs = require('fs');
const path = require('path');

const src = path.join(__dirname, '..', '.env');
const dst = path.join(__dirname, '..', 'python-service', '.env');

if (!fs.existsSync(src)) {
  console.error('[copy-env] No .env at repo root — aborting to avoid shipping an installer without API keys.');
  process.exit(1);
}
fs.copyFileSync(src, dst);
console.log('[copy-env] Copied .env -> python-service/.env');
