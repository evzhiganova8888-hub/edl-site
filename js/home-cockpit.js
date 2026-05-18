/* ============================================================
   Home Cockpit — interactive product demo on /index
   - tab switching across 5 layers
   - count-up on first reveal
   - bar chart animation
   - AI typing animation
   ============================================================ */
(function () {
  'use strict';

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const cockpit = document.querySelector('.cockpit');
  if (!cockpit) return;

  const tabs = cockpit.querySelectorAll('.cockpit__tab');
  const panels = cockpit.querySelectorAll('.cockpit__panel');
  const liveTime = cockpit.querySelector('[data-cockpit-time]');

  // --- Tab switching ---
  function activate(tabId) {
    tabs.forEach(t => t.setAttribute('aria-selected', t.dataset.tab === tabId ? 'true' : 'false'));
    panels.forEach(p => p.classList.toggle('is-active', p.dataset.panel === tabId));
    animatePanel(tabId);
    if (window.EDLTrack) window.EDLTrack('cockpit_tab_switched', { tab: tabId });
  }
  tabs.forEach(tab => {
    tab.addEventListener('click', () => activate(tab.dataset.tab));
    tab.addEventListener('keydown', (e) => {
      const order = Array.from(tabs);
      const idx = order.indexOf(tab);
      if (e.key === 'ArrowRight') { e.preventDefault(); const n = order[(idx + 1) % order.length]; n.focus(); activate(n.dataset.tab); }
      if (e.key === 'ArrowLeft')  { e.preventDefault(); const n = order[(idx - 1 + order.length) % order.length]; n.focus(); activate(n.dataset.tab); }
    });
  });

  // --- Animate panel content (bars, score arc, count-up) ---
  function animatePanel(tabId) {
    const panel = cockpit.querySelector(`[data-panel="${tabId}"]`);
    if (!panel) return;

    // Bars
    panel.querySelectorAll('.cockpit__bar').forEach(bar => {
      const target = parseFloat(bar.dataset.height || '0');
      bar.style.height = '0';
      requestAnimationFrame(() => {
        if (reduceMotion) {
          bar.style.transition = 'none';
          bar.style.height = target + '%';
        } else {
          setTimeout(() => { bar.style.height = target + '%'; }, 80);
        }
      });
    });

    // Score arcs
    panel.querySelectorAll('.cockpit__score-arc').forEach(arc => {
      const target = parseInt(arc.dataset.score || '0', 10);
      const circumference = 251.2;
      const offset = circumference - (circumference * target) / 100;
      arc.style.strokeDashoffset = circumference;
      if (reduceMotion) {
        arc.style.transition = 'none';
        arc.style.strokeDashoffset = String(offset);
      } else {
        setTimeout(() => { arc.style.strokeDashoffset = String(offset); }, 120);
      }
    });

    // Count-up
    panel.querySelectorAll('[data-countup]').forEach(el => {
      const target = parseFloat(el.dataset.countup);
      const suffix = el.dataset.suffix || '';
      const decimals = parseInt(el.dataset.decimals || '0', 10);
      const duration = reduceMotion ? 0 : 900;
      const start = performance.now();
      const initial = 0;
      function step(now) {
        const elapsed = now - start;
        const p = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - p, 3);
        const value = initial + (target - initial) * eased;
        el.textContent = value.toFixed(decimals) + suffix;
        if (p < 1) requestAnimationFrame(step);
      }
      if (duration === 0) {
        el.textContent = target.toFixed(decimals) + suffix;
      } else {
        requestAnimationFrame(step);
      }
    });

    // Restart AI msgs (force re-animation)
    panel.querySelectorAll('.cockpit__msg').forEach((m, i) => {
      m.style.animation = 'none';
      // force reflow
      void m.offsetWidth;
      m.style.animation = '';
    });
  }

  // --- Live clock ---
  function updateTime() {
    if (!liveTime) return;
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    liveTime.textContent = `${hh}:${mm} MSK`;
  }
  updateTime();
  setInterval(updateTime, 30000);

  // --- Start animation on first visibility ---
  const io = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        animatePanel('strategy');
        io.disconnect();
      }
    });
  }, { threshold: 0.25 });
  io.observe(cockpit);

  // --- Reveal-on-scroll for sections below ---
  const revealEls = document.querySelectorAll('.reveal-on-scroll');
  if (revealEls.length) {
    const revealIo = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('is-visible');
          revealIo.unobserve(e.target);
        }
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -60px 0px' });
    revealEls.forEach(el => revealIo.observe(el));
  }
})();
