/* ===================================================================
   EDL · clock.js · v3 · 30 апреля 2026
   1. iPhone-style крутящийся picker
   2. Save/Cancel надёжно работают через visibility/opacity (не display:none)
   3. Активная подсветка следует за выбором без race conditions
   4. Carousel в секции «Наша система» (вертикально-вращающаяся 3D)
   =================================================================== */

(function () {
  'use strict';

  /* ============== ЧАСТЬ 1: БУДИЛЬНИК ============== */

  function initClock(root) {
    if (!root || root.__inited) return;
    root.__inited = true;

    const scroll  = root.querySelector('.clock__picker-scroll');
    const cells   = Array.from(root.querySelectorAll('.clock__cell'));
    const display = root.querySelectorAll('[data-clock-display]');
    const saveBtn = root.querySelector('[data-clock-save]');
    const cancelBtn = root.querySelector('[data-clock-cancel]');
    const resetBtn  = root.querySelector('[data-clock-reset]');

    if (!scroll || !cells.length) return;

    const CELL_HEIGHT = 50; // должно совпадать с CSS .clock__cell { height: 50px; }
    let activeIdx = cells.findIndex(c => c.hasAttribute('data-default'));
    if (activeIdx < 0) activeIdx = Math.floor(cells.length / 2);

    /* ---- Установка активной ячейки ---- */
    function setActive(idx) {
      idx = Math.max(0, Math.min(cells.length - 1, idx));
      activeIdx = idx;
      cells.forEach((c, i) => {
        if (i === idx) c.classList.add('is-active');
        else c.classList.remove('is-active');
      });
      const time = cells[idx].dataset.time || '08:30';
      display.forEach(el => { el.textContent = time; });
    }

    function scrollToIdx(idx, smooth) {
      const top = idx * CELL_HEIGHT;
      try {
        scroll.scrollTo({ top, behavior: smooth ? 'smooth' : 'auto' });
      } catch (e) {
        scroll.scrollTop = top;
      }
    }

    /* ---- Initial position — ставим scroll и active одновременно ---- */
    function initialize() {
      scroll.scrollTop = activeIdx * CELL_HEIGHT;
      setActive(activeIdx);
    }
    // Делаем после layout
    if ('requestAnimationFrame' in window) {
      requestAnimationFrame(initialize);
    } else {
      setTimeout(initialize, 0);
    }

    /* ---- Scroll handler — обновляем active по позиции ---- */
    let snapTimer = null;
    let scrolling = false;

    scroll.addEventListener('scroll', () => {
      scrolling = true;
      const idx = Math.round(scroll.scrollTop / CELL_HEIGHT);
      setActive(idx);

      // Re-snap после остановки скролла
      if (snapTimer) clearTimeout(snapTimer);
      snapTimer = setTimeout(() => {
        scrolling = false;
        scrollToIdx(activeIdx, true);
      }, 150);
    });

    /* ---- Click on cell — скроллим к ней ---- */
    cells.forEach((cell, idx) => {
      cell.addEventListener('click', () => {
        scrollToIdx(idx, true);
        // setActive вызовется через scroll listener
      });
    });

    /* ---- Wheel — преобразуем в scroll ---- */
    scroll.addEventListener('wheel', (e) => {
      e.preventDefault();
      scroll.scrollTop += e.deltaY;
    }, { passive: false });

    /* ---- Save/Cancel/Reset — надёжно через class на root ---- */
    function showSaved() {
      root.classList.add('is-saved');
      // Аналитика
      try {
        if (window.ym) {
          const counters = Object.keys(window).filter(k => /^ym\d+$/.test(k));
          if (counters[0]) window[counters[0]]('reachGoal', 'clock_saved');
        }
        window.dispatchEvent(new CustomEvent('edl:clock-saved', {
          detail: { time: cells[activeIdx]?.dataset.time }
        }));
      } catch (e) {}
    }

    function hideSaved() {
      root.classList.remove('is-saved');
    }

    if (saveBtn) {
      saveBtn.addEventListener('click', (e) => {
        e.preventDefault();
        showSaved();
      });
    }
    if (cancelBtn) {
      cancelBtn.addEventListener('click', (e) => {
        e.preventDefault();
        hideSaved();
      });
    }
    if (resetBtn) {
      resetBtn.addEventListener('click', (e) => {
        e.preventDefault();
        hideSaved();
        // Возвращаем фокус на picker через rAF чтобы дождаться transition
        requestAnimationFrame(() => {
          scroll.focus({ preventScroll: true });
        });
      });
    }

    /* ---- Клавиатурная навигация ---- */
    scroll.setAttribute('tabindex', '0');
    scroll.setAttribute('role', 'listbox');
    scroll.setAttribute('aria-label', 'Выберите время утренней сводки');

    scroll.addEventListener('keydown', (e) => {
      if (root.classList.contains('is-saved')) return;
      let next = activeIdx;
      if (e.key === 'ArrowDown') next = Math.min(cells.length - 1, activeIdx + 1);
      else if (e.key === 'ArrowUp') next = Math.max(0, activeIdx - 1);
      else if (e.key === 'Home') next = 0;
      else if (e.key === 'End') next = cells.length - 1;
      else if (e.key === 'Enter') { e.preventDefault(); showSaved(); return; }
      else return;
      e.preventDefault();
      scrollToIdx(next, true);
    });
  }


  /* ============== ЧАСТЬ 2: 3D-КАРУСЕЛЬ ============== */

  function initCarousel(root) {
    if (!root || root.__inited) return;
    root.__inited = true;

    const cards = Array.from(root.querySelectorAll('.carousel__card'));
    const dots = Array.from(root.querySelectorAll('.carousel__dot'));
    if (cards.length < 2) return;

    // 3 позиции по часовой стрелке (front → back-left → back-right → front)
    // Каждая карточка стартует в своей позиции
    const positions = ['pos-front', 'pos-back-left', 'pos-back-right'];
    let currentRotation = 0; // сколько раз провернули
    let interval = null;
    const ROTATION_MS = 4500;

    function applyPositions() {
      cards.forEach((card, i) => {
        positions.forEach(p => card.classList.remove(p));
        // i + currentRotation определяет какую позицию занимает карточка
        const posIdx = (i + currentRotation) % positions.length;
        card.classList.add(positions[posIdx]);
      });
      // Подсветка точки — какой dot соответствует переднему фронту
      // Передняя карточка — та, у которой posIdx === 0, т.е. i = -currentRotation mod 3
      const frontIdx = ((cards.length - currentRotation) % cards.length + cards.length) % cards.length;
      dots.forEach((dot, i) => {
        if (i === frontIdx) dot.classList.add('is-active');
        else dot.classList.remove('is-active');
      });
    }

    function rotate() {
      currentRotation = (currentRotation + 1) % positions.length;
      applyPositions();
    }

    function start() {
      stop();
      interval = setInterval(rotate, ROTATION_MS);
    }

    function stop() {
      if (interval) {
        clearInterval(interval);
        interval = null;
      }
    }

    /* Инициализация */
    applyPositions();
    start();

    /* Pause on hover */
    root.addEventListener('mouseenter', stop);
    root.addEventListener('mouseleave', start);

    /* Pause when off-screen (экономия батареи мобильных) */
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) start();
          else stop();
        });
      }, { threshold: 0.1 });
      observer.observe(root);
    }

    /* Клик по точке — переключиться к этой карточке */
    dots.forEach((dot, dotIdx) => {
      dot.setAttribute('role', 'button');
      dot.setAttribute('tabindex', '0');
      dot.setAttribute('aria-label', `Карточка ${dotIdx + 1}`);

      const handleSelect = () => {
        // Мы хотим что-бы карточка с индексом dotIdx стала на позицию front (pos-front).
        // Это значит (dotIdx + currentRotation) % 3 === 0
        // → currentRotation = (-dotIdx) mod 3
        currentRotation = ((positions.length - dotIdx) % positions.length + positions.length) % positions.length;
        applyPositions();
        start(); // restart timer
      };

      dot.addEventListener('click', handleSelect);
      dot.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleSelect();
        }
      });
    });
  }


  /* ============== BOOTSTRAP ============== */

  function start() {
    document.querySelectorAll('.clock').forEach(initClock);
    document.querySelectorAll('.carousel').forEach(initCarousel);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
