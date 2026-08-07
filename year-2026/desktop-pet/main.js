const electron = require('electron');
const { app, BrowserWindow, Tray, Menu, nativeImage, screen } = electron;
const { ipcMain } = electron;
const path = require('path');

let win = null;
let tray = null;
let isQuitting = false;

function createTrayIcon() {
  // Create a simple 16x16 tray icon as a data URL
  const icon = nativeImage.createFromDataURL(
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAARklEQVQ4T2NkYPj/n4EBBJgYKAQMowYMhAETmRoSVuPfv38Mv379YuDg4GBgZmaGqwFJg3gODAxUcOD///8ZdHV1Gf7+/TtuAAAuFhZyLkINJQAAAABJRU5ErkJggg=='
  );
  const r = icon.resize({ width: 16, height: 16 });
  tray = new Tray(r);
  
  const contextMenu = Menu.buildFromTemplate([
    {
      label: '喂食 🐟',
      click: () => { if (win) win.webContents.send('pet-action', 'feed'); }
    },
    {
      label: '玩耍 🎾',
      click: () => { if (win) win.webContents.send('pet-action', 'play'); }
    },
    {
      label: '睡觉 😴',
      click: () => { if (win) win.webContents.send('pet-action', 'sleep'); }
    },
    { type: 'separator' },
    {
      label: '关于桌宠',
      click: () => {
        const { dialog } = require('electron');
        dialog.showMessageBox({
          type: 'info',
          title: '关于',
          message: '桌面宠物 v0.1.0',
          detail: '一只可爱的小猫咪陪你工作 🐱\n由 WorkBuddy + Electron 打造'
        });
      }
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        isQuitting = true;
        app.quit();
      }
    }
  ]);
  
  tray.setToolTip('桌面宠物 - 小猫咪');
  tray.setContextMenu(contextMenu);
  
  // Double-click tray to show/hide pet
  tray.on('double-click', () => {
    if (win) {
      win.isVisible() ? win.hide() : win.show();
    }
  });
}

function createWindow() {
  const { width: screenW, height: screenH } = screen.getPrimaryDisplay().workAreaSize;
  
  win = new BrowserWindow({
    width: 200,
    height: 220,
    x: screenW - 220,
    y: screenH - 260,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  win.loadFile(path.join(__dirname, 'src', 'index.html'));

  // Prevent window from closing — hide instead
  win.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault();
      win.hide();
    }
  });

  win.on('closed', () => {
    win = null;
  });
}

// IPC handlers
ipcMain.on('move-window', (event, { dx, dy }) => {
  if (win) {
    const [x, y] = win.getPosition();
    win.setPosition(x + dx, y + dy);
  }
});

ipcMain.on('minimize-window', () => {
  if (win) win.hide();
});

ipcMain.on('get-window-position', (event) => {
  if (win) {
    event.returnValue = win.getPosition();
  }
});

app.whenReady().then(() => {
  createWindow();
  createTrayIcon();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  isQuitting = true;
});

app.on('activate', () => {
  if (win === null) {
    createWindow();
  } else {
    win.show();
  }
});
