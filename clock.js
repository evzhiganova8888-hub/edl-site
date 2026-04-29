/* ===================================================================
   EDL Interactive Clock v1 — 30 апреля 2026
   ===================================================================
   Логика интерактивного будильника в секции «Принципы».

   Поведение:
   1. При загрузке — кнопка 08:30 уже отмечена как выбранная.
   2. Пользователь кликает на любую кнопку времени → она становится active.
   3. Через ~1.4 сек после выбора (или сразу по клику Сохранить) — запускается timeline.
   4. Timeline: 3 события появляются последовательно с задержкой 700мс.
   5. После 3-го события — fade-in CTA-блока.
   6. Кнопка «← Выбрать другое время» возвращает в picker-состояние.
   7. Уважает prefers-reduced-motion: показывает всё сразу, без анимации.

   Зависимостей нет. Vanilla ES6+. Безопасно встраивается в любой сайт.
   =================================================================== */

(function () {
  'use strict';

  function initEdlClock(root) {
    if (!root || root.__edlClockInited) return;
    root.__edlClockInited = true;

    const buttons   = root.querySelectorAll('.edl-clock__time-btn');
    const events    = root.querySelectorAll('.edl-clock__event');
    const cta       = root.querySelector('.edl-clock__cta');
    const display   = root.querySelectorAll('[data-clock-display]');
    const saveBtn   = root.querySelector('[data-clock-save]');
    const cancelBtn = root.querySelector('[data-clock-cancel]');
    const resetBtn  = root.querySelector('[data-clock-reset]');

    if (!buttons.length) return;

    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    let currentTime = '08:30';
    let autoRunTimer = null;
    let isRunning = false;

    /* ----- Helpers ----- */

    function updateDisplay(time) {
      currentTime = time;
      display.forEach(el => { el.textContent = time; });
    }

    function setSelected(btn) {
      buttons.forEach(b => {
        const isActive = b === btn;
        b.setAttribute('aria-pressed', String(isActive));
        b.setAttribute('aria-checked', String(isActive));
      });
      updateDisplay(btn.dataset.time);
    }

    function runTimeline() {
      if (isRunning) return;
      isRunning = true;
      root.classList.add('is-running');

      if (prefersReduced) {
        // Без анимации — показываем всё сразу
        events.forEach(ev => ev.classList.add('is-visible'));
        if (cta) cta.classList.add('is-visible');
        return;
      }

      // Поэтапное появление событий
      events.forEach((ev, i) => {
        setTimeout(() => {
          ev.classList.add('is-visible');
        }, 250 + i * 700);
      });

      // CTA — после последнего события
      const ctaDelay = 250 + events.length * 700 + 200;
      setTimeout(() => {
        if (cta) cta.classList.add('is-visible');
      }, ctaDelay);

      // Аналитика — отправляем событие в Я.Метрику если она есть
      try {
        if (window.ym && typeof window.ym === 'function') {
          // Берём первый счётчик из window
          const counters = Object.keys(window).filter(k => /^ym\d+$/.test(k));
          if (counters.length) {
            window[counters[0]]('reachGoal', 'clock_demo_played');
          }
        }
        // Универсальное событие
        window.dispatchEvent(new CustomEvent('edl:clock-played', { detail: { time: currentTime } }));
      } catch (e) { /* мягкий fail */ }
    }

    function resetTimeline() {
      isRunning = false;
      root.classList.remove('is-running');
      events.forEach(ev => ev.classList.remove('is-visible'));
      if (cta) cta.classList.remove('is-visible');
      if (autoRunTimer) {
        clearTimeout(autoRunTimer);
        autoRunTimer = null;
      }
    }

    function scheduleAutoRun() {
      if (autoRunTimer) clearTimeout(autoRunTimer);
      // Через 1.4с после последнего выбора — запуск timeline (если ещё не запущен)
      autoRunTimer = setTimeout(() => {
        if (!isRunning) runTimeline();
      }, 1400);
    }

    /* ----- Event handlers ----- */

    buttons.forEach(btn => {
      btn.addEventListener('click', () => {
        if (isRunning) return; // если уже играет — игнор
        setSelected(btn);
        scheduleAutoRun();
      });

      // Клавиатура: стрелки между radio-кнопками (стандарт WAI-ARIA)
      btn.addEventListener('keydown', (e) => {
        const idx = Array.from(buttons).indexOf(btn);
        let next = null;
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
          next = buttons[(idx + 1) % buttons.length];
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
          next = buttons[(idx - 1 + buttons.length) % buttons.length];
        }
        if (next) {
          e.preventDefault();
          next.focus();
          if (!isRunning) {
            setSelected(next);
            scheduleAutoRun();
          }
        }
      });
    });

    if (saveBtn) {
      saveBtn.addEventListener('click', () => {
        if (autoRunTimer) clearTimeout(autoRunTimer);
        runTimeline();
      });
    }

    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => {
        if (isRunning) {
          resetTimeline();
        }
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        resetTimeline();
        // Скроллим обратно к picker для удобства
        const picker = root.querySelector('.edl-clock__picker');
        if (picker) {
          picker.querySelector('[aria-pressed="true"]')?.focus({ preventScroll: true });
        }
      });
    }

    // Инициализация: дефолтная кнопка
    const defaultBtn = root.querySelector('.edl-clock__time-btn[data-default]') || buttons[0];
    if (defaultBtn) updateDisplay(defaultBtn.dataset.time);
  }

  /* ----- Bootstrap ----- */

  function init() {
    document.querySelectorAll('.edl-clock').forEach(initEdlClock);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
