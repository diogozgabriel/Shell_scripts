const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  getConfig: () => ipcRenderer.invoke('config:get'),
  saveConfig: (config) => ipcRenderer.invoke('config:save', config),
  resetConfig: () => ipcRenderer.invoke('config:reset'),
  clearSession: (serviceId) => ipcRenderer.invoke('service:clear-session', serviceId),
  getUserAgent: () => ipcRenderer.invoke('app:user-agent'),
});
