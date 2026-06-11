const { app, BrowserWindow, ipcMain, shell, clipboard, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execFile } = require('child_process');

let mainWindow;
const tasks = new Map(); // id -> child process
let nextTaskId = 1;

/* ---------------- util ---------------- */

function which(cmd) {
  return new Promise((resolve) => {
    execFile('which', [cmd], (err, out) => resolve(err ? null : out.trim()));
  });
}

function run(cmd, args, opts = {}) {
  return new Promise((resolve) => {
    execFile(cmd, args, { maxBuffer: 64 * 1024 * 1024, ...opts }, (err, stdout, stderr) =>
      resolve({ ok: !err, stdout: stdout || '', stderr: stderr || '', err })
    );
  });
}

function send(channel, payload) {
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send(channel, payload);
}

/* ---------------- janela ---------------- */

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 980,
    height: 720,
    minWidth: 720,
    minHeight: 520,
    backgroundColor: '#1e1e2e',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', (_e, argv) => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
      // "garuda-toolbox --ocr" (ex.: atalho global do KDE) dispara a captura
      if (argv.includes('--ocr')) send('ocr:trigger', {});
    }
  });

  app.whenReady().then(() => {
    createWindow();
    if (process.argv.includes('--ocr')) {
      mainWindow.webContents.once('did-finish-load', () => send('ocr:trigger', {}));
    }
  });

  app.on('window-all-closed', () => app.quit());
}

/* ---------------- detecção de ferramentas ---------------- */

ipcMain.handle('tools:check', async () => {
  const names = ['tesseract', 'ffmpeg', 'ffprobe', 'yt-dlp', 'magick', 'convert',
                 'spectacle', 'grim', 'slurp', 'maim', 'scrot', 'ai-chat-hub'];
  const found = {};
  await Promise.all(names.map(async (n) => (found[n] = !!(await which(n)))));
  found._screenshot = found.spectacle || (found.grim && found.slurp) || found.maim || found.scrot;
  found._magick = found.magick || found.convert;
  return found;
});

/* ---------------- OCR ---------------- */

async function captureRegion() {
  const out = path.join(os.tmpdir(), `toolbox-shot-${Date.now()}.png`);
  const isWayland = !!process.env.WAYLAND_DISPLAY;
  const candidates = [];
  if (await which('spectacle')) candidates.push(['spectacle', ['-r', '-b', '-n', '-o', out]]);
  if (isWayland && (await which('grim')) && (await which('slurp'))) {
    candidates.push(['sh', ['-c', `grim -g "$(slurp)" "${out}"`]]);
  }
  if (await which('maim')) candidates.push(['maim', ['-s', out]]);
  if (await which('scrot')) candidates.push(['scrot', ['-s', '-o', out]]);
  if (!candidates.length) throw new Error('Nenhuma ferramenta de captura encontrada (spectacle, grim+slurp, maim ou scrot).');

  for (const [cmd, args] of candidates) {
    const r = await run(cmd, args);
    if (r.ok && fs.existsSync(out) && fs.statSync(out).size > 0) return out;
  }
  throw new Error('Captura cancelada ou falhou.');
}

async function ocrFile(imagePath) {
  if (!(await which('tesseract'))) {
    throw new Error('Tesseract não instalado. Rode: sudo pacman -S tesseract tesseract-data-por tesseract-data-eng');
  }
  let r = await run('tesseract', [imagePath, 'stdout', '-l', 'por+eng']);
  if (!r.ok) r = await run('tesseract', [imagePath, 'stdout']); // sem dados de idioma pt
  if (!r.ok) throw new Error('OCR falhou: ' + r.stderr.split('\n')[0]);
  return r.stdout.trim();
}

ipcMain.handle('ocr:capture', async () => {
  mainWindow.hide();
  await new Promise((res) => setTimeout(res, 350)); // tempo da janela sumir
  try {
    const img = await captureRegion();
    const text = await ocrFile(img);
    fs.unlink(img, () => {});
    return { ok: true, text };
  } catch (e) {
    return { ok: false, error: e.message };
  } finally {
    mainWindow.show();
    mainWindow.focus();
  }
});

ipcMain.handle('ocr:file', async (_e, filePath) => {
  try {
    return { ok: true, text: await ocrFile(filePath) };
  } catch (e) {
    return { ok: false, error: e.message };
  }
});

ipcMain.handle('clipboard:write', (_e, text) => {
  clipboard.writeText(text || '');
  return true;
});

ipcMain.handle('open:aichathub', async () => {
  if (await which('ai-chat-hub')) {
    spawn('ai-chat-hub', [], { detached: true, stdio: 'ignore' }).unref();
    return true;
  }
  return false;
});

/* ---------------- Conversor ---------------- */

const IMG_EXT = ['png', 'jpg', 'jpeg', 'webp', 'avif', 'bmp', 'tiff', 'tif', 'gif', 'svg', 'ico', 'heic'];
const AUD_EXT = ['mp3', 'wav', 'flac', 'ogg', 'opus', 'm4a', 'aac', 'wma'];
const VID_EXT = ['mp4', 'mkv', 'webm', 'avi', 'mov', 'flv', 'wmv', 'mpg', 'mpeg', 'ts', 'm4v'];

function mediaCategory(file) {
  const ext = path.extname(file).slice(1).toLowerCase();
  if (IMG_EXT.includes(ext)) return 'image';
  if (AUD_EXT.includes(ext)) return 'audio';
  if (VID_EXT.includes(ext)) return 'video';
  return null;
}

ipcMain.handle('convert:category', (_e, file) => mediaCategory(file));

async function probeDuration(file) {
  const r = await run('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', file]);
  const d = parseFloat(r.stdout);
  return isNaN(d) ? 0 : d;
}

ipcMain.handle('convert:start', async (_e, { file, format }) => {
  const id = nextTaskId++;
  const cat = mediaCategory(file);
  const base = file.replace(/\.[^.]+$/, '');
  let out = `${base}.${format}`;
  let n = 2;
  while (fs.existsSync(out)) out = `${base}-${n++}.${format}`;

  if (cat === 'image' && !['mp4', 'webm'].includes(format)) {
    const magick = (await which('magick')) ? 'magick' : (await which('convert')) ? 'convert' : null;
    if (!magick) return { ok: false, error: 'ImageMagick não instalado: sudo pacman -S imagemagick' };
    const child = spawn(magick, [file, out]);
    tasks.set(id, child);
    child.on('close', (code) => {
      tasks.delete(id);
      send('task:done', { id, ok: code === 0, out, error: code === 0 ? null : 'Conversão falhou' });
    });
    return { ok: true, id, out };
  }

  if (!(await which('ffmpeg'))) return { ok: false, error: 'ffmpeg não instalado: sudo pacman -S ffmpeg' };
  const duration = await probeDuration(file);
  const child = spawn('ffmpeg', ['-y', '-i', file, '-progress', 'pipe:1', '-loglevel', 'error', out]);
  tasks.set(id, child);
  let errBuf = '';
  child.stderr.on('data', (d) => (errBuf += d));
  child.stdout.on('data', (d) => {
    const m = String(d).match(/out_time_ms=(\d+)/);
    if (m && duration > 0) {
      const pct = Math.min(99, (parseInt(m[1], 10) / 1e6 / duration) * 100);
      send('task:progress', { id, pct });
    }
  });
  child.on('close', (code) => {
    tasks.delete(id);
    send('task:done', { id, ok: code === 0, out, error: code === 0 ? null : errBuf.split('\n')[0] || 'Conversão falhou' });
  });
  return { ok: true, id, out };
});

/* ---------------- Baixador (yt-dlp) ---------------- */

ipcMain.handle('download:start', async (_e, { url, mode, dir, playlist }) => {
  if (!(await which('yt-dlp'))) return { ok: false, error: 'yt-dlp não instalado: sudo pacman -S yt-dlp' };
  const id = nextTaskId++;
  const args = ['--newline', '-o', path.join(dir, '%(title)s.%(ext)s')];
  if (!playlist) args.push('--no-playlist');
  if (mode === 'audio') args.push('-x', '--audio-format', 'mp3');
  else if (mode === '1080') args.push('-f', 'bv*[height<=1080]+ba/b[height<=1080]');
  else if (mode === '720') args.push('-f', 'bv*[height<=720]+ba/b[height<=720]');
  else args.push('-f', 'bv*+ba/b');
  args.push(url);

  const child = spawn('yt-dlp', args);
  tasks.set(id, child);
  let errBuf = '';
  let lastFile = '';
  const onLine = (line) => {
    const dest = line.match(/\[download\] Destination: (.+)/) || line.match(/Merging formats into "(.+)"/);
    if (dest) {
      lastFile = dest[1].replace(/"$/, '');
      send('task:label', { id, label: path.basename(lastFile) });
    }
    const pct = line.match(/\[download\]\s+([\d.]+)%/);
    if (pct) send('task:progress', { id, pct: parseFloat(pct[1]) });
  };
  child.stdout.on('data', (d) => String(d).split('\n').forEach(onLine));
  child.stderr.on('data', (d) => (errBuf += d));
  child.on('close', (code) => {
    tasks.delete(id);
    send('task:done', {
      id,
      ok: code === 0,
      out: lastFile || dir,
      error: code === 0 ? null : (errBuf.match(/ERROR: (.+)/) || [null, 'Download falhou'])[1],
    });
  });
  return { ok: true, id };
});

/* ---------------- tarefas / arquivos ---------------- */

ipcMain.handle('task:cancel', (_e, id) => {
  const child = tasks.get(id);
  if (child) child.kill('SIGTERM');
  return true;
});

ipcMain.handle('file:show', (_e, p) => {
  shell.showItemInFolder(p);
  return true;
});

ipcMain.handle('dialog:pick-dir', async () => {
  const r = await dialog.showOpenDialog(mainWindow, { properties: ['openDirectory'] });
  return r.canceled ? null : r.filePaths[0];
});

ipcMain.handle('dialog:pick-files', async (_e, filters) => {
  const r = await dialog.showOpenDialog(mainWindow, { properties: ['openFile', 'multiSelections'], filters });
  return r.canceled ? [] : r.filePaths;
});

ipcMain.handle('os:downloads', () => path.join(os.homedir(), 'Downloads'));
