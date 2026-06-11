const $ = (s) => document.querySelector(s);
let tools = {};
const taskEls = new Map(); // id -> element

/* ---------------- abas ---------------- */
document.querySelectorAll('.tab').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((b) => b.classList.toggle('active', b === btn));
    document.querySelectorAll('.panel').forEach((p) =>
      p.classList.toggle('active', p.id === 'tab-' + btn.dataset.tab)
    );
  });
});

/* ---------------- avisos de dependências ---------------- */
function warn(el, msg) {
  el.innerHTML = msg;
  el.classList.remove('hidden');
}

async function checkTools() {
  tools = await window.api.checkTools();
  if (!tools.tesseract) {
    warn($('#ocr-warn'), 'OCR indisponível — instale com: <code>sudo pacman -S tesseract tesseract-data-por tesseract-data-eng</code>');
  } else if (!tools._screenshot) {
    warn($('#ocr-warn'), 'Nenhuma ferramenta de captura encontrada — instale <code>spectacle</code> (KDE) ou <code>grim slurp</code> (Wayland).');
  }
  if (!tools.ffmpeg || !tools._magick) {
    const missing = [!tools.ffmpeg && 'ffmpeg', !tools._magick && 'imagemagick'].filter(Boolean).join(' ');
    warn($('#conv-warn'), `Para converter tudo, instale: <code>sudo pacman -S ${missing}</code>`);
  }
  if (!tools['yt-dlp']) {
    warn($('#dl-warn'), 'Baixador indisponível — instale com: <code>sudo pacman -S yt-dlp</code>');
  }
}

/* ---------------- fila de tarefas (comum) ---------------- */
function addTask(queueEl, name, id) {
  const el = document.createElement('div');
  el.className = 'task';
  el.innerHTML = `
    <div class="t-name"></div>
    <div class="t-actions">
      <button class="t-cancel">Cancelar</button>
      <button class="t-show hidden">📁 Mostrar</button>
    </div>
    <progress max="100" value="0"></progress>
    <div class="t-sub">Na fila…</div>`;
  el.querySelector('.t-name').textContent = name;
  el.querySelector('.t-cancel').addEventListener('click', () => window.api.cancelTask(id));
  queueEl.prepend(el);
  taskEls.set(id, el);
  return el;
}

window.api.onProgress(({ id, pct }) => {
  const el = taskEls.get(id);
  if (!el) return;
  el.querySelector('progress').value = pct;
  el.querySelector('.t-sub').textContent = pct.toFixed(1) + '%';
});

window.api.onLabel(({ id, label }) => {
  const el = taskEls.get(id);
  if (el) el.querySelector('.t-name').textContent = label;
});

window.api.onDone(({ id, ok, out, error }) => {
  const el = taskEls.get(id);
  if (!el) return;
  el.classList.add(ok ? 'ok' : 'err');
  el.querySelector('progress').value = ok ? 100 : 0;
  el.querySelector('.t-sub').textContent = ok ? 'Concluído ✓' : 'Erro: ' + (error || 'falhou');
  el.querySelector('.t-cancel').classList.add('hidden');
  if (ok && out) {
    const show = el.querySelector('.t-show');
    show.classList.remove('hidden');
    show.addEventListener('click', () => window.api.showInFolder(out));
  }
});

/* ---------------- OCR ---------------- */
async function doCapture() {
  $('#ocr-status').textContent = 'Selecione a área da tela…';
  const r = await window.api.ocrCapture();
  if (r.ok) {
    $('#ocr-text').value = r.text;
    $('#ocr-status').textContent = r.text ? 'Texto reconhecido ✓' : 'Nenhum texto encontrado na imagem.';
  } else {
    $('#ocr-status').textContent = r.error;
  }
}

$('#ocr-capture').addEventListener('click', doCapture);
window.api.onOcrTrigger(doCapture);

$('#ocr-open').addEventListener('click', async () => {
  const files = await window.api.pickFiles([{ name: 'Imagens', extensions: ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff'] }]);
  if (files[0]) {
    $('#ocr-status').textContent = 'Reconhecendo…';
    const r = await window.api.ocrFile(files[0]);
    $('#ocr-text').value = r.ok ? r.text : '';
    $('#ocr-status').textContent = r.ok ? 'Texto reconhecido ✓' : r.error;
  }
});

$('#ocr-copy').addEventListener('click', async () => {
  await window.api.copyText($('#ocr-text').value);
  $('#ocr-status').textContent = 'Copiado para a área de transferência ✓';
});

$('#ocr-ai').addEventListener('click', async () => {
  await window.api.copyText($('#ocr-text').value);
  const opened = await window.api.openAiChatHub();
  $('#ocr-status').textContent = opened
    ? 'Copiado ✓ — cole no chat com Ctrl+V'
    : 'Copiado ✓ — AI Chat Hub não está instalado';
});

// arrastar imagem para a aba de OCR
const ocrPanel = $('#tab-ocr');
ocrPanel.addEventListener('dragover', (e) => e.preventDefault());
ocrPanel.addEventListener('drop', async (e) => {
  e.preventDefault();
  const f = e.dataTransfer.files[0];
  if (!f) return;
  $('#ocr-status').textContent = 'Reconhecendo…';
  const r = await window.api.ocrFile(window.api.pathForFile(f));
  $('#ocr-text').value = r.ok ? r.text : '';
  $('#ocr-status').textContent = r.ok ? 'Texto reconhecido ✓' : r.error;
});

/* ---------------- Conversor ---------------- */
const FORMATS = {
  image: ['png', 'jpg', 'webp', 'avif', 'gif', 'bmp', 'ico', 'pdf'],
  audio: ['mp3', 'ogg', 'flac', 'wav', 'opus', 'm4a'],
  video: ['mp4', 'mkv', 'webm', 'gif', 'mp3', 'ogg', 'wav'],
};

async function offerConversion(filePath) {
  const cat = await window.api.convertCategory(filePath);
  const name = filePath.split('/').pop();
  if (!cat) {
    const el = document.createElement('div');
    el.className = 'task err';
    el.innerHTML = `<div class="t-name"></div><div></div><div class="t-sub">Formato não suportado</div>`;
    el.querySelector('.t-name').textContent = name;
    $('#conv-queue').prepend(el);
    return;
  }
  const ext = name.split('.').pop().toLowerCase();
  const el = document.createElement('div');
  el.className = 'task';
  el.innerHTML = `
    <div class="t-name"></div>
    <div class="t-actions">
      <select class="fmt"></select>
      <button class="go primary">Converter</button>
    </div>
    <progress max="100" value="0"></progress>
    <div class="t-sub">Escolha o formato de saída</div>`;
  el.querySelector('.t-name').textContent = name;
  const sel = el.querySelector('.fmt');
  for (const f of FORMATS[cat].filter((f) => f !== ext)) {
    const o = document.createElement('option');
    o.value = f;
    o.textContent = ext.toUpperCase() + ' → ' + f.toUpperCase();
    sel.appendChild(o);
  }
  el.querySelector('.go').addEventListener('click', async () => {
    const r = await window.api.convertStart({ file: filePath, format: sel.value });
    if (!r.ok) {
      el.classList.add('err');
      el.querySelector('.t-sub').textContent = r.error;
      return;
    }
    el.querySelector('.t-actions').innerHTML =
      '<button class="t-cancel">Cancelar</button><button class="t-show hidden">📁 Mostrar</button>';
    el.querySelector('.t-cancel').addEventListener('click', () => window.api.cancelTask(r.id));
    el.querySelector('.t-sub').textContent = 'Convertendo…';
    taskEls.set(r.id, el);
  });
  $('#conv-queue').prepend(el);
}

const dz = $('#dropzone');
dz.addEventListener('dragover', (e) => {
  e.preventDefault();
  dz.classList.add('drag');
});
dz.addEventListener('dragleave', () => dz.classList.remove('drag'));
dz.addEventListener('drop', (e) => {
  e.preventDefault();
  dz.classList.remove('drag');
  for (const f of e.dataTransfer.files) offerConversion(window.api.pathForFile(f));
});
$('#conv-pick').addEventListener('click', async () => {
  const files = await window.api.pickFiles([]);
  for (const f of files) offerConversion(f);
});

/* ---------------- Baixador ---------------- */
let dlDir = null;
(async () => {
  dlDir = await window.api.downloadsDir();
})();

$('#dl-dir-btn').addEventListener('click', async () => {
  const d = await window.api.pickDir();
  if (d) {
    dlDir = d;
    $('#dl-dir-label').textContent = d.split('/').pop() || d;
  }
});

async function startDownload() {
  const url = $('#dl-url').value.trim();
  if (!url.startsWith('http')) return;
  const r = await window.api.downloadStart({
    url,
    mode: $('#dl-mode').value,
    dir: dlDir,
    playlist: $('#dl-playlist').checked,
  });
  if (!r.ok) {
    warn($('#dl-warn'), r.error);
    return;
  }
  addTask($('#dl-queue'), url, r.id).querySelector('.t-sub').textContent = 'Iniciando…';
  $('#dl-url').value = '';
}

$('#dl-start').addEventListener('click', startDownload);
$('#dl-url').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') startDownload();
});

checkTools();
