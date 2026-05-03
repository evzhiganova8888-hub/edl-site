/* EDL OS — Main JavaScript */
(function() {
  'use strict';

  /* ── Mobile Nav ── */
  const burger = document.getElementById('burger');
  const mobileNav = document.getElementById('mobile-nav');
  if (burger) {
    burger.addEventListener('click', () => {
      mobileNav.classList.toggle('is-open');
    });
  }
  window.closeMobileNav = function() {
    if (mobileNav) mobileNav.classList.remove('is-open');
  };

  /* ── Hero TG Bot Animation ── */
  const heroTgBody = document.getElementById('hero-tg-body');
  if (heroTgBody) {
    const msgs = heroTgBody.querySelectorAll('.tg-msg, .tg-inline-btns');
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          msgs.forEach(msg => {
            const delay = parseInt(msg.dataset.delay || 0);
            setTimeout(() => msg.classList.add('is-visible'), delay);
          });
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.3 });
    observer.observe(heroTgBody);
  }

  /* ── Counter Animation (Live Proof) ── */
  document.querySelectorAll('.stat-block__number').forEach(el => {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const target = el.dataset.target;
          const suffix = el.dataset.suffix || '';
          const type = el.dataset.type;
          if (type === 'time') {
            el.textContent = target;
          } else {
            const end = parseInt(target);
            let current = 0;
            const step = Math.max(1, Math.floor(end / 30));
            const timer = setInterval(() => {
              current += step;
              if (current >= end) { current = end; clearInterval(timer); }
              el.textContent = current + suffix;
            }, 20);
          }
          observer.unobserve(el);
        }
      });
    }, { threshold: 0.5 });
    observer.observe(el);
  });

  /* ── Trigger Cards Click → Scroll ── */
  document.querySelectorAll('[data-scroll-to]').forEach(card => {
    card.addEventListener('click', () => {
      const target = document.getElementById(card.dataset.scrollTo);
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  });

  /* ── Killer #1: TG Commands ── */
  const cmdCash = document.getElementById('cmd-cash');
  const cmdLeads = document.getElementById('cmd-leads');
  if (cmdCash) {
    cmdCash.addEventListener('click', () => {
      document.getElementById('resp-cash').classList.add('is-visible');
    });
  }
  if (cmdLeads) {
    cmdLeads.addEventListener('click', () => {
      document.getElementById('resp-leads').classList.add('is-visible');
    });
  }

  /* ── Killer #2: AI Suggestions ── */
  document.querySelectorAll('.ai-suggestion-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      // Reset all
      document.querySelectorAll('.ai-suggestion-btn').forEach(b => b.classList.remove('is-active'));
      document.querySelectorAll('.ai-response').forEach(r => r.classList.remove('is-visible'));
      // Activate
      btn.classList.add('is-active');
      const resp = document.getElementById('ai-resp-' + btn.dataset.answer);
      if (resp) {
        resp.classList.add('is-visible');
        // Streaming text effect
        const fullText = resp.textContent;
        resp.textContent = '';
        resp.classList.add('is-visible');
        let i = 0;
        const cursor = document.createElement('span');
        cursor.className = 'typing-cursor';
        resp.appendChild(cursor);
        const typeInterval = setInterval(() => {
          if (i < fullText.length) {
            resp.insertBefore(document.createTextNode(fullText[i]), cursor);
            i++;
          } else {
            clearInterval(typeInterval);
            setTimeout(() => cursor.remove(), 1000);
          }
        }, 12);
      }
    });
  });

  /* ── Tabs (AI Examples + Battle) ── */
  document.querySelectorAll('.tabs').forEach(tabContainer => {
    const buttons = tabContainer.querySelectorAll('.tab-btn');
    buttons.forEach(btn => {
      btn.addEventListener('click', () => {
        const tabId = btn.dataset.tab;
        // Deactivate siblings
        buttons.forEach(b => { b.classList.remove('is-active'); b.setAttribute('aria-selected', 'false'); });
        btn.classList.add('is-active');
        btn.setAttribute('aria-selected', 'true');
        // Show panel
        const parent = tabContainer.closest('section') || tabContainer.parentElement;
        parent.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('is-active'));
        const panel = document.getElementById(tabId);
        if (panel) panel.classList.add('is-active');
      });
    });
  });

  /* ── FAQ Accordion ── */
  document.querySelectorAll('.faq-item__q').forEach(btn => {
    btn.addEventListener('click', () => {
      const item = btn.closest('.faq-item');
      const isOpen = item.classList.contains('is-open');
      // Close all
      document.querySelectorAll('.faq-item').forEach(i => {
        i.classList.remove('is-open');
        i.querySelector('.faq-item__q').setAttribute('aria-expanded', 'false');
      });
      // Toggle current
      if (!isOpen) {
        item.classList.add('is-open');
        btn.setAttribute('aria-expanded', 'true');
      }
    });
  });

  /* ── Smooth scroll for anchor links ── */
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', (e) => {
      const targetId = link.getAttribute('href').slice(1);
      if (!targetId) return;
      const target = document.getElementById(targetId);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth' });
        closeMobileNav();
      }
    });
  });

  /* ── Fast-Track JTBD Logic ── */
  const jtbdCheckboxes = document.querySelectorAll('.jtbd-toggle input');
  const ftSolution = document.getElementById('ft-solution');
  
  if (jtbdCheckboxes.length > 0 && ftSolution) {
    const defaultText = 'Отметьте хотя бы один пункт слева, чтобы увидеть решение.';
    
    jtbdCheckboxes.forEach(cb => {
      cb.addEventListener('change', () => {
        const checked = Array.from(jtbdCheckboxes).filter(i => i.checked).map(i => i.value);
        
        if (checked.length === 0) {
          ftSolution.textContent = defaultText;
          ftSolution.style.color = 'var(--color-tangerine)';
          return;
        }
        
        ftSolution.style.color = 'var(--color-gray-900)';
        let solutionText = '';
        
        if (checked.includes('reports') || checked.includes('margin')) {
          solutionText += '1. Внедряем автоматический P&L и Cashflow на базе ваших 1С/банков. ';
        }
        if (checked.includes('leads') || checked.includes('focus')) {
          solutionText += '2. Подключаем CRM с AI-скорингом и пушами в Telegram по горячим лидам. ';
        }
        if (checked.length >= 3) {
          solutionText += '3. Настраиваем утреннюю AI-сводку (запас денег, риски, фокус) лично для вас.';
        }
        
        if (solutionText === '') {
            solutionText = 'Собираем инфраструктуру под ключ: CRM + Дашборды + Telegram-бот.';
        }
        
        ftSolution.textContent = solutionText;
      });
    });
  }

  /* ── Floating TG Button Visibility ── */
  const floatingTg = document.getElementById('floating-tg');
  if (floatingTg) {
    window.addEventListener('scroll', () => {
      if (window.scrollY > 500) {
        floatingTg.classList.add('is-visible');
      } else {
        floatingTg.classList.remove('is-visible');
      }
    }, { passive: true });
  }

  /* ── Header scroll effect ── */
  let lastScroll = 0;
  window.addEventListener('scroll', () => {
    const header = document.getElementById('header');
    if (!header) return;
    const currentScroll = window.scrollY;
    if (currentScroll > 100) {
      header.style.boxShadow = '0 1px 8px rgba(0,0,0,0.08)';
    } else {
      header.style.boxShadow = 'none';
    }
    lastScroll = currentScroll;
  }, { passive: true });

})();
