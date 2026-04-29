/* ===================================================================
   EDL Clock v2 — iPhone-style scroll picker
   После Сохранить: toast «Сводка установлена» + CTA «Записаться на демо»
   =================================================================== */

(function () {
  'use strict';

  function initClock(root) {
    if (!root || root.__inited) return;
    root.__inited = true;

    const scroll  = root.querySelector('.clock__picker-scroll');
    const cells   = root.querySelectorAll('.clock__cell');
    const display = root.querySelectorAll('[data-clock-display]');
    const saveBtn = root.querySelector('[data-clock-save]');
    const cancelBtn = root.querySelector('[data-clock-cancel]');
    const resetBtn  = root.querySelector('[data-clock-reset]');
    const success = root.querySelector('.clock__success');

    if (!scroll || !cells.length) return;

    let activeTime = '08:30';
    let snapTimer = null;

    /* ----- Centering helpers ----- */

    function getCellHeight() {
      return cells[0].offsetHeight; // 50px
    }

    function scrollToCell(cell, instant) {
      const idx = Array.from(cells).indexOf(cell);
      if (idx < 0) return;
      const top = idx * getCellHeight();
      try {
        scroll.scrollTo({ top, behavior: instant ? 'auto' : 'smooth' });
      } catch (e) {
        scroll.scrollTop = top; // fallback
      }
    }

    function updateActiveByScroll() {
      const cellH = getCellHeight();
      const idx = Math.round(scroll.scrollTop / cellH);
      const safeIdx = Math.max(0, Math.min(cells.length - 1, idx));
      const cell = cells[safeIdx];
      if (!cell) return;

      cells.forEach(c => c.classList.toggle('is-active', c === cell));
      activeTime = cell.dataset.time;
      display.forEach(el => { el.textContent = activeTime; });
    }

    /* ----- Init: scroll to default ----- */

    function init() {
      const defCell = root.querySelector('.clock__cell[data-default]') || cells[Math.floor(cells.length / 2)];
      // Делаем после layout
      requestAnimationFrame(() => {
        scrollToCell(defCell, true);
        updateActiveByScroll();
      });
    }

    /* ----- Scroll handling ----- */

    scroll.addEventListener('scroll', () => {
      updateActiveByScroll();
      if (snapTimer) clearTimeout(snapTimer);
      snapTimer = setTimeout(() => {
        // soft re-snap
        const cellH = getCellHeight();
        const idx = Math.round(scroll.scrollTop / cellH);
        const safeIdx = Math.max(0, Math.min(cells.length - 1, idx));
        scrollToCell(cells[safeIdx]);
      }, 120);
    });

    /* ----- Click on cell — scroll to it ----- */

    cells.forEach(cell => {
      cell.addEventListener('click', () => {
        scrollToCell(cell);
      });
    });

    /* ----- Wheel: convert vertical wheel to scroll ----- */

    scroll.addEventListener('wheel', (e) => {
      e.preventDefault();
      scroll.scrollTop += e.deltaY;
    }, { passive: false });

    /* ----- Save button — shows toast + CTA ----- */

    function showSuccess() {
      root.classList.add('is-saved');
      // double-rAF to allow display change before opacity transition
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (success) success.classList.add('is-visible');
        });
      });

      // Analytics
      try {
        if (window.ym && typeof window.ym === 'function') {
          const counters = Object.keys(window).filter(k => /^ym\d+$/.test(k));
          if (counters.length) {
            window[counters[0]]('reachGoal', 'clock_demo_saved', { time: activeTime });
          }
        }
        window.dispatchEvent(new CustomEvent('edl:clock-saved', { detail: { time: activeTime } }));
      } catch (e) {}
    }

    function resetClock() {
      root.classList.remove('is-saved');
      if (success) success.classList.remove('is-visible');
      // Re-snap on default
      requestAnimationFrame(() => {
        const defCell = root.querySelector('.clock__cell[data-default]') || cells[Math.floor(cells.length / 2)];
        scrollToCell(defCell, true);
        updateActiveByScroll();
      });
    }

    if (saveBtn) saveBtn.addEventListener('click', showSuccess);
    if (resetBtn) resetBtn.addEventListener('click', resetClock);
    if (cancelBtn) cancelBtn.addEventListener('click', () => {
      if (root.classList.contains('is-saved')) resetClock();
    });

    /* ----- Keyboard support on the scroller ----- */

    scroll.setAttribute('tabindex', '0');
    scroll.setAttribute('role', 'listbox');
    scroll.setAttribute('aria-label', 'Выберите время утренней сводки');

    scroll.addEventListener('keydown', (e) => {
      const cellH = getCellHeight();
      const idx = Math.round(scroll.scrollTop / cellH);
      let nextIdx = idx;
      if (e.key === 'ArrowDown') nextIdx = Math.min(cells.length - 1, idx + 1);
      else if (e.key === 'ArrowUp') nextIdx = Math.max(0, idx - 1);
      else if (e.key === 'Enter') { e.preventDefault(); showSuccess(); return; }
      else if (e.key === 'Home') nextIdx = 0;
      else if (e.key === 'End') nextIdx = cells.length - 1;
      else return;
      e.preventDefault();
      scrollToCell(cells[nextIdx]);
    });

    /* ----- Recalculate on resize ----- */
    let resizeTimer;
    window.addEventListener('resize', () => {
      if (resizeTimer) clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        const activeCell = root.querySelector('.clock__cell.is-active') || cells[Math.floor(cells.length / 2)];
        scrollToCell(activeCell, true);
      }, 150);
    });

    init();
  }

  function start() {
    document.querySelectorAll('.clock').forEach(initClock);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
