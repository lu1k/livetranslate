/**
 * router.js — Minimal hash-based router
 *
 * Performance rationale:
 * - Uses hashchange (no History API overhead, works in overlay windows)
 * - Routes are plain objects; no class instantiation per navigation
 * - Each page module is imported lazily so initial JS parse is small
 */

/** @type {Map<string, () => Promise<{ mount: (el:HTMLElement) => void, unmount?: () => void }>>} */
const routes = new Map();

let currentUnmount = null;

export function registerRoute(path, loader) {
  routes.set(path, loader);
}

export function navigate(path) {
  // Triggers hashchange → router handles render
  window.location.hash = path;
}

async function render() {
  const hash = window.location.hash.slice(1) || '/';
  const loader = routes.get(hash);
  const app = document.getElementById('app');

  // Unmount previous page (cleanup streams, listeners, etc.)
  if (currentUnmount) {
    currentUnmount();
    currentUnmount = null;
  }

  if (!loader) {
    app.innerHTML = `<p style="color:var(--text-dim);font-size:12px;">404 — route not found: ${hash}</p>`;
    return;
  }

  const page = await loader();
  app.innerHTML = '';  // clear without innerHTML assignment per render cycle

  // Page enter animation class (CSS-only, no GSAP/Framer)
  app.classList.remove('page-enter');
  // Force reflow so animation re-triggers on each navigation
  void app.offsetWidth;
  app.classList.add('page-enter');

  page.mount(app);
  currentUnmount = page.unmount ?? null;
}

export function initRouter() {
  window.addEventListener('hashchange', render);
  // Render immediately for initial load
  render();
}
