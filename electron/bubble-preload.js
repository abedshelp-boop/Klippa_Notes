const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('bubbleAPI', {
  showMainWindow: () => ipcRenderer.invoke('bubble:show-main'),
  triggerNote: () => ipcRenderer.invoke('bubble:trigger-note'),
  moveBubble: (dx, dy) => ipcRenderer.send('bubble:move', dx, dy),
  setInteractive: (interactive) => ipcRenderer.send('bubble:set-interactive', !!interactive),
});
