// Expose push-to-talk events from the main process to the renderer.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("catbot", {
  onPtt(cb) {
    ipcRenderer.on("ptt", (_event, state) => cb(state));
  },
});
