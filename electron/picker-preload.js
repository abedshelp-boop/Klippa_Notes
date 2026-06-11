const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('pickerAPI', {
  listNotes: () => ipcRenderer.invoke('picker:list-notes'),
  // Phase 10: fetch notes + groups in a single round-trip so the picker can
  // render the tree without flicker.
  listTree: () => ipcRenderer.invoke('picker:tree'),
  getTarget: () => ipcRenderer.invoke('picker:get-target'),
  select: (noteId) => ipcRenderer.invoke('picker:select', noteId),
  createNew: () => ipcRenderer.invoke('picker:create-new'),
  // Phase 4: create an empty note immediately (not pending) and open it
  // in the main window in edit mode. Distinct from createNew above —
  // createNew sets the routing target for the NEXT audio capture, while
  // createEmptyNote materializes a row right now so the user can type.
  createEmptyNote: () => ipcRenderer.invoke('picker:create-empty-note'),
  close: () => ipcRenderer.invoke('picker:close'),
});
