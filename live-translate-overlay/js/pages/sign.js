/**
 * pages/sign.js — Sign Language Capture page
 *
 * Performance rationale:
 * - MediaStream is stored at module scope so we can reliably stop tracks on unmount
 * - No canvas processing in this MVP (just preview); ML backend integration point marked
 * - requestAnimationFrame NOT used unless/until frame analysis is needed
 * - Stats update uses setInterval at 1 Hz — not rAF — to avoid 60fps JS execution
 */

import { navigate } from '../router.js';

// ---- Module-scope stream ref (survives re-renders, cleaned on unmount) ----
let stream = null;
let statsInterval = null;
let frameCount = 0;
const listeners = [];

function addListener(el, event, handler) {
  el.addEventListener(event, handler);
  listeners.push({ el, event, handler });
}

// ---- Simple DOM builder -------------------------------------------
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'className') node.className = v;
    else node[k] = v;
  }
  for (const child of children) {
    if (child == null) continue;
    node.append(typeof child === 'string' ? document.createTextNode(child) : child);
  }
  return node;
}

// ---- Mount --------------------------------------------------------
export function mount(root) {
  let isCapturing = false;

  // ---- Webcam elements ----
  const videoOverlayText = el('span', {}, '⬡  Camera Off');
  const videoOverlay     = el('div', { className: 'webcam-overlay' }, videoOverlayText);
  const video            = el('video', { id: 'webcam-feed', autoplay: true, muted: true, playsinline: true });
  const camWrapper       = el('div', { className: 'webcam-wrapper' }, video, videoOverlay);

  // ---- Capture button ----
  const captureBtn = el('button', { className: 'btn-capture start', type: 'button' }, '▶  Start Capture');

  // ---- Error / info message ----
  const statusMsg = el('p', { className: 'msg info', hidden: true });

  // ---- Recognition output (placeholder for backend integration) ----
  const recognitionBox = el('div', { className: 'recognition-output' },
    el('span', { className: 'placeholder' }, 'Sign language output will appear here…')
  );

  // ---- Stats bar ----
  const fpsVal    = el('span', { className: 'stat-val' }, '—');
  const statusDot = el('span', { className: 'status-dot' });
  const statsBar  = el('div', { className: 'stats-bar' },
    statusDot,
    el('span', {}, 'FPS '), fpsVal,
    el('span', { style: 'margin-left:12px' }, 'Backend '),
    el('span', { className: 'stat-val' }, 'not connected')
  );

  // ---- Back link ----
  const backLink = (() => {
    const a = el('a', { className: 'btn-ghost' }, '← Back');
    addListener(a, 'click', () => navigate('/'));
    return a;
  })();

  // ---- Panel ----
  const panel = el('div', { className: 'panel' },
    el('div', { className: 'panel-header' },
      el('span', { className: 'logo-mark' }, '✋ Sign', el('span', {}, ' Mode')),
      el('span', { className: 'version-tag' }, 'MVP v0.1')
    ),
    el('div', { className: 'panel-body' },
      camWrapper,
      statusMsg,
      el('div', { className: 'capture-controls' },
        captureBtn,
        backLink
      ),
      el('p', { className: 'field-label', style: 'margin-top:4px' }, 'Recognition Output'),
      recognitionBox,
      statsBar
    )
  );

  root.append(panel);

  // ---- Toggle capture logic ----------------------------------
  async function startCapture() {
    statusMsg.hidden = true;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: false,
      });
      video.srcObject = stream;
      isCapturing = true;

      // Visual state updates
      camWrapper.classList.add('active');
      videoOverlay.classList.add('hidden');
      captureBtn.className = 'btn-capture stop';
      captureBtn.textContent = '■  Stop Capture';
      statusDot.className = 'status-dot active';

      // Low-frequency stats poll (1 Hz is sufficient; avoids 60fps JS)
      // In a real implementation, frame timestamps from rAF would be used here
      statsInterval = setInterval(() => {
        // Placeholder: real FPS would come from a frame counter in rAF callback
        fpsVal.textContent = stream?.active ? '~30' : '—';
      }, 1000);

      // ── Backend integration point ─────────────────────────────
      // When a sign-language recognition backend is ready:
      //   const ws = new WebSocket('wss://api.example.com/sign-recognize');
      //   Capture frames via: canvas.drawImage(video, 0, 0); canvas.toBlob(...)
      //   Send blob/base64 over ws, update recognitionBox with result
      // ─────────────────────────────────────────────────────────

    } catch (err) {
      const msg = err.name === 'NotAllowedError'
        ? 'Camera permission denied. Please allow camera access and try again.'
        : `Camera error: ${err.message}`;
      statusMsg.textContent = msg;
      statusMsg.className = 'msg err';
      statusMsg.hidden = false;
    }
  }

  function stopCapture() {
    if (stream) {
      // Stop all tracks to release hardware — critical to avoid resource leak
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }
    video.srcObject = null;
    isCapturing = false;

    camWrapper.classList.remove('active');
    videoOverlay.classList.remove('hidden');
    captureBtn.className = 'btn-capture start';
    captureBtn.textContent = '▶  Start Capture';
    statusDot.className = 'status-dot';
    fpsVal.textContent = '—';

    clearInterval(statsInterval);
    statsInterval = null;
  }

  addListener(captureBtn, 'click', () => {
    if (isCapturing) stopCapture();
    else startCapture();
  });

  // ---- Keyboard shortcut (Space = toggle) -------------------
  const shortcutHandler = (e) => {
    if (e.detail === ' ') {
      if (isCapturing) stopCapture();
      else startCapture();
    }
  };
  addListener(document, 'app:shortcut', shortcutHandler);
}

// ---- Cleanup — MUST stop camera tracks on route change ----
export function unmount() {
  // Stop camera hardware if user navigates away mid-capture
  if (stream) {
    stream.getTracks().forEach(t => t.stop());
    stream = null;
  }
  clearInterval(statsInterval);
  statsInterval = null;

  for (const { el, event, handler } of listeners) {
    el.removeEventListener(event, handler);
  }
  listeners.length = 0;
}
