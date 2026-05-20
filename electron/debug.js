// Dev-time debug helper for the Electron main process.
// `log` / `warn` are dev-gated. `error` always prints (errors stay loud).
// CommonJS module — matches the rest of electron/.

function createDebug(isDev) {
  const format = (subsystem, message) => `[${subsystem}] ${message}`;

  return {
    log(subsystem, message, ...data) {
      if (!isDev) return;
      console.log(format(subsystem, message), ...data);
    },
    warn(subsystem, message, ...data) {
      if (!isDev) return;
      console.warn(format(subsystem, message), ...data);
    },
    error(subsystem, message, ...data) {
      console.error(format(subsystem, message), ...data);
    },
  };
}

module.exports = { createDebug };
