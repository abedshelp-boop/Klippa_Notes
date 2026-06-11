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

  // Phase 4: subscribe to "open this note in edit mode" requests from the
  // main process (used by the picker's "+ Create empty note" row).
  onOpenNote: (callback) => {
    const handler = (_event, noteId) => callback(noteId);
    ipcRenderer.on('note:open', handler);
    return () => ipcRenderer.removeListener('note:open', handler);
  },

  // Sub-project 5: tell the main process which note (if any) is open, so it
  // can push foreground + open-note context to the Python service. Voice
  // routing uses this for the no-qualifier "Hey Deen, [content]" default
  // (route to the open note instead of Quick Inbox).
  notifyOpenNote: (noteId) => ipcRenderer.invoke('context:open-note', noteId),

  // Sub-project 4: hear-back. The renderer asks for TTS by text, main does
  // the fetch + returns the WAV ArrayBuffer so the renderer can play it via
  // a regular HTMLAudioElement. Returns null on any failure — TTS must
  // never crash the user-visible "saved" path.
  ttsSay: (text) => ipcRenderer.invoke('tts:say', text),
});
