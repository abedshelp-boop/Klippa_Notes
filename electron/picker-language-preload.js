const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('languageAPI', {
  get: () => ipcRenderer.invoke('lang-picker:get'),
  select: (payload) => ipcRenderer.invoke('lang-picker:select', payload),
  close: () => ipcRenderer.invoke('lang-picker:close'),
});
