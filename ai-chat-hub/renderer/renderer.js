let config = null;
let activeId = null;
const webviews = new Map();

const $ = (sel) => document.querySelector(sel);
const serviceList = $('#service-list');
const viewsEl = $('#views');

// Script injetado quando "Enter envia" está DESLIGADO: Enter passa a criar
// nova linha e Ctrl+Enter envia (repassa o Enter original sem interceptar).
const ENTER_NEWLINE_SCRIPT = `
  if (!window.__aiHubEnterPatched) {
    window.__aiHubEnterPatched = true;
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const t = e.target;
        const editable = t && (t.isContentEditable || t.tagName === 'TEXTAREA' || t.tagName === 'INPUT');
        if (editable && t.tagName !== 'INPUT') {
          e.preventDefault();
          e.stopImmediatePropagation();
          document.execCommand('insertLineBreak');
        }
      }
    }, true);
  }
`;

function enabledServices() {
  return config.services.filter((s) => s.enabled !== false);
}

function applyTheme() {
  document.body.classList.toggle('light', config.settings.theme === 'light');
  document.body.classList.toggle('compact', !!config.settings.sidebarCompact);
  document.documentElement.style.setProperty(
    '--sidebar-width',
    (config.settings.sidebarWidth || 200) + 'px'
  );
}

function renderSidebar() {
  serviceList.innerHTML = '';
  for (const svc of enabledServices()) {
    const item = document.createElement('div');
    item.className = 'svc-item' + (svc.id === activeId ? ' active' : '');
    item.title = svc.name;
    const icon = document.createElement('span');
    icon.className = 'svc-icon';
    icon.textContent = svc.icon || '💬';
    const name = document.createElement('span');
    name.className = 'svc-name';
    name.textContent = svc.name;
    item.append(icon, name);
    item.addEventListener('click', () => activate(svc.id));
    serviceList.appendChild(item);
  }
}

function getWebview(svc) {
  if (webviews.has(svc.id)) return webviews.get(svc.id);
  const wv = document.createElement('webview');
  wv.setAttribute('partition', 'persist:' + svc.id);
  wv.setAttribute('allowpopups', 'true');
  wv.setAttribute('src', svc.url);
  wv.classList.add('hidden');
  wv.addEventListener('dom-ready', () => {
    wv.setZoomFactor(config.settings.zoomFactor || 1);
    if (config.settings.enterToSend === false) {
      wv.executeJavaScript(ENTER_NEWLINE_SCRIPT).catch(() => {});
    }
  });
  // Páginas de SPA: reaplicar o patch de Enter ao navegar internamente.
  wv.addEventListener('did-navigate-in-page', () => {
    if (config.settings.enterToSend === false) {
      wv.executeJavaScript(ENTER_NEWLINE_SCRIPT).catch(() => {});
    }
  });
  viewsEl.appendChild(wv);
  webviews.set(svc.id, wv);
  return wv;
}

function activate(id) {
  const svc = config.services.find((s) => s.id === id && s.enabled !== false);
  if (!svc) return;
  activeId = id;
  const wv = getWebview(svc);
  for (const [sid, view] of webviews) view.classList.toggle('hidden', sid !== id);
  renderSidebar();
  wv.focus();
}

function applySettingsToViews() {
  for (const [, wv] of webviews) {
    try {
      wv.setZoomFactor(config.settings.zoomFactor || 1);
      if (config.settings.enterToSend === false) {
        wv.executeJavaScript(ENTER_NEWLINE_SCRIPT).catch(() => {});
      }
    } catch {}
  }
}

/* ------------------- Configurações ------------------- */
const dlg = $('#settings-dialog');
let draft = null;

function slugify(name) {
  const base = name.toLowerCase().normalize('NFD').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'servico';
  let id = base, n = 2;
  while (draft.services.some((s) => s.id === id)) id = base + '-' + n++;
  return id;
}

function renderServiceEditor() {
  const box = $('#svc-editor');
  box.innerHTML = '';
  draft.services.forEach((svc, i) => {
    const row = document.createElement('div');
    row.className = 'svc-row' + (svc.enabled === false ? ' disabled' : '');

    const icon = document.createElement('input');
    icon.type = 'text';
    icon.value = svc.icon || '';
    icon.maxLength = 4;
    icon.addEventListener('input', () => (svc.icon = icon.value));

    const name = document.createElement('input');
    name.type = 'text';
    name.value = svc.name;
    name.placeholder = 'Nome';
    name.addEventListener('input', () => (svc.name = name.value));

    const url = document.createElement('input');
    url.type = 'text';
    url.value = svc.url;
    url.placeholder = 'https://...';
    url.addEventListener('input', () => (svc.url = url.value));

    const btns = document.createElement('div');
    btns.className = 'row-btns';
    const mk = (label, title, fn) => {
      const b = document.createElement('button');
      b.textContent = label;
      b.title = title;
      b.addEventListener('click', fn);
      btns.appendChild(b);
    };
    mk(svc.enabled === false ? '◻' : '☑', 'Ativar/desativar', () => {
      svc.enabled = svc.enabled === false;
      renderServiceEditor();
    });
    mk('↑', 'Mover para cima', () => {
      if (i > 0) {
        [draft.services[i - 1], draft.services[i]] = [draft.services[i], draft.services[i - 1]];
        renderServiceEditor();
      }
    });
    mk('↓', 'Mover para baixo', () => {
      if (i < draft.services.length - 1) {
        [draft.services[i + 1], draft.services[i]] = [draft.services[i], draft.services[i + 1]];
        renderServiceEditor();
      }
    });
    mk('Sair', 'Apagar login/sessão deste serviço', async () => {
      if (confirm(`Apagar o login salvo de "${svc.name}"?`)) {
        await window.api.clearSession(svc.id);
        const wv = webviews.get(svc.id);
        if (wv) wv.reload();
      }
    });
    mk('🗑', 'Remover serviço', () => {
      if (confirm(`Remover "${svc.name}" da lista?`)) {
        draft.services.splice(i, 1);
        renderServiceEditor();
      }
    });

    row.append(icon, name, url, btns);
    box.appendChild(row);
  });

  const startup = $('#set-startup');
  startup.innerHTML = '';
  for (const s of draft.services) {
    const opt = document.createElement('option');
    opt.value = s.id;
    opt.textContent = s.name;
    startup.appendChild(opt);
  }
  startup.value = draft.settings.startupService || (draft.services[0] && draft.services[0].id);
}

function openSettings() {
  draft = JSON.parse(JSON.stringify(config));
  $('#set-theme').value = draft.settings.theme || 'dark';
  $('#set-zoom').value = draft.settings.zoomFactor || 1;
  $('#set-enter').checked = draft.settings.enterToSend !== false;
  $('#set-spell').checked = draft.settings.spellcheck !== false;
  $('#set-external').checked = draft.settings.openLinksExternally !== false;
  $('#set-compact').checked = !!draft.settings.sidebarCompact;
  $('#set-ua').value = draft.settings.userAgent || '';
  renderServiceEditor();
  dlg.showModal();
}

$('#btn-add-svc').addEventListener('click', () => {
  draft.services.push({
    id: slugify('servico-' + (draft.services.length + 1)),
    name: 'Novo serviço',
    url: 'https://',
    icon: '💬',
    enabled: true,
  });
  renderServiceEditor();
});

$('#btn-save').addEventListener('click', async () => {
  draft.settings.theme = $('#set-theme').value;
  draft.settings.zoomFactor = parseFloat($('#set-zoom').value) || 1;
  draft.settings.enterToSend = $('#set-enter').checked;
  draft.settings.spellcheck = $('#set-spell').checked;
  draft.settings.openLinksExternally = $('#set-external').checked;
  draft.settings.sidebarCompact = $('#set-compact').checked;
  draft.settings.userAgent = $('#set-ua').value.trim();
  draft.settings.startupService = $('#set-startup').value;
  draft.services = draft.services.filter((s) => s.name.trim() && s.url.trim().startsWith('http'));

  config = draft;
  await window.api.saveConfig(config);
  dlg.close();
  applyTheme();
  renderSidebar();
  applySettingsToViews();
  if (!enabledServices().some((s) => s.id === activeId) && enabledServices()[0]) {
    activate(enabledServices()[0].id);
  }
});

$('#btn-cancel').addEventListener('click', () => dlg.close());
$('#btn-reset').addEventListener('click', async () => {
  if (confirm('Restaurar todas as configurações padrão? (logins são mantidos)')) {
    config = await window.api.resetConfig();
    dlg.close();
    applyTheme();
    renderSidebar();
    applySettingsToViews();
  }
});

$('#btn-settings').addEventListener('click', openSettings);
$('#btn-reload').addEventListener('click', () => {
  const wv = webviews.get(activeId);
  if (wv) wv.reload();
});

/* ------------------- Atalhos ------------------- */
window.addEventListener('keydown', (e) => {
  if (!(e.ctrlKey || e.metaKey)) return;
  if (e.key >= '1' && e.key <= '9') {
    const svc = enabledServices()[parseInt(e.key, 10) - 1];
    if (svc) activate(svc.id);
  } else if (e.key === 'r') {
    const wv = webviews.get(activeId);
    if (wv) { wv.reload(); e.preventDefault(); }
  } else if (e.key === ',') {
    openSettings();
  } else if (e.key === '=' || e.key === '+') {
    config.settings.zoomFactor = Math.min(2, (config.settings.zoomFactor || 1) + 0.1);
    window.api.saveConfig(config);
    applySettingsToViews();
  } else if (e.key === '-') {
    config.settings.zoomFactor = Math.max(0.5, (config.settings.zoomFactor || 1) - 0.1);
    window.api.saveConfig(config);
    applySettingsToViews();
  }
});

/* ------------------- Início ------------------- */
(async () => {
  config = await window.api.getConfig();
  applyTheme();
  renderSidebar();
  const first =
    enabledServices().find((s) => s.id === config.settings.startupService) || enabledServices()[0];
  if (first) activate(first.id);
})();
