const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('petAPI', {
  moveWindow: (dx, dy) => ipcRenderer.send('move-window', { dx, dy }),
  minimizeWindow: () => ipcRenderer.send('minimize-window'),
  getWindowPosition: () => ipcRenderer.sendSync('get-window-position'),
  onPetAction: (callback) => {
    ipcRenderer.on('pet-action', (event, action) => callback(action));
  }
});
