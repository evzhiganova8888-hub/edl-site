/* ============================================================
   EDL Track — unified analytics DataLayer
   Loaded with `defer` after parsing — no blocking on TTI.
   Funnel events: click_MCP → oauth_complete → first_tool_call
   ============================================================ */
(function () {
  'use strict';

  const ENDPOINT = window.EDL_ANALYTICS_ENDPOINT || null;
  const STORAGE_KEY = 'edl_events';
  const buffer = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');

  // Per-event-type rate limit (prevents accidental flood)
  const lastByType = Object.create(null);
  const RATE_MS = 500;

  function track(event, payload) {
    payload = payload || {};
    const now = Date.now();
    if (lastByType[event] && now - lastByType[event] < RATE_MS) return;
    lastByType[event] = now;

    const segment =
      document.body.dataset.segmentActive ||
      sessionStorage.getItem('edl_icp') ||
      'unknown';

    const data = {
      event,
      timestamp: new Date().toISOString(),
      page: document.body.dataset.page || location.pathname,
      segment,
      referrer: document.referrer || null,
      utm: parseUTM(),
      ...payload,
    };

    buffer.push(data);

    // dataLayer for GTM-compatibility
    if (!window.dataLayer) window.dataLayer = [];
    window.dataLayer.push(data);

    persist();
    if (ENDPOINT) scheduleFlush();
  }

  function parseUTM() {
    try {
      const p = new URLSearchParams(location.search);
      const out = {};
      for (const k of ['utm_source','utm_medium','utm_campaign','utm_content','utm_term']) {
        const v = p.get(k);
        if (v) out[k] = v;
      }
      return Object.keys(out).length ? out : null;
    } catch (e) { return null; }
  }

  function persist() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(buffer.slice(-200))); } catch (e) {}
  }

  let flushTimer = null;
  function scheduleFlush() {
    if (flushTimer) return;
    flushTimer = setTimeout(flush, 1500);
  }
  function flush() {
    flushTimer = null;
    if (!ENDPOINT || !buffer.length) return;
    const payload = JSON.stringify(buffer);
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon(ENDPOINT, payload);
      } else {
        fetch(ENDPOINT, { method: 'POST', body: payload, keepalive: true }).catch(() => {});
      }
      buffer.length = 0;
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {}
  }

  window.EDLTrack = track;
  window.addEventListener('beforeunload', flush);
  window.addEventListener('pagehide', flush);
  window.addEventListener('DOMContentLoaded', () => track('page_view', {}));

  // Auto-attach to data-cta-type buttons / links (one-line instrumentation)
  document.addEventListener('click', function (e) {
    const el = e.target.closest('[data-cta-type]');
    if (!el) return;
    track('cta_clicked', {
      cta_type: el.dataset.ctaType,
      cta_location: el.dataset.ctaLocation || 'unknown',
      href: el.getAttribute('href') || null,
    });
  }, { passive: true });

  // Funnel helpers — exposed for direct calls
  window.EDLTrack.funnel = {
    mcpInstallClicked: (where) => track('mcp_install_clicked', { where }),
    oauthCompleted: (provider) => track('oauth_completed', { provider }),
    firstToolCalled: (tool) => track('first_tool_called', { tool }),
  };
})();
