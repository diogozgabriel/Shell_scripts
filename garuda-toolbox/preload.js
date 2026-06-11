const { contextBridge, ipcRenderer, webUtils } = require('electron');

contextBridge.exposeInMainWorld('api', {
  checkTools: () => ipcRenderer.invoke('tools:check'),

  ocrCapture: () => ipcRenderer.invoke('ocr:capture'),
  ocrFile: (p) => ipcRenderer.invoke('ocr:file', p),
  onOcrTrigger: (fn) => ipcRenderer.on('ocr:trigger', fn),

  copyText: (t) => ipcRenderer.invoke('clipboard:write', t),
  openAiChatHub: () => ipcRenderer.invoke('open:aichathub'),

  convertCategory: (f) => ipcRenderer.invoke('convert:category', f),
  convertStart: (opts) => ipcRenderer.invoke('convert:start', opts),

  downloadStart: (opts) => ipcRenderer.invoke('download:start', opts),

  cancelTask: (id) => ipcRenderer.invoke('task:cancel', id),
  onProgress: (fn) => ipcRenderer.on('task:progress', (_e, p) => fn(p)),
  onLabel: (fn) => ipcRenderer.on('task:label', (_e, p) => fn(p)),
  onDone: (fn) => ipcRenderer.on('task:done', (_e, p) => fn(p)),

  showInFolder: (p) => ipcRenderer.invoke('file:show', p),
  pickDir: () => ipcRenderer.invoke('dialog:pick-dir'),
  pickFiles: (filters) => ipcRenderer.invoke('dialog:pick-files', filters),
  downloadsDir: () => ipcRenderer.invoke('os:downloads'),
  pathForFile: (file) => webUtils.getPathForFile(file),
});
