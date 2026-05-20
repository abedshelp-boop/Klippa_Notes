/**
 * Dev-time debug helper. `log` and `warn` are no-ops in production builds.
 * `error` always surfaces — errors are signals we want visible, not silently dropped.
 *
 * Boundary-log doctrine: prefer one log at a process/network doorway over many
 * logs inside function bodies. Use the debugger or React DevTools for state.
 */

/**
 * @param {boolean} isDev
 */
export function createDebug(isDev) {
  /**
   * @param {string} subsystem
   * @param {string} message
   */
  const format = (subsystem, message) => `[${subsystem}] ${message}`;

  return {
    /**
     * @param {string} subsystem
     * @param {string} message
     * @param {...unknown} data
     */
    log(subsystem, message, ...data) {
      if (!isDev) return;
      // eslint-disable-next-line no-console
      console.log(format(subsystem, message), ...data);
    },
    /**
     * @param {string} subsystem
     * @param {string} message
     * @param {...unknown} data
     */
    warn(subsystem, message, ...data) {
      if (!isDev) return;
      // eslint-disable-next-line no-console
      console.warn(format(subsystem, message), ...data);
    },
    /**
     * @param {string} subsystem
     * @param {string} message
     * @param {...unknown} data
     */
    error(subsystem, message, ...data) {
      // ALWAYS prints — errors stay loud, even in prod.
      // eslint-disable-next-line no-console
      console.error(format(subsystem, message), ...data);
    },
  };
}

export const debug = createDebug(import.meta.env.DEV);
