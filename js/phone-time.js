function updatePhoneTime() {
  const now = new Date();
  const timeStr = now.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit'
  });
  
  // Короткое название таймзоны
  const offsetMin = -now.getTimezoneOffset();
  const offsetH = Math.floor(Math.abs(offsetMin) / 60);
  const sign = offsetMin >= 0 ? '+' : '−';
  const tzShort = `UTC${sign}${offsetH}`;
  
  const timeEl = document.querySelector('.phone-time');
  const tzEl = document.querySelector('.phone-tz');
  
  if (timeEl) timeEl.textContent = timeStr;
  if (tzEl) tzEl.textContent = `сегодня · ${tzShort}`;
}

// Запуск и обновление каждые 30 секунд
document.addEventListener("DOMContentLoaded", () => {
    updatePhoneTime();
    setInterval(updatePhoneTime, 30000);
    initPhoneScenes();
});

// ──────────────────────────────────────────────────────────────────
// Phone scenes: «Один день фаундера» — 3 сцены автоциклируются.
// Pause on hover/focus, manual dot navigation, respects reduced-motion.
// ──────────────────────────────────────────────────────────────────
function initPhoneScenes() {
  const scenesEl = document.getElementById('phone-scenes');
  if (!scenesEl) return;

  const scenes = Array.from(scenesEl.querySelectorAll('.phone-scene'));
  const dots = Array.from(document.querySelectorAll('.phone-dot'));
  const labelEl = document.getElementById('phone-scene-label');
  const captionTextEl = document.getElementById('phone-caption-text');

  const meta = [
    { label: 'Сводка · 8:30',        caption: 'Утренняя сводка в кармане. Главные риски — за 3 минуты до первого совещания.' },
    { label: 'ИИ-консультант',       caption: 'Любой вопрос про маржу, CAC, runway — ответ цифрами, со ссылкой на источник.' },
    { label: 'Голосовая команда',    caption: 'Решения голосом из такси. Бот пишет CFO, ставит задачу, ждёт подтверждения.' }
  ];

  let i = 0;
  let timer = null;
  const PERIOD = 5400; // ms per scene

  function go(next, manual = false) {
    i = ((next % scenes.length) + scenes.length) % scenes.length;
    scenes.forEach((s, idx) => s.classList.toggle('is-active', idx === i));
    dots.forEach((d, idx) => d.classList.toggle('is-active', idx === i));
    if (labelEl && meta[i]) labelEl.textContent = meta[i].label;
    if (captionTextEl && meta[i]) {
      captionTextEl.style.opacity = '0';
      setTimeout(() => {
        captionTextEl.textContent = meta[i].caption;
        captionTextEl.style.opacity = '1';
      }, 220);
    }
    if (manual) restart();
  }

  function start() {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    stop();
    timer = setInterval(() => go(i + 1), PERIOD);
  }
  function stop() { if (timer) { clearInterval(timer); timer = null; } }
  function restart() { stop(); start(); }

  // Dot navigation
  dots.forEach((dot, idx) => {
    dot.addEventListener('click', () => {
      go(idx, true);
      if (typeof window.EDLTrack === 'function') {
        window.EDLTrack('hero_scene_clicked', { scene: idx });
      }
    });
  });

  // Pause on hover/focus inside phone
  const phone = document.getElementById('phone-mockup');
  if (phone) {
    phone.addEventListener('mouseenter', stop);
    phone.addEventListener('mouseleave', start);
    phone.addEventListener('focusin', stop);
    phone.addEventListener('focusout', start);
  }

  go(0);
  start();
}
