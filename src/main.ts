import { invoke, isTauri } from '@tauri-apps/api/core';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { open, save, confirm } from '@tauri-apps/plugin-dialog';
import { revealItemInDir, openUrl } from '@tauri-apps/plugin-opener';
import { t, getLocale, setLocale } from './i18n';
import { icon } from './icons';
import { getTheme, setTheme, type Theme } from './theme';
import type { View, Location, Entry, Update } from './types';
import './style.css';

const root = document.querySelector<HTMLDivElement>('#app')!;
let view: View | null = null;
let locations: Location[] = [];
let page: 'home' | 'editor' = 'home';
let busy = false;
let query = '';
let source = 'all';
let category = 'all';
let changedOnly = false;
let selectedId: number | null = null;
let pageIndex = 0;
const pageSize = 150;
let originals = new Map<number, string>();
let changedIds = new Set<number>();
let reviewing = false;
let lastBackup = '';
let pendingUpdate: Update | null = null;
let toastTimer: ReturnType<typeof setTimeout>;
const escape = (v: string | number) =>
  String(v).replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!,
  );
const basename = (path: string) => path.split(/[\\/]/).pop() ?? path;
const directory = (path: string) => path.replace(/[\\/][^\\/]*$/, '');
function readRecents(): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem('cts.recents') ?? '[]');
    return Array.isArray(value)
      ? value.filter((v): v is string => typeof v === 'string').slice(0, 5)
      : [];
  } catch {
    return [];
  }
}
function size(bytes: number) {
  return `${(bytes / 1024).toFixed(1)} KB`;
}
function section(entry: Entry) {
  return t(entry.section === 'custom' ? 'section.customVars' : 'section.metaVars');
}
function note(entry: Entry) {
  return t(entry.description || entry.note);
}
function changed(entry: Entry) {
  return changedIds.has(entry.id);
}
function acceptView(next: View) {
  view = next;
  originals = new Map(
    Object.entries(next.originalValues).map(([id, value]) => [Number(id), value]),
  );
  changedIds = new Set(next.changedIds);
}
function button(id: string, name: string, image: string, cls = '', disabled = false) {
  return `<button id="${id}" class="button ${cls}" ${disabled ? 'disabled' : ''}>${icon(image)}<span>${escape(t(name))}</span></button>`;
}
function toast(message: string, error = false) {
  clearTimeout(toastTimer);
  const el = document.querySelector<HTMLDivElement>('#toast')!;
  el.innerHTML = `${icon(error ? 'info' : 'check')}<span>${escape(message)}</span><button aria-label="${escape(t('new.dismiss'))}" id="dismiss-toast">${icon('close')}</button>`;
  el.className = `toast visible ${error ? 'error' : ''}`;
  document
    .querySelector('#dismiss-toast')
    ?.addEventListener('click', () => el.classList.remove('visible'));
  toastTimer = setTimeout(() => el.classList.remove('visible'), error ? 15000 : 6000);
}
async function action(work: () => Promise<void>) {
  if (busy) return;
  busy = true;
  root.classList.add('busy');
  root.setAttribute('aria-busy', 'true');
  try {
    await work();
  } catch (e) {
    toast(String(e), true);
  } finally {
    busy = false;
    root.classList.remove('busy');
    root.setAttribute('aria-busy', 'false');
  }
}
async function mayDiscard() {
  return (
    !view?.dirty ||
    (await confirm(t('new.discardPrompt'), {
      title: t('new.unsaved'),
      kind: 'warning',
      okLabel: t('new.discard'),
      cancelLabel: t('new.keepEditing'),
    }))
  );
}
async function load(path: string) {
  await action(async () => {
    if (!(await mayDiscard())) return;
    const loaded = await invoke<View>('open_save', { path });
    acceptView(loaded);
    reviewing = false;
    query = '';
    source = 'all';
    category = 'all';
    changedOnly = false;
    pageIndex = 0;
    selectedId = loaded.entries[0]?.id ?? null;
    page = 'editor';
    lastBackup = '';
    localStorage.setItem(
      'cts.recents',
      JSON.stringify([loaded.path, ...readRecents().filter((p) => p !== loaded.path)].slice(0, 5)),
    );
    render();
    toast(t('message.loaded'));
  });
}
async function pickFile(folder = false) {
  if (busy) return;
  const result = await open({
    directory: folder,
    multiple: false,
    title: t(folder ? 'new.selectFolder' : 'dialog.select_save'),
    ...(folder
      ? {}
      : {
          filters: [
            { name: t('dialog.cts_save'), extensions: ['gd'] },
            { name: t('dialog.all_files'), extensions: ['*'] },
          ],
        }),
  });
  if (typeof result === 'string') await load(result);
}
function bind(id: string, fn: () => void | Promise<void>) {
  document.getElementById(id)?.addEventListener('click', () => {
    Promise.resolve(fn()).catch((e) => toast(String(e), true));
  });
}
function render() {
  root.innerHTML = `<div class="app-shell">
    <aside class="rail"><a class="brand" href="#" id="brand" aria-label="CTS Save Editor">${icon('atom')}<span>CTS<span class="brand-small">SAVE EDITOR</span></span></a>
      <nav aria-label="${escape(t('new.navigation'))}"><button id="nav-home" class="nav-item ${page === 'home' ? 'active' : ''}">${icon('folder')}<span>${escape(t('new.saves'))}</span></button><button id="nav-editor" class="nav-item ${page === 'editor' ? 'active' : ''}" ${!view ? 'disabled' : ''}>${icon('edit')}<span>${escape(t('new.workspace'))}</span>${view?.dirty ? '<i class="dirty-dot"></i>' : ''}</button></nav>
      <div class="rail-bottom"><div class="theme-switch" role="group" aria-label="${escape(t('new.theme'))}">${(['light', 'dark', 'system'] as const).map((theme) => `<button data-theme="${theme}" class="${getTheme() === theme ? 'active' : ''}" title="${escape(t(`new.theme_${theme}`))}" aria-label="${escape(t(`new.theme_${theme}`))}" aria-pressed="${getTheme() === theme}">${icon(theme)}</button>`).join('')}</div><span class="version">v0.3.0</span><button class="language" id="language" aria-label="${getLocale() === 'zh-CN' ? 'Switch to English' : '切换到简体中文'}">${icon('globe')}<span>${getLocale() === 'zh-CN' ? 'English' : '简体中文'}</span></button></div>
    </aside>
    <main><header class="topbar"><span class="breadcrumb">Cell to Singularity <span>/</span> ${escape(t(page === 'home' ? 'new.saves' : 'new.workspace'))}</span><span class="local-badge"><i></i>${escape(t('new.localOnly'))}</span></header>
      <div id="content">${page === 'home' ? home() : workspace()}</div>
    </main></div><div id="toast" class="toast" role="status" aria-live="polite"></div><div id="update-slot"></div><div id="changes-slot"></div>`;
  bind('brand', () => {
    page = 'home';
    render();
  });
  bind('nav-home', () => {
    page = 'home';
    render();
  });
  bind('nav-editor', () => {
    if (view) {
      page = 'editor';
      render();
    }
  });
  bind('language', () => {
    setLocale(getLocale() === 'zh-CN' ? 'en-US' : 'zh-CN');
    render();
  });
  document.querySelectorAll<HTMLButtonElement>('button[data-theme]').forEach(
    (button) =>
      (button.onclick = () => {
        setTheme(button.dataset.theme as Theme);
        document.querySelectorAll<HTMLButtonElement>('button[data-theme]').forEach((b) => {
          b.classList.toggle('active', b === button);
          b.setAttribute('aria-pressed', String(b === button));
        });
      }),
  );
  if (page === 'home') bindHome();
  else bindWorkspace();
  renderUpdate();
  renderReview();
}
function home() {
  const found = locations.filter((l) => l.files.some((f) => f.exists)).length;
  return `<section class="home-page"><div class="page-heading"><div><p class="eyebrow">${escape(t('new.homeEyebrow'))}</p><h1>${escape(t('new.homeTitle'))}</h1><p class="muted">${escape(t('new.homeSubtitle'))}</p></div><span class="heading-count">${escape(t('new.detected', { count: found }))}</span></div>
    <section class="open-hero" id="dropzone"><div class="hero-art" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><div class="orbit orbit-three"></div><div class="nucleus">${icon('atom')}</div><span class="particle p-one"></span><span class="particle p-two"></span><span class="particle p-three"></span></div><div class="hero-content"><span class="mini-label">${escape(t('new.startHere'))}</span><h2>${escape(t('new.openTitle'))}</h2><p>${escape(t('new.openSubtitle'))}</p><div class="hero-actions">${button('open-folder', 'new.openFolder', 'folder', 'primary')}${button('open-file', 'new.chooseFile', 'file')}</div><p class="drop-hint">${escape(t('new.dropHint'))} <kbd>${navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'} O</kbd></p></div></section>
    <div class="section-heading"><h2>${escape(t('new.detectedSaves'))}</h2><button id="scan" class="text-button">${icon('refresh')}${escape(t('new.rescan'))}</button></div>
    <div class="location-grid">${locations.length ? locations.map((l, i) => `<article class="location-card"><div class="card-top"><span class="folder-icon">${icon('folder')}</span><span class="badge ${l.files.some((f) => f.exists) ? 'ready' : ''}">${escape(t(l.files.some((f) => f.exists) ? 'new.available' : 'new.notFound'))}</span></div><h3>${escape(l.label)}</h3><p class="path" title="${escape(l.path)}">${escape(l.path)}</p><div class="file-pair">${l.files.map((f) => `<div><span class="file-state ${f.exists ? 'exists' : ''}"></span><span>${escape(f.name)}</span><span>${f.exists ? size(f.size) : escape(t('new.missing'))}</span></div>`).join('')}</div><div class="card-actions"><button data-location="${i}" class="button primary" ${!l.files.some((f) => f.exists) ? 'disabled' : ''}>${escape(t('new.openSave'))}${icon('arrow')}</button><button data-reveal="${i}" class="icon-button" title="${escape(t('buttons.reveal_path'))}" aria-label="${escape(t('buttons.reveal_path'))}">${icon('folder')}</button></div>${l.files.filter((f) => f.exists).length === 2 ? `<div class="source-choice">${escape(t('new.chooseSource'))} ${l.files.map((f) => `<button data-source-path="${escape(f.path)}">${escape(f.name)}</button>`).join('')}</div>` : ''}</article>`).join('') : `<div class="no-locations">${icon('folder')}<p>${escape(t('new.noLocations'))}</p></div>`}</div>
    <div class="home-lower"><section class="recent-section"><div class="section-heading"><h2>${escape(t('new.recent'))}</h2><button class="text-button" id="clear-recents">${escape(t('new.clearHistory'))}</button></div>${
      readRecents().length
        ? readRecents()
            .map(
              (p, i) =>
                `<button class="recent-row" data-recent="${i}">${icon('file')}<span><strong>${escape(basename(p))}</strong><small>${escape(directory(p))}</small></span>${icon('arrow')}</button>`,
            )
            .join('')
        : `<p class="empty-recent">${escape(t('new.noRecent'))}</p>`
    }</section><aside class="save-tip">${icon('shield')}<h3>${escape(t('new.pairTitle'))}</h3><p>${escape(t('new.pairTip'))}</p><span>${escape(t('new.backupTip'))}</span></aside></div>
    <details class="manual-path"><summary>${escape(t('new.manualPath'))}</summary><form id="path-form"><input id="path-input" aria-label="${escape(t('new.pathLabel'))}" placeholder="${escape(t('new.pathPlaceholder'))}" required><button class="button" type="submit">${escape(t('buttons.open'))}${icon('arrow')}</button></form></details>
    <label class="autoload-setting"><input id="autoload" type="checkbox" ${localStorage.getItem('cts.autoload') === 'true' ? 'checked' : ''}>${escape(t('new.autoload'))}</label>
    ${view ? `<button id="resume" class="button resume">${icon('back')}${escape(t('new.resume'))} · ${escape(basename(view.path))}</button>` : ''}
  </section>`;
}
function bindHome() {
  bind('open-folder', () => pickFile(true));
  bind('open-file', () => pickFile());
  bind('scan', () =>
    action(async () => {
      locations = await invoke<Location[]>('discover_saves');
      render();
    }),
  );
  bind('clear-recents', () => {
    localStorage.removeItem('cts.recents');
    render();
  });
  bind('resume', () => {
    page = 'editor';
    render();
  });
  document.querySelector<HTMLInputElement>('#autoload')!.onchange = (e) =>
    localStorage.setItem('cts.autoload', String((e.target as HTMLInputElement).checked));
  document.querySelectorAll<HTMLButtonElement>('[data-location]').forEach(
    (b) =>
      (b.onclick = () => {
        void load(locations[Number(b.dataset.location)].path);
      }),
  );
  document.querySelectorAll<HTMLButtonElement>('[data-source-path]').forEach(
    (b) =>
      (b.onclick = () => {
        void load(b.dataset.sourcePath!);
      }),
  );
  document.querySelectorAll<HTMLButtonElement>('[data-recent]').forEach(
    (b) =>
      (b.onclick = () => {
        void load(readRecents()[Number(b.dataset.recent)]);
      }),
  );
  document.querySelectorAll<HTMLButtonElement>('[data-reveal]').forEach(
    (b) =>
      (b.onclick = () => {
        void revealItemInDir(locations[Number(b.dataset.reveal)].path).catch((e) =>
          toast(String(e), true),
        );
      }),
  );
  document.querySelector('#path-form')?.addEventListener('submit', (e) => {
    e.preventDefault();
    void load(document.querySelector<HTMLInputElement>('#path-input')!.value.trim());
  });
}
function workspace() {
  if (!view) return '';
  const counts = new Map<string, number>();
  view.entries.forEach((e) => counts.set(e.category, (counts.get(e.category) ?? 0) + 1));
  const custom = view.entries.filter((e) => e.section === 'custom').length;
  const changes = view.entries.filter(changed).length;
  return `<section class="editor-page"><div class="editor-heading"><div><p class="eyebrow">${escape(t('new.saveWorkspace'))}</p><h1>${escape(basename(view.path))}<span class="badge ${view.dirty ? 'pending' : 'ready'}">${escape(t(view.dirty ? 'new.unsaved' : 'new.saved'))}</span></h1><button id="reveal-current" class="path path-button" title="${escape(view.path)}">${escape(directory(view.path))}${icon('folder')}</button></div><div class="editor-actions">${button('undo', 'new.undo', 'undo', '', !view.canUndo)}${button('redo', 'new.redo', 'redo', '', !view.canRedo)}${button('backup', 'buttons.backup', 'shield')}${button('reload', 'buttons.reload', 'refresh')}${button('save-as', 'buttons.save_as', 'download')}${button('save', view.files.length > 1 ? 'new.saveBoth' : 'buttons.save_in_place', 'save', 'primary')}</div></div>
    <div class="save-strip"><span>${icon('file')}${view.files.map((f) => `<span class="paired-name">${escape(f.name)}${!f.exists ? `<small>${escape(t('new.willCreate'))}</small>` : ''}</span>`).join('<span class="pair-plus">+</span>')}</span><span>${icon('shield')}${escape(t('new.automaticBackup'))}</span></div>
    ${view.diverged ? `<div class="notice">${icon('info')}<span>${escape(t('new.diverged', { name: basename(view.path) }))}</span></div>` : ''}
    <div class="editor-layout"><aside class="categories"><h2>${escape(t('filters.category'))}</h2><button class="category-button ${category === 'all' ? 'active' : ''}" data-category="all"><span>${escape(t('new.allVariables'))}</span><span>${view.entries.length}</span></button>${Array.from(
      counts,
    )
      .sort(([a], [b]) => t(a).localeCompare(t(b)))
      .map(
        ([c, count]) =>
          `<button class="category-button ${category === c ? 'active' : ''}" data-category="${escape(c)}"><span>${escape(t(c))}</span><span>${count}</span></button>`,
      )
      .join(
        '',
      )}<div class="category-footer"><span>${custom} ${escape(t('dashboard.string_items'))}</span><span>${view.entries.length - custom} ${escape(t('dashboard.numeric_items'))}</span></div></aside>
      <section class="variables"><div class="filter-bar"><label class="search-field">${icon('search')}<input id="search" value="${escape(query)}" placeholder="${escape(t('new.searchPlaceholder'))}" aria-label="${escape(t('filters.search'))}"><kbd>${navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'} F</kbd></label><button id="clear-filters" class="icon-button" title="${escape(t('buttons.clear_filter'))}" aria-label="${escape(t('buttons.clear_filter'))}">${icon('close')}</button></div><div class="table-toolbar"><div class="source-tabs" role="group" aria-label="${escape(t('filters.source'))}">${['all', 'custom', 'meta'].map((s) => `<button data-section="${s}" class="${source === s ? 'active' : ''}">${escape(t(s === 'all' ? 'section.all' : s === 'custom' ? 'section.customVars' : 'section.metaVars'))}</button>`).join('')}</div><label class="changes-toggle"><input id="changes-only" type="checkbox" ${changedOnly ? 'checked' : ''}>${escape(t('new.changes'))}<span id="changes-count">${changes}</span></label></div><div class="table-scroll"><table><thead><tr><th>${escape(t('filters.column_key'))}</th><th>${escape(t('filters.column_source'))}</th><th>${escape(t('filters.column_value'))}</th></tr></thead><tbody id="rows"></tbody></table><div id="empty-filter" class="empty-filter" hidden>${icon('search')}<h3>${escape(t('new.noResults'))}</h3><p>${escape(t('new.tryAnotherFilter'))}</p></div></div><footer class="table-footer"><span id="item-count"></span><div><button id="previous-page" class="icon-button" aria-label="${escape(t('new.previous'))}">${icon('back')}</button><span id="page-count"></span><button id="next-page" class="icon-button" aria-label="${escape(t('new.next'))}">${icon('arrow')}</button></div></footer></section>
      <aside id="inspector" class="inspector"></aside>
    </div><div class="workspace-footer">${button('review-changes', 'new.reviewChanges', 'changes', '', changes === 0)}<span>${icon('info')}${escape(t('new.editHint'))}</span><button class="text-button" id="show-backup" ${!lastBackup ? 'disabled' : ''}>${escape(t('new.showBackup'))}${icon('arrow')}</button></div>
  </section>`;
}
function filtered() {
  const q = query.trim().toLocaleLowerCase();
  return (
    view?.entries.filter(
      (e) =>
        (source === 'all' || e.section === source) &&
        (category === 'all' || e.category === category) &&
        (!changedOnly || changed(e)) &&
        (!q ||
          [e.section, section(e), e.key, e.value, t(e.category), note(e)]
            .join('\n')
            .toLocaleLowerCase()
            .includes(q)),
    ) ?? []
  );
}
function renderRows() {
  const entries = filtered();
  const pages = Math.max(1, Math.ceil(entries.length / pageSize));
  pageIndex = Math.min(pageIndex, pages - 1);
  const visible = entries.slice(pageIndex * pageSize, (pageIndex + 1) * pageSize);
  const previous = selectedId;
  if (!visible.some((entry) => entry.id === selectedId)) selectedId = visible[0]?.id ?? null;
  document.querySelector('#rows')!.innerHTML = visible
    .map(
      (e) =>
        `<tr tabindex="0" data-id="${e.id}" class="${selectedId === e.id ? 'selected' : ''} ${changed(e) ? 'changed' : ''}" aria-selected="${selectedId === e.id}"><td><strong class="variable-key" title="${escape(e.key)}">${escape(e.key)}</strong><small class="variable-note" title="${escape(note(e))}">${escape(t(e.category))} <span class="variable-separator">·</span> ${escape(note(e))}</small></td><td><span class="type-tag ${e.section}">${escape(section(e))}</span></td><td class="value-cell" title="${escape(e.value)}">${changed(e) ? '<i class="dirty-dot"></i>' : ''}${escape(e.value)}</td></tr>`,
    )
    .join('');
  document.querySelector<HTMLElement>('#empty-filter')!.hidden = entries.length > 0;
  document.querySelector('#item-count')!.textContent = t('common.items_count', {
    shown: entries.length,
    total: view!.entries.length,
  });
  document.querySelector('#page-count')!.textContent = `${pageIndex + 1} / ${pages}`;
  document.querySelector<HTMLButtonElement>('#previous-page')!.disabled = pageIndex === 0;
  document.querySelector<HTMLButtonElement>('#next-page')!.disabled = pageIndex + 1 === pages;
  document.querySelectorAll<HTMLTableRowElement>('tr[data-id]').forEach((row) => {
    const select = () => {
      selectedId = Number(row.dataset.id);
      renderRows();
      renderInspector();
    };
    row.onclick = select;
    row.ondblclick = () => {
      select();
      document.querySelector<HTMLInputElement>('#edit-value')?.focus();
    };
    row.onkeydown = (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        select();
        document.querySelector<HTMLInputElement>('#edit-value')?.focus();
      }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        const index = visible.findIndex((v) => v.id === Number(row.dataset.id));
        const next = visible[index + (e.key === 'ArrowDown' ? 1 : -1)];
        if (next) {
          selectedId = next.id;
          renderRows();
          renderInspector();
          document.querySelector<HTMLElement>(`tr[data-id="${next.id}"]`)?.focus();
        }
      }
    };
  });
  if (previous !== selectedId) renderInspector();
}
function editorMode(entry: Entry) {
  if (entry.section === 'meta') return 'number';
  if (['True', 'False'].includes(entry.value.trim())) return 'boolean';
  return entry.value.trim() && !Number.isNaN(Number(entry.value)) ? 'number' : 'text';
}
function renderInspector() {
  const entry = view!.entries.find((e) => e.id === selectedId);
  const inspector = document.querySelector('#inspector')!;
  if (!entry) {
    inspector.innerHTML = `<div class="inspector-empty">${icon('edit')}<h3>${escape(t('common.unselected'))}</h3><p>${escape(t('common.no_category_note'))}</p></div>`;
    return;
  }
  const mode = editorMode(entry);
  inspector.innerHTML = `<div class="inspector-top"><span class="eyebrow">${escape(t('inspector.title'))}</span>${icon('edit')}</div><h2>${escape(note(entry) || entry.key)}</h2><code class="inspector-key">${escape(entry.key)}</code><div class="inspector-tags"><span class="type-tag ${entry.section}">${escape(section(entry))}</span><span class="badge">${escape(t(`inspector.value_type_${mode}`))}</span></div><dl><dt>${escape(t('inspector.category'))}</dt><dd>${escape(t(entry.category))}</dd><dt>${escape(t('new.currentValue'))}</dt><dd class="mono current-value">${escape(entry.value)}</dd>${changed(entry) ? `<dt>${escape(t('inspector.original_value'))}</dt><dd class="mono">${escape(originals.get(entry.id)!)} </dd>` : ''}</dl><form id="edit-form"><label for="edit-value">${escape(t('inspector.new_value'))}</label>${mode === 'boolean' ? `<select id="edit-value"><option ${entry.value === 'True' ? 'selected' : ''}>True</option><option ${entry.value === 'False' ? 'selected' : ''}>False</option></select>` : `<textarea id="edit-value" rows="${mode === 'text' ? 4 : 2}" spellcheck="false" ${mode === 'number' ? 'inputmode="decimal"' : ''}>${escape(entry.value)}</textarea>`}<p class="input-hint">${escape(t(mode === 'number' ? 'new.numberHint' : mode === 'boolean' ? 'new.booleanHint' : 'new.textHint'))}</p><button class="button primary apply-button" type="submit">${icon('check')}${escape(t('buttons.apply_change'))}</button><button id="restore" class="text-button" type="button">${icon('refresh')}${escape(t('buttons.restore_value'))}</button>${changed(entry) ? `<button id="restore-original" class="text-button" type="button">${icon('undo')}${escape(t('new.restoreOriginal'))}</button>` : ''}<p id="edit-error" class="inline-error" role="alert"></p></form><div class="note-box"><h3>${escape(t('inspector.category_note'))}</h3><p>${escape(note(entry))}</p></div>`;
  bind('restore-original', () =>
    action(async () => {
      acceptView(await invoke<View>('restore_entry', { id: entry.id }));
      render();
      toast(t('new.restored'));
    }),
  );
  bind('restore', () => {
    document.querySelector<HTMLTextAreaElement | HTMLSelectElement>('#edit-value')!.value =
      entry.value;
    document.querySelector('#edit-error')!.textContent = '';
  });
  document.querySelector('#edit-form')!.addEventListener('submit', (e) => {
    e.preventDefault();
    void apply(entry);
  });
  document.querySelector('#edit-value')!.addEventListener('keydown', (e) => {
    const k = e as KeyboardEvent;
    if (k.key === 'Enter' && (mode !== 'text' || k.ctrlKey || k.metaKey)) {
      k.preventDefault();
      void apply(entry);
    }
  });
}
async function apply(entry: Entry) {
  const value = document
    .querySelector<HTMLTextAreaElement | HTMLSelectElement>('#edit-value')!
    .value.trim();
  const error = document.querySelector('#edit-error')!;
  if (!value) {
    error.textContent = t('message.value_required');
    return;
  }
  if (
    editorMode(entry) === 'number' &&
    !/^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/.test(value)
  ) {
    error.textContent = t('message.number_required');
    return;
  }
  await action(async () => {
    acceptView(await invoke<View>('apply_edit', { id: entry.id, value }));
    render();
    toast(t('message.change_applied'));
  });
}
async function saveCurrent(as = false) {
  if (!view || busy) return;
  let path: string | null = null;
  if (as) {
    path = await save({
      title: t('dialog.save_as'),
      defaultPath: view.path,
      filters: [{ name: t('dialog.cts_save'), extensions: ['gd'] }],
    });
    if (!path) return;
  }
  await action(async () => {
    const result = await invoke<{ view: View; backup: string }>('save_session', { path });
    acceptView(result.view);
    reviewing = false;
    lastBackup = result.backup;
    localStorage.setItem(
      'cts.recents',
      JSON.stringify(
        [result.view.path, ...readRecents().filter((p) => p !== result.view.path)].slice(0, 5),
      ),
    );
    render();
    toast(t('new.savedFiles', { files: result.view.files.map((f) => f.name).join(' + ') }));
  });
}
async function history(redo = false) {
  if (!view || !(redo ? view.canRedo : view.canUndo)) return;
  await action(async () => {
    acceptView(await invoke<View>('history_edit', { redo }));
    render();
    toast(t(redo ? 'new.redoDone' : 'new.undoDone'));
  });
}
function bindWorkspace() {
  bind('undo', () => history());
  bind('redo', () => history(true));
  bind('review-changes', () => {
    reviewing = true;
    renderReview();
  });
  document.querySelector<HTMLInputElement>('#search')!.oninput = (e) => {
    query = (e.target as HTMLInputElement).value;
    pageIndex = 0;
    renderRows();
  };
  document.querySelectorAll<HTMLButtonElement>('[data-category]').forEach(
    (b) =>
      (b.onclick = () => {
        category = b.dataset.category!;
        pageIndex = 0;
        document
          .querySelectorAll('[data-category]')
          .forEach((el) => el.classList.toggle('active', el === b));
        renderRows();
      }),
  );
  document.querySelectorAll<HTMLButtonElement>('[data-section]').forEach(
    (b) =>
      (b.onclick = () => {
        source = b.dataset.section!;
        pageIndex = 0;
        document
          .querySelectorAll('[data-section]')
          .forEach((el) => el.classList.toggle('active', el === b));
        renderRows();
      }),
  );
  document.querySelector<HTMLInputElement>('#changes-only')!.onchange = (e) => {
    changedOnly = (e.target as HTMLInputElement).checked;
    pageIndex = 0;
    renderRows();
  };
  bind('clear-filters', () => {
    query = '';
    source = 'all';
    category = 'all';
    changedOnly = false;
    pageIndex = 0;
    render();
    document.querySelector<HTMLInputElement>('#search')?.focus();
  });
  bind('previous-page', () => {
    pageIndex--;
    renderRows();
  });
  bind('next-page', () => {
    pageIndex++;
    renderRows();
  });
  bind('reload', () => load(view!.path));
  bind('save', () => saveCurrent());
  bind('save-as', () => saveCurrent(true));
  bind('reveal-current', () => revealItemInDir(view!.path));
  bind('show-backup', () => revealItemInDir(lastBackup));
  bind('backup', async () => {
    const directory = await open({
      directory: true,
      multiple: false,
      title: t('new.backupDirectory'),
    });
    if (typeof directory !== 'string') return;
    await action(async () => {
      lastBackup = await invoke<string>('backup_session', { directory });
      render();
      toast(`${t('dialog.backup_done_title')}: ${lastBackup}`);
    });
  });
  renderRows();
  renderInspector();
}
function renderReview() {
  const slot = document.querySelector('#changes-slot')!;
  if (!reviewing || !view) {
    slot.innerHTML = '';
    return;
  }
  const entries = view.entries.filter(changed);
  slot.innerHTML = `<div class="modal-backdrop"><section class="changes-modal" role="dialog" aria-modal="true" aria-labelledby="changes-title"><div class="section-heading"><h2 id="changes-title">${escape(t('new.reviewChanges'))} · ${entries.length}</h2><button id="close-review" class="icon-button" aria-label="${escape(t('new.dismiss'))}">${icon('close')}</button></div><div class="review-list">${entries.map((e) => `<article class="review-item"><strong>${escape(e.key)}</strong><small>${escape(note(e))}</small><dl><dt>${escape(t('inspector.original_value'))}</dt><dd>${escape(originals.get(e.id) ?? '')}</dd><dt>${escape(t('new.currentValue'))}</dt><dd>${escape(e.value)}</dd></dl></article>`).join('')}</div><div class="review-actions">${button('review-back', 'new.keepEditing', 'back')}${button('review-save', view.files.length > 1 ? 'new.saveBoth' : 'buttons.save_in_place', 'save', 'primary', !view.dirty)}</div></section></div>`;
  const close = () => {
    reviewing = false;
    renderReview();
    document.querySelector<HTMLButtonElement>('#review-changes')?.focus();
  };
  bind('close-review', close);
  bind('review-back', close);
  bind('review-save', () => saveCurrent());
  document.querySelector<HTMLButtonElement>('#close-review')?.focus();
}
function renderUpdate() {
  const slot = document.querySelector('#update-slot')!;
  if (!pendingUpdate) {
    slot.innerHTML = '';
    return;
  }
  slot.innerHTML = `<div class="modal-backdrop"><section class="update-modal" role="dialog" aria-modal="true" aria-labelledby="update-title"><span class="folder-icon">${icon('download')}</span><h2 id="update-title">${escape(t('update.available', { version: pendingUpdate.version }))}</h2><p>${escape(pendingUpdate.title || t('update.current_new'))}</p><pre>${escape(pendingUpdate.changelog || t('update.no_changelog'))}</pre><div>${button('update-later', 'update.later', 'close')}${button('update-download', 'update.download', 'arrow', 'primary')}</div></section></div>`;
  bind('update-later', () => {
    pendingUpdate = null;
    renderUpdate();
  });
  bind('update-download', async () => {
    await openUrl(pendingUpdate!.url);
    pendingUpdate = null;
    renderUpdate();
  });
}
document.addEventListener('keydown', (e) => {
  const cmd = e.ctrlKey || e.metaKey;
  if (reviewing && e.key === 'Escape') {
    e.preventDefault();
    reviewing = false;
    renderReview();
    document.querySelector<HTMLButtonElement>('#review-changes')?.focus();
    return;
  }
  if (reviewing && e.key === 'Tab') {
    const buttons = [
      ...document.querySelectorAll<HTMLButtonElement>('.changes-modal button:not(:disabled)'),
    ];
    const first = buttons[0],
      last = buttons.at(-1);
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last?.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first?.focus();
    }
  }
  const typing =
    e.target instanceof HTMLElement &&
    (e.target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName));
  if (cmd && !typing && page === 'editor' && ['z', 'y'].includes(e.key.toLowerCase())) {
    e.preventDefault();
    void history(e.shiftKey || e.key.toLowerCase() === 'y');
  }
  if (cmd && e.key.toLowerCase() === 'o') {
    e.preventDefault();
    void pickFile().catch((err) => toast(String(err), true));
  }
  if (cmd && e.key.toLowerCase() === 's') {
    e.preventDefault();
    void saveCurrent(e.shiftKey).catch((err) => toast(String(err), true));
  }
  if (cmd && e.key.toLowerCase() === 'f' && view) {
    e.preventDefault();
    if (page !== 'editor') {
      page = 'editor';
      render();
    }
    document.querySelector<HTMLInputElement>('#search')?.focus();
  }
  if (e.key === 'F5' && view) {
    e.preventDefault();
    void load(view.path);
  }
  if (e.key === 'Escape' && pendingUpdate) {
    pendingUpdate = null;
    renderUpdate();
  }
});
window.addEventListener('beforeunload', (e) => {
  if (view?.dirty) {
    e.preventDefault();
    e.returnValue = '';
  }
});
render();
if (isTauri()) {
  void invoke<Location[]>('discover_saves')
    .then((data) => {
      locations = data;
      if (page === 'home') render();
      if (localStorage.getItem('cts.autoload') === 'true') {
        const location = data.find((l) => l.files.some((f) => f.exists));
        if (location) void load(location.path);
      }
    })
    .catch((e) => toast(String(e), true));
  void invoke<Update | null>('check_update', { locale: getLocale() })
    .then((update) => {
      pendingUpdate = update;
      renderUpdate();
    })
    .catch(() => {});
  const win = getCurrentWindow();
  void win.onCloseRequested(async (e) => {
    if (busy) {
      e.preventDefault();
      return;
    }
    if (!(await mayDiscard())) e.preventDefault();
  });
  void win.onDragDropEvent((e) => {
    root.classList.toggle('dragging', e.payload.type === 'over' || e.payload.type === 'enter');
    if (e.payload.type === 'drop') {
      root.classList.remove('dragging');
      if (e.payload.paths[0]) void load(e.payload.paths[0]);
    }
  });
}
