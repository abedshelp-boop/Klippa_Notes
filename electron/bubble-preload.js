const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('bubbleAPI', {
  showMainWindow: () => ipcRenderer.invoke('bubble:show-main'),
  triggerNote: () => ipcRenderer.invoke('bubble:trigger-note'),
  openPicker: () => ipcRenderer.invoke('picker:open'),
  openLangPicker: () => ipcRenderer.invoke('lang-picker:open'),
  moveBubble: (dx, dy) => ipcRenderer.send('bubble:move', dx, dy),
  setInteractive: (interactive) => ipcRenderer.send('bubble:set-interactive', !!interactive),
});
