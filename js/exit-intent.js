(function() {
  'use strict';

  const DISMISSED_KEY = 'edl_exit_intent_dismissed';

  if (sessionStorage.getItem(DISMISSED_KEY)) return;

  const overlay = document.createElement('div');
  overlay.className = 'exit-intent-overlay';
  overlay.innerHTML = `
    <div class="exit-intent-modal">
      <button class="exit-intent-close" aria-label="Закрыть">&times;</button>
      <div class="exit-intent-icon">📄</div>
      <h2 class="exit-intent-title">Уже уходите?</h2>
      <p class="exit-intent-text">Скачайте PDF-руководство со сравнением всех 5 продуктов EDL OS на одной странице. Это поможет вам выбрать правильный путь для масштабирования бизнеса.</p>
      <a href="/assets/pdf/edl-product-ladder.pdf" class="exit-intent-btn" download>Скачать PDF-руководство</a>
    </div>
  `;
  document.body.appendChild(overlay);

  const closeBtn = overlay.querySelector('.exit-intent-close');

  function dismiss() {
    overlay.classList.remove('is-visible');
    sessionStorage.setItem(DISMISSED_KEY, 'true');
    setTimeout(() => overlay.remove(), 300);
  }

  closeBtn.addEventListener('click', dismiss);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) dismiss();
  });
  
  overlay.querySelector('.exit-intent-btn').addEventListener('click', () => {
    window.EDLTrack && window.EDLTrack('exit_intent_pdf_downloaded');
    dismiss();
  });

  function triggerExitIntent() {
    overlay.classList.add('is-visible');
    window.EDLTrack && window.EDLTrack('exit_intent_shown');
  }

  const onMouseLeave = (e) => {
    if (e.clientY < 0) {
      triggerExitIntent();
      document.removeEventListener('mouseleave', onMouseLeave);
    }
  };

  let lastScrollY = window.scrollY;
  const onScroll = () => {
    const currentScrollY = window.scrollY;
    const scrollSpeed = currentScrollY - lastScrollY;
    lastScrollY = currentScrollY;
    
    // Fast upward scroll near the top of the page
    if (scrollSpeed < -40 && currentScrollY < 300) {
      triggerExitIntent();
      window.removeEventListener('scroll', onScroll);
    }
  };

  document.addEventListener('mouseleave', onMouseLeave);
  
  // Mobile fallback
  if (window.innerWidth <= 768) {
    window.addEventListener('scroll', onScroll, {passive: true});
  }
})();
