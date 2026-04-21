const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  minimize: () => ipcRenderer.invoke('window:minimize'),
  maximize: () => ipcRenderer.invoke('window:maximize'),
  close: () => ipcRenderer.invoke('window:close'),
  triggerNote: () => ipcRenderer.invoke('trigger-note'),

  toggleBubble: () => ipcRenderer.invoke('bubble:toggle'),
  setBubbleVisible: (visible) => ipcRenderer.invoke('bubble:set-visible', visible),
  getBubbleVisible: () => ipcRenderer.invoke('bubble:get-visible'),
  onBubbleVisibilityChange: (callback) => {
    const handler = (_event, visible) => callback(visible);
    ipcRenderer.on('bubble:visibility', handler);
    return () => ipcRenderer.removeListener('bubble:visibility', handler);
  },
});
