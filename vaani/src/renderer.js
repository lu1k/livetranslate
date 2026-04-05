/* ════════════════════════════════════════════════
   VAANI — Renderer Process
   All UI logic runs here (in the browser context).
════════════════════════════════════════════════ */

'use strict';

// ── DOM refs ────────────────────────────────────
const wsDot       = document.getElementById('wsDot');
const wsLabel     = document.getElementById('wsLabel');
const wsUrlInput  = document.getElementById('wsUrl');
const btnConnect  = document.getElementById('btnConnect');
const btnDisconn  = document.getElementById('btnDisconnect');

const srcMic      = document.getElementById('srcMic');
const srcUrl      = document.getElementById('srcUrl');
const micArea     = document.getElementById('micArea');
const urlArea     = document.getElementById('urlArea');
const micRing     = document.getElementById('micRing');
const micState    = document.getElementById('micState');

const spDot       = document.getElementById('spDot');
const spStatus    = document.getElementById('spStatus');
const spOutput    = document.getElementById('spOutput');
const spPlaceholder = document.getElementById('spPlaceholder');
const btnSpeech   = document.getElementById('btnSpeech');
const btnSpLabel  = document.getElementById('btnSpLabel');

const islDot      = document.getElementById('islDot');
const islStatus   = document.getElementById('islStatus');
const islOutput   = document.getElementById('islOutput');
const islEmpty    = document.getElementById('islEmpty');
const btnIsl      = document.getElementById('btnIsl');
const btnIslLabel = document.getElementById('btnIslLabel');

// Window controls (wired to preload bridge)
document.getElementById('btnMin').addEventListener('click',   () => window.electronAPI.minimize());
document.getElementById('btnMax').addEventListener('click',   () => window.electronAPI.maximize());
document.getElementById('btnClose').addEventListener('click', () => window.electronAPI.close());

// Swap max/restore icon
window.electronAPI.onMaxState((isMax) => {
  document.getElementById('btnMax').textContent = isMax ? '❐' : '⬜';
});

// ── State ───────────────────────────────────────
let ws            = null;
let speechRunning = false;
let islRunning    = false;
let speechText    = '';

// ══════════════════════════════════════════════════
// WebSocket
// ══════════════════════════════════════════════════
function setWsUi(state) {
  wsDot.className = 'ws-dot ' + state;
  wsLabel.textContent = {
    connected:  'CONNECTED',
    connecting: 'CONNECTING…',
    error:      'ERROR',
  }[state] || 'DISCONNECTED';
}

function connect() {
  const url = wsUrlInput.value.trim();
  if (!url) return;
  if (ws && ws.readyState < 2) ws.close();

  setWsUi('connecting');
  try {
    ws = new WebSocket(url);
  } catch (e) {
    setWsUi('error');
    return;
  }

  ws.onopen  = () => setWsUi('connected');
  ws.onclose = () => {
    setWsUi('');
    if (speechRunning) stopSpeech(true);
    if (islRunning)    stopIsl(true);
  };
  ws.onerror = () => setWsUi('error');
  ws.onmessage = ({ data }) => {
    let msg;
    try { msg = JSON.parse(data); } catch { msg = { type: 'raw', data }; }
    handleMessage(msg);
  };
}

function disconnect() {
  if (ws) { ws.close(); ws = null; }
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(obj));
    return true;
  }
  return false;
}

// ══════════════════════════════════════════════════
// Message dispatcher
// ══════════════════════════════════════════════════
function handleMessage(msg) {
  switch (msg.type) {
    case 'speech_transcript':
    case 'transcript':
      appendSpeech(msg.text || msg.data || '');
      break;
    case 'isl_signs':
    case 'isl':
      appendIsl(msg.word || '', msg.description || msg.data || '');
      break;
    case 'speech_status':
      setSpeechStatus(msg.status);
      break;
    case 'isl_status':
      setIslStatus(msg.status);
      break;
    case 'error':
      console.error('[VAANI WS]', msg.message || msg.data);
      break;
    default:
      if (typeof msg.data === 'string') appendSpeech(msg.data);
  }
}

// ══════════════════════════════════════════════════
// Speech panel
// ══════════════════════════════════════════════════
function startSpeech() {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    alert('Connect to a WebSocket endpoint first.');
    return;
  }
  speechRunning = true;
  speechText = '';
  spOutput.innerHTML = '<span class="cursor"></span>';

  btnSpeech.classList.add('running');
  btnSpLabel.textContent = '■  Stop Translation';
  micRing.classList.add('live');
  micState.textContent = 'Listening…';
  setSpeechStatus('running');

  const source = document.querySelector('input[name=source]:checked').value;
  const payload = { type: 'start_speech', source };
  if (source === 'url') payload.url = document.getElementById('streamUrl').value.trim();
  send(payload);
}

function stopSpeech(silent = false) {
  speechRunning = false;
  btnSpeech.classList.remove('running');
  btnSpLabel.textContent = '▶\u00a0\u00a0Start Translation';
  micRing.classList.remove('live');
  micState.textContent = 'Idle';
  setSpeechStatus('idle');
  if (!silent) send({ type: 'stop_speech' });
}

function appendSpeech(text) {
  const cur = spOutput.querySelector('.cursor');
  if (cur) cur.remove();
  speechText += (speechText ? ' ' : '') + text;
  spOutput.textContent = speechText;
  const newCur = document.createElement('span');
  newCur.className = 'cursor';
  spOutput.appendChild(newCur);
  spOutput.scrollTop = spOutput.scrollHeight;
}

function setSpeechStatus(state) {
  spStatus.textContent = { running: 'Translating…', idle: 'Idle', error: 'Error' }[state] || state;
  spDot.className = 'sdot' + (state === 'running' ? ' on' : '');
}

// ══════════════════════════════════════════════════
// ISL panel
// ══════════════════════════════════════════════════
function startIsl() {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    alert('Connect to a WebSocket endpoint first.');
    return;
  }
  islRunning = true;
  islOutput.innerHTML = '';
  btnIsl.classList.add('running');
  btnIslLabel.textContent = '■  Stop Translation';
  setIslStatus('running');
  send({ type: 'start_isl' });
}

function stopIsl(silent = false) {
  islRunning = false;
  btnIsl.classList.remove('running');
  btnIslLabel.textContent = '▶\u00a0\u00a0Start Translation';
  setIslStatus('idle');
  if (!silent) send({ type: 'stop_isl' });
}

function appendIsl(word, description) {
  const entry = document.createElement('div');
  entry.className = 'isl-entry';
  entry.innerHTML = `
    <div class="isl-word">${esc(word.toUpperCase())}</div>
    <div class="isl-desc">${esc(description)}</div>
  `;
  islOutput.appendChild(entry);
  islOutput.scrollTop = islOutput.scrollHeight;
}

function setIslStatus(state) {
  islStatus.textContent = { running: 'Translating to ISL…', idle: 'Idle', error: 'Error' }[state] || state;
  islDot.className = 'sdot' + (state === 'running' ? ' on' : '');
}

// ══════════════════════════════════════════════════
// Event bindings
// ══════════════════════════════════════════════════
btnConnect.addEventListener('click', connect);
btnDisconn.addEventListener('click', disconnect);

[srcMic, srcUrl].forEach(r => r.addEventListener('change', () => {
  const isMic = srcMic.checked;
  micArea.classList.toggle('hidden', !isMic);
  urlArea.classList.toggle('hidden',  isMic);
}));

btnSpeech.addEventListener('click', () => speechRunning ? stopSpeech() : startSpeech());
btnIsl.addEventListener('click',    () => islRunning    ? stopIsl()    : startIsl());

// ══════════════════════════════════════════════════
// Dev helpers — call from DevTools console:
//   simulate('transcript', 'Hello world')
//   simulate('isl', 'HELLO', 'Right hand raised, palm outward, sweeps forward')
// ══════════════════════════════════════════════════
window.simulate = (type, text, description) => {
  if (type === 'transcript') handleMessage({ type: 'speech_transcript', text });
  if (type === 'isl')        handleMessage({ type: 'isl_signs', word: text || 'WORD', description });
};

// ── Utilities ───────────────────────────────────
function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
