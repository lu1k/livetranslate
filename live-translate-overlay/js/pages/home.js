/**
 * pages/home.js — Home / input selection page
 *
 * Performance rationale:
 * - Builds DOM imperatively (no virtual DOM diffing overhead)
 * - State is a plain object; no reactivity framework
 * - All event listeners stored in `listeners` array and removed on unmount
 *   to prevent memory leaks across page navigations
 */

import { navigate } from '../router.js';

// ---- Supported languages (extend as backend grows) --------
const LANGUAGES = [
  { code: 'auto', label: 'Auto-detect' },
  { code: 'en',   label: 'English' },
  { code: 'es',   label: 'Spanish' },
  { code: 'fr',   label: 'French' },
  { code: 'de',   label: 'German' },
  { code: 'zh',   label: 'Chinese' },
  { code: 'ar',   label: 'Arabic' },
  { code: 'hi',   label: 'Hindi' },
  { code: 'ja',   label: 'Japanese' },
  { code: 'pt',   label: 'Portuguese' },
  { code: 'ru',   label: 'Russian' },
];

// ---- Page-level state (plain object, no proxy/store) ------
const state = {
  inputType: 'mic',  // 'mic' | 'url'
  url: '',
  sourceLang: 'auto',
  targetLang: 'en',
  error: null,
};

// Track all listeners to clean up on unmount
const listeners = [];

function addListener(el, event, handler) {
  el.addEventListener(event, handler);
  listeners.push({ el, event, handler });
}

// ---- DOM helpers ------------------------------------------
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'className') node.className = v;
    else if (k.startsWith('data-')) node.dataset[k.slice(5)] = v;
    else node[k] = v;
  }
  for (const child of children) {
    if (child == null) continue;
    node.append(typeof child === 'string' ? document.createTextNode(child) : child);
  }
  return node;
}

function buildLangOption(lang, selected) {
  return el('option', { value: lang.code, selected: lang.code === selected }, lang.label);
}

function buildLangSelect(id, selectedCode) {
  const select = el('select', { id, className: 'lang-select' });
  LANGUAGES.forEach(lang => select.append(buildLangOption(lang, selectedCode)));
  return select;
}

// ---- Validation -------------------------------------------
function validate() {
  if (state.inputType === 'url') {
    if (!state.url.trim()) return 'Please enter a stream or video URL.';
    try { new URL(state.url.trim()); }
    catch { return 'URL appears invalid. Include http:// or https://'; }
  }
  if (state.sourceLang === state.targetLang && state.sourceLang !== 'auto') {
    return 'Source and target language must differ.';
  }
  return null;
}

// ---- Render -----------------------------------------------
export function mount(root) {
  // ---- Error message (conditionally shown) ----
  const errorMsg = el('p', { className: 'msg err', id: 'home-error', hidden: true });

  // ---- Input type toggle ----
  const micBtn = el('button', { className: 'toggle-btn selected', type: 'button' },
    el('span', { className: 'icon' }, '🎙'),
    'Microphone'
  );
  const urlBtn = el('button', { className: 'toggle-btn', type: 'button' },
    el('span', { className: 'icon' }, '🔗'),
    'Stream URL'
  );

  function selectInputType(type) {
    state.inputType = type;
    micBtn.className = 'toggle-btn' + (type === 'mic' ? ' selected' : '');
    urlBtn.className = 'toggle-btn' + (type === 'url' ? ' selected' : '');
    urlField.hidden = type !== 'url';
    clearError();
  }

  addListener(micBtn, 'click', () => selectInputType('mic'));
  addListener(urlBtn, 'click', () => selectInputType('url'));

  // ---- URL input ----
  const urlInput = el('input', {
    type: 'text',
    className: 'text-input',
    placeholder: 'https://example.com/stream.m3u8',
    autocomplete: 'off',
    spellcheck: false,
  });
  addListener(urlInput, 'input', (e) => {
    state.url = e.target.value;
    clearError();
  });

  const urlField = el('div', { hidden: true },
    el('p', { className: 'field-label' }, 'Stream / Video URL'),
    urlInput
  );

  // ---- Language selectors ----
  const sourceSel = buildLangSelect('src-lang', state.sourceLang);
  const targetSel = buildLangSelect('tgt-lang', state.targetLang);

  addListener(sourceSel, 'change', (e) => { state.sourceLang = e.target.value; });
  addListener(targetSel, 'change', (e) => { state.targetLang = e.target.value; });

  // ---- Mic permission hint ----
  const micHint = el('p', { className: 'source-info', id: 'mic-hint' },
    el('span', { className: 'status-dot' }),
    'Microphone access will be requested on start.'
  );

  // ---- Start button ----
  const startBtn = el('button', { className: 'btn-primary', type: 'button' }, 'Start Translating');
  addListener(startBtn, 'click', handleStart);

  // ---- Sign language nav ----
  const signNav = el('div', { className: 'nav-sign' },
    '⌥ ',
    (() => {
      const a = el('a', {}, 'Sign Language Mode →');
      addListener(a, 'click', () => navigate('/sign'));
      return a;
    })()
  );

  // ---- Assemble panel ----
  const panel = el('div', { className: 'panel' },
    el('div', { className: 'panel-header' },
      el('span', { className: 'logo-mark' }, 'Live', el('span', {}, 'Translate')),
      el('span', { className: 'version-tag' }, 'MVP v0.1')
    ),
    el('div', { className: 'panel-body' },
      el('p', { className: 'field-label' }, 'Input Source'),
      el('div', { className: 'input-toggle' }, micBtn, urlBtn),
      urlField,
      micHint,
      el('div', { className: 'divider' }),
      el('p', { className: 'field-label' }, 'Languages'),
      el('div', { className: 'lang-row' },
        sourceSel,
        el('span', { className: 'arrow' }, '→'),
        targetSel
      ),
      errorMsg,
      startBtn,
      signNav
    )
  );

  root.append(panel);

  // ---- Shortcut listener (Space = start, M = mic, U = url) ----
  const shortcutHandler = (e) => {
    switch (e.detail) {
      case ' ': handleStart(); break;
      case 'm': selectInputType('mic'); break;
      case 'u': selectInputType('url'); urlInput.focus(); break;
    }
  };
  addListener(document, 'app:shortcut', shortcutHandler);

  // ---- Helpers ----
  function clearError() {
    errorMsg.hidden = true;
    urlInput.classList.remove('err');
  }

  function handleStart() {
    const err = validate();
    if (err) {
      errorMsg.textContent = err;
      errorMsg.hidden = false;
      if (state.inputType === 'url') urlInput.classList.add('err');
      return;
    }
    // TODO: Pass state to translation service adapter
    // navigate('/translating') once the active translation page is built
    alert(`[MVP] Would start translating.\nInput: ${state.inputType === 'mic' ? 'Microphone' : state.url}\nFrom: ${state.sourceLang} → To: ${state.targetLang}`);
  }
}

// ---- Cleanup on unmount (prevents memory leaks) -----------
export function unmount() {
  for (const { el, event, handler } of listeners) {
    el.removeEventListener(event, handler);
  }
  listeners.length = 0;
}
