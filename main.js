/* ========================================================================
   EDL · main.js
   v1.0 · 2026-04-26
   Все скрипты в одном файле. Vanilla JS, без зависимостей.
   ======================================================================== */

(function () {
  'use strict';

  // ─── Yandex.Metrica counter ID — заменить на реальный ID после регистрации ───
  const METRICA_ID = 'YOUR_COUNTER_ID';

  // ─── 1. Header scroll behaviour ──────────────────────────────────────
  const header = document.querySelector('.header');
  if (header) {
    let scrolled = false;
    const onScroll = () => {
      const isScrolled = window.scrollY > 24;
      if (isScrolled !== scrolled) {
        scrolled = isScrolled;
        header.classList.toggle('is-scrolled', isScrolled);
      }
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  // ─── 2. Mobile menu toggle ───────────────────────────────────────────
  const menuToggle = document.querySelector('[data-menu-toggle]');
  const mobileMenu = document.querySelector('.mobile-menu');
  if (menuToggle && mobileMenu) {
    menuToggle.addEventListener('click', () => {
      const isOpen = mobileMenu.classList.toggle('is-open');
      menuToggle.setAttribute('aria-expanded', String(isOpen));
      document.body.style.overflow = isOpen ? 'hidden' : '';
    });
    // Close on link click
    mobileMenu.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        mobileMenu.classList.remove('is-open');
        menuToggle.setAttribute('aria-expanded', 'false');
        document.body.style.overflow = '';
      });
    });
  }

  // ─── 3. FAQ accordion ────────────────────────────────────────────────
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    const trigger = item.querySelector('.faq-item__trigger');
    if (!trigger) return;
    trigger.addEventListener('click', () => {
      const isOpen = item.classList.contains('is-open');
      // Close all
      faqItems.forEach(i => {
        i.classList.remove('is-open');
        const t = i.querySelector('.faq-item__trigger');
        if (t) t.setAttribute('aria-expanded', 'false');
      });
      // Open clicked (if it wasn't open)
      if (!isOpen) {
        item.classList.add('is-open');
        trigger.setAttribute('aria-expanded', 'true');
        track('faq_open', { id: trigger.dataset.faqId || 'unknown' });
      }
    });
  });

  // ─── 4. Calendly modal ───────────────────────────────────────────────
  const modal = document.getElementById('calendly-modal');
  const ctaButtons = document.querySelectorAll('[data-cta="demo"]');
  let calendlyLoaded = false;

  function loadCalendlyScript() {
    if (calendlyLoaded) return;
    const script = document.createElement('script');
    script.src = 'https://assets.calendly.com/assets/external/widget.js';
    script.async = true;
    document.body.appendChild(script);
    calendlyLoaded = true;
  }

  function openModal() {
    if (!modal) return;
    loadCalendlyScript();
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
    // Focus management
    const closeBtn = modal.querySelector('[data-modal-close]');
    if (closeBtn) closeBtn.focus();
    track('cta_calendly_open');
  }

  function closeModal() {
    if (!modal) return;
    modal.hidden = true;
    document.body.style.overflow = '';
  }

  ctaButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      // If it's an <a> with href, prevent default
      if (btn.tagName === 'A') e.preventDefault();
      track('cta_demo_click', { location: btn.dataset.ctaLocation || 'unknown' });
      openModal();
    });
  });

  if (modal) {
    modal.querySelectorAll('[data-modal-close]').forEach(el => {
      el.addEventListener('click', closeModal);
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !modal.hidden) closeModal();
    });
  }

  // ─── 5. Analytics tracking ───────────────────────────────────────────

  // Wrapper that's safe even if Метрика ещё не загружена
  function track(goalName, params) {
    if (typeof window.ym === 'function' && METRICA_ID !== 'YOUR_COUNTER_ID') {
      try {
        window.ym(METRICA_ID, 'reachGoal', goalName, params || {});
      } catch (e) {
        console.warn('Metrica track failed:', e);
      }
    } else {
      // Лог в консоль на этапе разработки — увидеть, что ивенты ловятся
      console.log('[track]', goalName, params || {});
    }
  }

  // Scroll depth tracking (50%, 75%, 100%)
  const scrollMarkers = { 50: false, 75: false, 100: false };
  let scrollTrackingTimeout;

  function checkScrollDepth() {
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    if (docHeight <= 0) return;
    const percent = (window.scrollY / docHeight) * 100;
    [50, 75, 100].forEach(threshold => {
      if (percent >= threshold && !scrollMarkers[threshold]) {
        scrollMarkers[threshold] = true;
        track(`scroll_${threshold}`);
      }
    });
  }

  window.addEventListener('scroll', () => {
    clearTimeout(scrollTrackingTimeout);
    scrollTrackingTimeout = setTimeout(checkScrollDepth, 200);
  }, { passive: true });

  // Track outbound links (Telegram, Calendly direct, etc.)
  document.querySelectorAll('a[href^="http"]').forEach(link => {
    link.addEventListener('click', () => {
      const url = new URL(link.href);
      if (url.host !== window.location.host) {
        track('outbound_click', { host: url.host, href: link.href });
      }
    });
  });

  // ─── 6. Smooth scroll for anchor links ───────────────────────────────
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const href = this.getAttribute('href');
      if (href === '#' || href.length < 2) return;
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // ─── 7. Lazy-load video (если есть в hero) ───────────────────────────
  const lazyVideos = document.querySelectorAll('video[data-lazy]');
  if (lazyVideos.length && 'IntersectionObserver' in window) {
    const videoObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const video = entry.target;
          const sources = video.querySelectorAll('source[data-src]');
          sources.forEach(source => {
            source.src = source.dataset.src;
            source.removeAttribute('data-src');
          });
          video.load();
          video.play().catch(() => { /* autoplay denied — ok */ });
          videoObserver.unobserve(video);
        }
      });
    }, { rootMargin: '0px 0px -100px 0px' });
    lazyVideos.forEach(v => videoObserver.observe(v));
  }

})();
