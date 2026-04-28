/* =========================================================================
   EDL · main.js · v2.0
   Vanilla JS motion system. No dependencies.
   - IntersectionObserver for reveal animations
   - Hero word-by-word reveal
   - Magnetic CTA hover (desktop only)
   - Count-up numbers in stats
   - Sticky mobile CTA
   - FAQ accordion
   - Calendly modal
   - Header scroll behaviour
   - Architecture diagram draw-in
   ========================================================================= */

(function () {
  'use strict';

  const METRICA_ID = 'YOUR_COUNTER_ID';
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const isMobile = window.matchMedia('(max-width: 1023px)').matches;

  /* ── 1 · Header scroll ─────────────────────────────────────────────── */
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

  /* ── 2 · Mobile menu ───────────────────────────────────────────────── */
  const menuToggle = document.querySelector('[data-menu-toggle]');
  const mobileMenu = document.querySelector('.mobile-menu');
  if (menuToggle && mobileMenu) {
    menuToggle.addEventListener('click', () => {
      const isOpen = mobileMenu.classList.toggle('is-open');
      menuToggle.setAttribute('aria-expanded', String(isOpen));
      document.body.style.overflow = isOpen ? 'hidden' : '';
    });
    mobileMenu.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        mobileMenu.classList.remove('is-open');
        menuToggle.setAttribute('aria-expanded', 'false');
        document.body.style.overflow = '';
      });
    });
  }

  /* ── 3 · Hero word-by-word reveal ──────────────────────────────────── */
  function splitWords(el) {
    if (!el || reduceMotion) return;
    const html = el.innerHTML;
    // Split by words but preserve <span class="accent"> wrapping
    const wrapped = html.replace(/<span class="accent">(.*?)<\/span>/g, (_, inner) => {
      return `<span class="accent">${inner.split(' ').map((w, i) =>
        `<span class="word" style="animation-delay: ${(i + 1) * 0.08}s">${w}</span>`
      ).join(' ')}</span>`;
    });
    // Wrap remaining words outside accent
    el.innerHTML = wrapped.replace(/(?<!class="word"[^>]*>)([\wА-яЁё]+)(?![^<]*<\/span>)/g, (match, word) => {
      return word; // skip — accent already handled, rest gets simple animation
    });
    // Simpler approach: split top-level text into word spans
    const fragments = el.childNodes;
    let wordIndex = 0;
    fragments.forEach(node => {
      if (node.nodeType === Node.TEXT_NODE) {
        const words = node.textContent.split(/(\s+)/);
        const frag = document.createDocumentFragment();
        words.forEach(part => {
          if (part.trim()) {
            const span = document.createElement('span');
            span.className = 'word';
            span.style.animationDelay = `${wordIndex * 0.08}s`;
            span.textContent = part;
            frag.appendChild(span);
            wordIndex++;
          } else {
            frag.appendChild(document.createTextNode(part));
          }
        });
        node.parentNode.replaceChild(frag, node);
      }
    });
  }

  // Apply to hero title — only words, not the accent span (it has its own animation)
  const heroTitle = document.querySelector('[data-hero-title]');
  if (heroTitle && !reduceMotion) {
    // Wrap each top-level text word in <span class="word">
    const accent = heroTitle.querySelector('.accent');
    let accentHTML = '';
    if (accent) accentHTML = accent.outerHTML;

    let html = heroTitle.innerHTML;
    let delay = 0;

    // Split text outside accent into words
    if (accent) {
      const parts = html.split(accentHTML);
      const before = parts[0].trim().split(/(\s+)/).map(w => {
        if (w.trim()) {
          const d = (delay += 0.08).toFixed(2);
          return `<span class="word" style="animation-delay: ${d}s">${w}</span>`;
        }
        return w;
      }).join('');

      const after = (parts[1] || '').trim().split(/(\s+)/).map(w => {
        if (w.trim()) {
          const d = (delay += 0.08).toFixed(2);
          return `<span class="word" style="animation-delay: ${d}s">${w}</span>`;
        }
        return w;
      }).join('');

      heroTitle.innerHTML = before + ' ' + accentHTML + ' ' + after;
    } else {
      heroTitle.innerHTML = html.split(/(\s+)/).map(w => {
        if (w.trim()) {
          const d = (delay += 0.08).toFixed(2);
          return `<span class="word" style="animation-delay: ${d}s">${w}</span>`;
        }
        return w;
      }).join('');
    }
  }

  /* ── 4 · IntersectionObserver — reveal animations ──────────────────── */
  if ('IntersectionObserver' in window && !reduceMotion) {
    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          revealObserver.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.15,
      rootMargin: '0px 0px -10% 0px'
    });

    document.querySelectorAll('[data-reveal], [data-reveal-stagger]').forEach(el => {
      revealObserver.observe(el);
    });
  } else {
    // Fallback — show all
    document.querySelectorAll('[data-reveal], [data-reveal-stagger]').forEach(el => {
      el.classList.add('is-visible');
    });
  }

  /* ── 5 · Count-up numbers ──────────────────────────────────────────── */
  function easeOutQuart(t) {
    return 1 - Math.pow(1 - t, 4);
  }

  function animateCountUp(el, target, duration = 1600) {
    if (reduceMotion) {
      el.textContent = target;
      return;
    }
    const start = performance.now();
    const isFloat = String(target).includes('.');
    const targetNum = parseFloat(target);
    const fromNum = 0;

    function tick(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = easeOutQuart(progress);
      const current = fromNum + (targetNum - fromNum) * eased;

      el.textContent = isFloat ? current.toFixed(1) : Math.floor(current);

      if (progress < 1) {
        requestAnimationFrame(tick);
      } else {
        el.textContent = target;
      }
    }
    requestAnimationFrame(tick);
  }

  const statValues = document.querySelectorAll('[data-count]');
  if ('IntersectionObserver' in window && statValues.length) {
    const countObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const target = entry.target.dataset.count;
          animateCountUp(entry.target, target);
          countObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.5 });
    statValues.forEach(el => countObserver.observe(el));
  }

  /* ── 6 · Magnetic CTA buttons (desktop only) ───────────────────────── */
  if (!isMobile && !reduceMotion) {
    document.querySelectorAll('[data-magnetic]').forEach(btn => {
      btn.addEventListener('mousemove', (e) => {
        const rect = btn.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;
        const distance = Math.sqrt(x * x + y * y);
        const max = Math.max(rect.width, rect.height) / 2;
        const strength = Math.min(distance / max, 1);
        const moveX = (x / max) * 8 * strength;
        const moveY = (y / max) * 8 * strength;
        btn.style.transform = `translate(${moveX}px, ${moveY}px)`;
      });
      btn.addEventListener('mouseleave', () => {
        btn.style.transform = '';
      });
    });
  }

  /* ── 7 · Architecture diagram draw-in ──────────────────────────────── */
  const archSvg = document.querySelector('.arch-svg');
  if (archSvg && 'IntersectionObserver' in window) {
    const archObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const layers = archSvg.querySelectorAll('.arch-layer');
          const connectors = archSvg.querySelectorAll('.arch-connector');

          layers.forEach((layer, i) => {
            layer.style.opacity = '0';
            layer.style.transform = 'translateY(20px)';
            layer.style.transition = 'opacity 0.6s cubic-bezier(0.16,1,0.3,1), transform 0.6s cubic-bezier(0.16,1,0.3,1)';
            setTimeout(() => {
              layer.style.opacity = '1';
              layer.style.transform = 'translateY(0)';
            }, i * 200);
          });

          connectors.forEach((conn, i) => {
            conn.style.opacity = '0';
            conn.style.transition = 'opacity 0.4s ease-out';
            setTimeout(() => {
              conn.style.opacity = '1';
            }, 100 + i * 200);
          });

          archObserver.unobserve(archSvg);
        }
      });
    }, { threshold: 0.3 });
    archObserver.observe(archSvg);
  }

  /* ── 8 · FAQ accordion ─────────────────────────────────────────────── */
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    const trigger = item.querySelector('.faq-item__trigger');
    if (!trigger) return;
    trigger.addEventListener('click', () => {
      const isOpen = item.classList.contains('is-open');
      faqItems.forEach(i => {
        i.classList.remove('is-open');
        const t = i.querySelector('.faq-item__trigger');
        if (t) t.setAttribute('aria-expanded', 'false');
      });
      if (!isOpen) {
        item.classList.add('is-open');
        trigger.setAttribute('aria-expanded', 'true');
        track('faq_open', { id: trigger.dataset.faqId || 'unknown' });
      }
    });
  });

  /* ── 9 · Calendly modal ────────────────────────────────────────────── */
  const modal = document.getElementById('calendly-modal');
  const ctaButtons = document.querySelectorAll('[data-cta="demo"]');
  let calendlyLoaded = false;
  let calendlyInited = false;

  function initCalendlyWidget() {
    if (calendlyInited) return;
    if (!window.Calendly || typeof window.Calendly.initInlineWidget !== 'function') return;
    const container = modal && modal.querySelector('.calendly-inline-widget');
    if (!container) return;
    try {
      window.Calendly.initInlineWidget({
        url: container.dataset.url,
        parentElement: container
      });
      calendlyInited = true;
    } catch (e) {
      console.warn('Calendly init failed:', e);
    }
  }

  function loadCalendlyScript() {
    if (calendlyLoaded) {
      initCalendlyWidget();
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://assets.calendly.com/assets/external/widget.js';
    script.async = true;
    script.onload = initCalendlyWidget;
    document.body.appendChild(script);
    calendlyLoaded = true;
  }

  function openModal() {
    if (!modal) return;
    loadCalendlyScript();
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
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
      // Если модалка есть и JS работает — перехватываем и открываем модалку.
      // Если модалки нет (ошибка DOM) — даём href сработать как fallback в новую вкладку.
      if (!modal) return;
      // Cmd/Ctrl/middle-click — даём браузеру открыть Calendly в новой вкладке штатно.
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
      e.preventDefault();
      track('cta_demo_click', { location: btn.dataset.ctaLocation || 'unknown' });
      openModal();
    });
    // Прелоад Calendly script на первый hover/touch — экономит 200–500мс на самом клике.
    const preload = () => loadCalendlyScript();
    btn.addEventListener('mouseenter', preload, { once: true });
    btn.addEventListener('touchstart', preload, { once: true, passive: true });
    btn.addEventListener('focus', preload, { once: true });
  });

  if (modal) {
    modal.querySelectorAll('[data-modal-close]').forEach(el => {
      el.addEventListener('click', closeModal);
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !modal.hidden) closeModal();
    });
  }

  /* ── 10 · Sticky mobile CTA ────────────────────────────────────────── */
  const stickyCta = document.querySelector('.sticky-cta');
  const heroSection = document.querySelector('.hero');
  if (stickyCta && heroSection && isMobile) {
    const stickyObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        // When hero is OUT of view, show sticky CTA
        if (!entry.isIntersecting) {
          stickyCta.classList.add('is-visible');
        } else {
          stickyCta.classList.remove('is-visible');
        }
      });
    }, { threshold: 0.05 });
    stickyObserver.observe(heroSection);
  }

  /* ── 11 · Smooth anchor scroll ─────────────────────────────────────── */
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const href = this.getAttribute('href');
      if (href === '#' || href.length < 2) return;
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
      }
    });
  });

  /* ── 12 · Analytics ────────────────────────────────────────────────── */
  function track(goalName, params) {
    if (typeof window.ym === 'function' && METRICA_ID !== 'YOUR_COUNTER_ID') {
      try {
        window.ym(METRICA_ID, 'reachGoal', goalName, params || {});
      } catch (e) {
        console.warn('Metrica track failed:', e);
      }
    } else {
      console.log('[track]', goalName, params || {});
    }
  }

  // Scroll depth
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

  // Outbound links
  document.querySelectorAll('a[href^="http"]').forEach(link => {
    link.addEventListener('click', () => {
      try {
        const url = new URL(link.href);
        if (url.host !== window.location.host) {
          track('outbound_click', { host: url.host });
        }
      } catch (e) {}
    });
  });

  /* ── 13 · Lead magnet click tracking ───────────────────────────────── */
  document.querySelectorAll('[data-lead-magnet]').forEach(link => {
    link.addEventListener('click', () => {
      track('lead_magnet_click');
    });
  });

})();

/* =========================================================================
   v2.1 ADDITIONS — feedback iteration
   ========================================================================= */

(function () {
  'use strict';
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── 14 · Animated hero mock — 12s cinematic cycle (4s per frame) ──── */
  const heroMockWrap = document.querySelector('[data-hero-mock-wrap]');
  const heroMock = document.querySelector('[data-hero-mock]');
  if (heroMock && !reduceMotion) {
    const frames = heroMock.querySelectorAll('.hero-mock__frame');
    const dots = heroMock.querySelectorAll('.hero-mock__dot');
    const labels = heroMockWrap ? heroMockWrap.querySelectorAll('.hero-label') : [];
    const cursor = heroMock.querySelector('[data-cursor]');
    let currentFrame = 0;
    let cycleInterval;

    function showFrame(index) {
      frames.forEach((f, i) => f.classList.toggle('is-active', i === index));
      dots.forEach((d, i) => d.classList.toggle('is-active', i === index));
      labels.forEach((l, i) => l.classList.toggle('is-active', i === index));
    }

    function startCycle() {
      // Activate cursor
      if (cursor) cursor.classList.add('is-visible');

      // 4 seconds per frame for cinematic Apple-style pacing
      cycleInterval = setInterval(() => {
        currentFrame = (currentFrame + 1) % frames.length;
        showFrame(currentFrame);
      }, 4000);
    }

    // Start when hero is visible
    if ('IntersectionObserver' in window) {
      const heroObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            if (!cycleInterval) {
              showFrame(0); // initialize labels
              startCycle();
            }
          } else {
            clearInterval(cycleInterval);
            cycleInterval = null;
            if (cursor) cursor.classList.remove('is-visible');
          }
        });
      }, { threshold: 0.3 });
      heroObserver.observe(heroMock);
    } else {
      showFrame(0);
      startCycle();
    }

    // Allow click on dots
    dots.forEach((dot, i) => {
      dot.addEventListener('click', () => {
        currentFrame = i;
        showFrame(i);
        clearInterval(cycleInterval);
        startCycle();
      });
    });
  }

  /* ── 15 · ICP flip cards — click to flip ────────────────────────────── */
  document.querySelectorAll('[data-flip]').forEach(card => {
    card.addEventListener('click', () => {
      card.classList.toggle('is-flipped');
    });
    // Keyboard: Enter or Space
    card.setAttribute('tabindex', '0');
    card.setAttribute('role', 'button');
    card.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        card.classList.toggle('is-flipped');
      }
    });
  });

  /* ── 16 · Newsletter form — submit to Apps Script ───────────────────── */
  const NEWSLETTER_URL = 'https://script.google.com/macros/s/AKfycbx9z6AecRYinB1eUZYQd90Y_QigU5xv6AO-uFw835shoQt-w79q1kjFzbRHWZ-CP2Z_Kg/exec';
  document.querySelectorAll('[data-newsletter-form]').forEach(form => {
    const success = form.querySelector('[data-newsletter-success]');
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = form.querySelector('input[name="email"]').value.trim();
      if (!email || !email.includes('@')) {
        alert('Проверьте email');
        return;
      }
      const btn = form.querySelector('button[type="submit"]');
      const original = btn.textContent;
      btn.disabled = true;
      btn.textContent = 'Отправляю...';

      try {
        // Apps Script accepts no-cors POST with form data
        const formData = new FormData();
        formData.append('email', email);
        formData.append('source', 'newsletter');

        await fetch(NEWSLETTER_URL, {
          method: 'POST',
          body: formData,
          mode: 'no-cors'
        });

        // no-cors means we can't read response, so we assume success
        form.querySelector('.newsletter-form__row').style.display = 'none';
        form.querySelector('.newsletter-form__hint').style.display = 'none';
        if (success) success.hidden = false;
        if (typeof window.ym === 'function') {
          try { window.ym(window.METRICA_ID || 'YOUR_COUNTER_ID', 'reachGoal', 'newsletter_subscribe'); } catch(e){}
        }
        console.log('[track] newsletter_subscribe', { email });
      } catch (err) {
        btn.disabled = false;
        btn.textContent = original;
        alert('Что-то пошло не так. Попробуйте ещё раз или напишите в Telegram.');
      }
    });
  });

  /* ── Readiness meter · 5 вопросов · скоринг 0–10 · 3 уровня результата ─ */
  const meter = document.querySelector('[data-readiness-meter]');
  if (meter) {
    const questionsList = meter.querySelector('[data-meter-questions]');
    const fillEl   = meter.querySelector('[data-meter-fill]');
    const resultEl = meter.querySelector('[data-meter-result]');
    const scoreEl  = meter.querySelector('[data-meter-score]');
    const textEl   = meter.querySelector('[data-meter-text]');
    const ctaEl    = meter.querySelector('[data-meter-cta]');
    const answers = {};

    function recomputeMeter() {
      let total = 0;
      let answered = 0;
      Object.values(answers).forEach(v => { total += v; answered++; });
      const totalQs = meter.querySelectorAll('[data-q]').length;

      // Заполнение шкалы — пропорционально текущему счёту относительно максимума.
      // Максимум = 10 (5 вопросов × 2 балла за «Да»).
      const pct = Math.min(100, (total / 10) * 100);
      fillEl.style.width = pct + '%';

      // Показываем результат только когда отвечены все вопросы.
      if (answered < totalQs) {
        resultEl.hidden = true;
        return;
      }

      let level, text, cta;
      if (total <= 3) {
        level = 'early';
        text = 'Возможно, ещё рано — система такого уровня заметно проявит себя при выручке от 30 млн ₽ и команде от 5 человек. Пока — почитайте Telegram, посмотрите, как мы работаем.';
        cta = '<a href="https://t.me/elephantdreamscommunity" target="_blank" rel="noopener noreferrer" class="is-secondary">Канал EDL в&nbsp;Telegram&nbsp;→</a>';
      } else if (total <= 7) {
        level = 'fit';
        text = 'Похоже на наш кейс. Приходите на бесплатное демо — за 30 минут покажем нашу систему и обсудим, что из этого подойдёт под ваш контекст.';
        cta = '<a href="https://calendly.com/evzhiganova8888/30min" target="_blank" rel="noopener noreferrer" data-cta="demo" data-cta-location="meter">Записаться на демо&nbsp;→</a>';
      } else {
        level = 'ready';
        text = 'Точно ваш формат. На демо покажем систему и сразу обсудим формат диагностики или спринта под ваш бизнес.';
        cta = '<a href="https://calendly.com/evzhiganova8888/30min" target="_blank" rel="noopener noreferrer" data-cta="demo" data-cta-location="meter-ready">Записаться на демо системы&nbsp;→</a>';
      }

      scoreEl.textContent = total;
      textEl.textContent = text;
      ctaEl.innerHTML = cta;
      resultEl.hidden = false;

      // Аналитика — когда тест завершён.
      try {
        if (typeof window.ym === 'function' && window.METRICA_ID && window.METRICA_ID !== 'YOUR_COUNTER_ID') {
          window.ym(window.METRICA_ID, 'reachGoal', 'meter_complete', { score: total, level: level });
        }
      } catch (e) {}
      console.log('[track] meter_complete', { score: total, level: level });
    }

    questionsList.addEventListener('click', (e) => {
      const btn = e.target.closest('.icp-meter__btn');
      if (!btn) return;
      const q = btn.closest('[data-q]');
      if (!q) return;
      const qId = q.dataset.q;
      const value = parseInt(btn.dataset.answer, 10);

      // Снимаем выделение с других кнопок этого вопроса
      q.querySelectorAll('.icp-meter__btn').forEach(b => b.classList.remove('is-selected'));
      btn.classList.add('is-selected');
      answers[qId] = value;
      recomputeMeter();
    });
  }

  /* ── Method layers · stagger reveal на скролле ────────────────────────── */
  const methodLayersContainer = document.querySelector('[data-method-layers]');
  const reduceMotionMethod = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (methodLayersContainer && 'IntersectionObserver' in window) {
    const layerObserver = new IntersectionObserver((entries, obs) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        // CSS transition-delay через --layer-i делает stagger автоматически.
        entry.target.querySelectorAll('[data-method-layer]')
          .forEach(layer => layer.classList.add('is-visible'));
        obs.unobserve(entry.target);
      });
    }, { threshold: 0.25, rootMargin: '0px 0px -10% 0px' });
    layerObserver.observe(methodLayersContainer);
  } else if (methodLayersContainer) {
    methodLayersContainer.querySelectorAll('[data-method-layer]')
      .forEach(l => l.classList.add('is-visible'));
  }

  /* ── Method principles · reveal с доп. задержкой после слоёв ─────────── */
  const principlesList = document.querySelector('[data-principles-list]');
  if (principlesList && 'IntersectionObserver' in window) {
    const pObserver = new IntersectionObserver((entries, obs) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        // Доп. задержка: глаз переключается с архитектуры на смысл.
        setTimeout(() => {
          entry.target.querySelectorAll('[data-principle]')
            .forEach(p => p.classList.add('is-visible'));
        }, 200);
        obs.unobserve(entry.target);
      });
    }, { threshold: 0.3, rootMargin: '0px 0px -10% 0px' });
    pObserver.observe(principlesList);
  } else if (principlesList) {
    principlesList.querySelectorAll('[data-principle]')
      .forEach(p => p.classList.add('is-visible'));
  }

  /* ── Smooth scroll к #method из Authority Anchor ─────────────────────── */
  document.querySelectorAll('[data-method-scroll]').forEach(link => {
    link.addEventListener('click', (e) => {
      const href = link.getAttribute('href');
      if (!href || !href.startsWith('#')) return;
      const target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();
      const headerEl = document.querySelector('.header');
      const headerH = headerEl ? headerEl.offsetHeight : 80;
      const top = target.getBoundingClientRect().top + window.scrollY - headerH - 16;
      if (reduceMotionMethod) {
        window.scrollTo(0, top);
      } else {
        window.scrollTo({ top: top, behavior: 'smooth' });
      }
    });
  });

})();
