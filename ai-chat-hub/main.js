const { app, BrowserWindow, ipcMain, shell, session, Menu } = require('electron');
const path = require('path');
const fs = require('fs');

const CONFIG_PATH = () => path.join(app.getPath('userData'), 'config.json');
const DEFAULTS_PATH = path.join(__dirname, 'default-services.json');

// User-agent de um Chrome comum: necessário para o login do Google funcionar
// dentro do app (sem isso o Google bloqueia com "navegador não seguro").
const CHROME_UA =
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';

// Domínios de autenticação que devem abrir em janela popup dentro do app
// (fluxos OAuth), em vez de irem para o navegador externo.
const AUTH_HOSTS = [
  'accounts.google.com',
  'accounts.youtube.com',
  'login.microsoftonline.com',
  'login.live.com',
  'login.microsoft.com',
  'appleid.apple.com',
  'github.com',
  'auth0.com',
  'okta.com',
  'clerk.',
  'auth.openai.com',
  'auth0.openai.com',
  'claude.ai',
  'anthropic.com',
];

function loadConfig() {
  const defaults = JSON.parse(fs.readFileSync(DEFAULTS_PATH, 'utf8'));
  try {
    const saved = JSON.parse(fs.readFileSync(CONFIG_PATH(), 'utf8'));
    return {
      services: saved.services || defaults.services,
      settings: { ...defaults.settings, ...(saved.settings || {}) },
    };
  } catch {
    return defaults;
  }
}

function saveConfig(config) {
  fs.mkdirSync(path.dirname(CONFIG_PATH()), { recursive: true });
  fs.writeFileSync(CONFIG_PATH(), JSON.stringify(config, null, 2));
}

function effectiveUA() {
  const cfg = loadConfig();
  return (cfg.settings.userAgent || '').trim() || CHROME_UA;
}

function isAuthUrl(url) {
  try {
    const host = new URL(url).host;
    return AUTH_HOSTS.some((h) => host === h || host.endsWith('.' + h) || host.includes(h));
  } catch {
    return false;
  }
}

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 850,
    minWidth: 800,
    minHeight: 500,
    backgroundColor: '#1e1e2e',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webviewTag: true,
      spellcheck: true,
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

app.userAgentFallback = CHROME_UA;

app.on('web-contents-created', (_event, contents) => {
  if (contents.getType() === 'webview') {
    contents.setUserAgent(effectiveUA());

    const cfg = loadConfig();
    const langs = cfg.settings.spellcheckLanguages || ['pt-BR', 'en-US'];
    try {
      contents.session.setSpellCheckerLanguages(langs);
      contents.session.setSpellCheckerEnabled(cfg.settings.spellcheck !== false);
    } catch {}

    contents.setWindowOpenHandler(({ url }) => {
      // Popups de login (Google, Microsoft etc.) abrem dentro do app,
      // na mesma sessão, para o OAuth completar. O resto vai para o navegador.
      if (isAuthUrl(url)) {
        return {
          action: 'allow',
          overrideBrowserWindowOptions: {
            width: 520,
            height: 720,
            autoHideMenuBar: true,
            webPreferences: { session: contents.session },
          },
        };
      }
      const openExternal = loadConfig().settings.openLinksExternally !== false;
      if (openExternal) {
        shell.openExternal(url);
        return { action: 'deny' };
      }
      return { action: 'allow' };
    });

    // Menu de contexto com correção ortográfica e copiar/colar.
    contents.on('context-menu', (_e, params) => {
      const template = [];
      for (const suggestion of params.dictionarySuggestions || []) {
        template.push({ label: suggestion, click: () => contents.replaceMisspelling(suggestion) });
      }
      if (template.length) template.push({ type: 'separator' });
      template.push(
        { role: 'cut', label: 'Recortar' },
        { role: 'copy', label: 'Copiar' },
        { role: 'paste', label: 'Colar' },
        { role: 'selectAll', label: 'Selecionar tudo' }
      );
      Menu.buildFromTemplate(template).popup();
    });
  } else {
    // Janelas popup (OAuth) também precisam do UA de Chrome.
    contents.setUserAgent(effectiveUA());
  }
});

ipcMain.handle('config:get', () => loadConfig());
ipcMain.handle('config:save', (_e, config) => {
  saveConfig(config);
  return true;
});
ipcMain.handle('config:reset', () => {
  try { fs.unlinkSync(CONFIG_PATH()); } catch {}
  return loadConfig();
});
ipcMain.handle('service:clear-session', async (_e, serviceId) => {
  const ses = session.fromPartition('persist:' + serviceId);
  await ses.clearStorageData();
  await ses.clearCache();
  return true;
});
ipcMain.handle('app:user-agent', () => effectiveUA());

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
