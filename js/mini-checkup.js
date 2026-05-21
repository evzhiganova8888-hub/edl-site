/**
 * mini-checkup.js — Mini-Чекап v2 виджет (multiple-choice 14 шагов).
 * Встраивается в .edl-chat-window через bot-widget.js.
 * Использует mini-checkup-engine.js + mini-checkup-canon.json.
 */
(function () {
  'use strict';

  const STORAGE_KEY = 'edl_widget_quiz_v2';
  const API_URL = '/api/quiz/submit';
  const BOT_USERNAME = 'edl_os_bot';
  const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Ждём, пока оба скрипта и DOM готовы
  function waitForDeps(cb) {
    const MAX = 30; let tries = 0;
    const iv = setInterval(function () {
      if (window.MiniCheckupEngine && document.querySelector('.edl-chat-window')) {
        clearInterval(iv);
        cb();
      } else if (++tries > MAX) {
        clearInterval(iv);
      }
    }, 200);
  }

  // ── Загрузка канона ───────────────────────────────────────────────────────
  function loadCanon(cb) {
    if (window._edlCanon) return cb(window._edlCanon);
    fetch('/js/mini-checkup-canon.json')
      .then(r => r.json())
      .then(data => {
        window._edlCanon = data;
        MiniCheckupEngine.setCanon(data);
        cb(data);
      })
      .catch(function () { cb(null); });
  }

  // ── State ─────────────────────────────────────────────────────────────────
  function defaultState() {
    return {
      phase: 'p1',
      segment: null,
      p2Option: null,
      answers: {},
      startTs: Date.now(),
      quizSessionId: null,
      result: null,
    };
  }

  function loadState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const s = JSON.parse(raw);
      // Expire after 24h
      if (!s.startTs || Date.now() - s.startTs > 86400000) return null;
      return s;
    } catch (e) { return null; }
  }

  function saveState(s) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch (e) {}
  }

  // ── Render helpers ────────────────────────────────────────────────────────
  function widget() { return document.querySelector('.edl-chat-window'); }

  function setContent(html) {
    const w = widget();
    if (!w) return;
    let inner = w.querySelector('.edl-widget-quiz-inner');
    if (!inner) {
      inner = document.createElement('div');
      inner.className = 'edl-widget-quiz-inner';
      inner.style.cssText = [
        'height:100%', 'overflow-y:auto', 'display:flex',
        'flex-direction:column', 'font-family:inherit',
      ].join(';');
      // Replace widget body content
      const body = w.querySelector('.edl-chat-body') || w;
      body.innerHTML = '';
      body.appendChild(inner);
    }
    inner.innerHTML = html;
    if (!REDUCED_MOTION) {
      inner.style.opacity = '0';
      requestAnimationFrame(() => {
        inner.style.transition = 'opacity 0.2s ease';
        inner.style.opacity = '1';
      });
    }
  }

  const CSS = `
    .wq { padding: 16px; }
    .wq-prog { height: 3px; background: #E5E7EB; border-radius: 2px; margin-bottom: 14px; overflow: hidden; }
    .wq-prog-fill { height: 100%; background: #F97316; transition: width 0.3s; border-radius: 2px; }
    .wq-label { font-size: 0.7rem; font-weight: 600; color: #9CA3AF; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }
    .wq-q { font-size: 1rem; font-weight: 700; color: #111827; margin-bottom: 14px; line-height: 1.4; }
    .wq-opts { display: flex; flex-direction: column; gap: 8px; }
    .wq-opt { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border: 1.5px solid #E5E7EB; border-radius: 8px; cursor: pointer; font-size: 0.875rem; font-weight: 500; color: #374151; transition: border-color .15s, background .15s; min-height: 48px; }
    .wq-opt:hover, .wq-opt.sel { border-color: #F97316; background: #FFF7ED; }
    .wq-radio { width: 16px; height: 16px; border-radius: 50%; border: 2px solid #D1D5DB; flex-shrink: 0; display: flex; align-items: center; justify-content: center; background: #fff; transition: border-color .15s; }
    .wq-opt.sel .wq-radio { border-color: #F97316; background: #F97316; }
    .wq-dot { width: 6px; height: 6px; border-radius: 50%; background: #fff; opacity: 0; }
    .wq-opt.sel .wq-dot { opacity: 1; }
    .wq-nav { display: flex; justify-content: space-between; align-items: center; margin-top: 14px; }
    .wq-back { background: none; border: none; color: #9CA3AF; font-size: 0.8rem; cursor: pointer; padding: 4px 0; }
    .wq-link { background: none; border: none; color: #9CA3AF; font-size: 0.8rem; cursor: pointer; text-decoration: underline; }
    .wq-result { padding: 16px; }
    .wq-score { text-align: center; padding: 20px; border-radius: 12px; margin-bottom: 14px; }
    .wq-score-num { font-size: 3.5rem; font-weight: 800; line-height: 1; }
    .wq-cat { font-size: 0.85rem; font-weight: 600; margin-top: 4px; }
    .wq-bm { background: #F0F9FF; border: 1px solid #BAE6FD; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; font-size: 0.825rem; line-height: 1.5; }
    .wq-gp { border: 1px solid #E5E7EB; border-radius: 8px; padding: 12px; margin-bottom: 8px; }
    .wq-gp-num { font-size: 0.7rem; font-weight: 700; color: #F97316; text-transform: uppercase; margin-bottom: 4px; }
    .wq-gp-short { font-weight: 700; font-size: 0.875rem; margin-bottom: 4px; }
    .wq-gp-act { font-size: 0.8rem; color: #6B7280; line-height: 1.5; }
    .wq-cta-p { display: block; background: #F97316; color: #fff; font-weight: 700; text-align: center; padding: 14px; border-radius: 10px; text-decoration: none; margin-top: 16px; font-size: 0.9rem; }
    .wq-cta-full { display: block; text-align: center; color: #9CA3AF; font-size: 0.8rem; margin-top: 10px; text-decoration: underline; cursor: pointer; background: none; border: none; width: 100%; }
  `;

  function injectStyles() {
    if (document.getElementById('edl-wq-styles')) return;
    const s = document.createElement('style');
    s.id = 'edl-wq-styles';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  // ── Render functions ──────────────────────────────────────────────────────
  const TOTAL = 14;

  function pct(phase) {
    if (phase === 'p1') return 7;
    if (phase === 'p2') return 14;
    const m = /^q(\d+)$/.exec(phase);
    if (m) return Math.round((2 + parseInt(m[1]) + 1) / TOTAL * 100);
    if (phase === 'result') return 100;
    return 0;
  }

  function progressBar(p) {
    return `<div class="wq-prog"><div class="wq-prog-fill" style="width:${p}%"></div></div>`;
  }

  function optHtml(label, val, name) {
    return `<div class="wq-opt" data-val="${val}" role="radio" tabindex="0" aria-label="${label}">
      <div class="wq-radio"><div class="wq-dot"></div></div>
      <span>${label}</span>
    </div>`;
  }

  // P1
  function renderP1(canon, state) {
    const opts = canon.preliminary.p1.options.map(o => optHtml(o.label, o.value)).join('');
    setContent(`<div class="wq">
      ${progressBar(pct('p1'))}
      <div class="wq-label">Шаг 1 из ${TOTAL}</div>
      <div class="wq-q">${canon.preliminary.p1.text}</div>
      <div class="wq-opts" id="wq-p1">${opts}</div>
      <div class="wq-nav">
        <span></span>
        <button class="wq-link" onclick="window.open('https://elephantdreams.ru/quiz.html','_blank')">Открыть полную версию</button>
      </div>
    </div>`);
    bindOpts('wq-p1', function (val) {
      state.segment = val;
      state.phase = 'p2';
      saveState(state);
      setTimeout(() => renderP2(canon, state), 200);
    });
  }

  // P2
  function renderP2(canon, state) {
    const opts = canon.preliminary.p2.options.map(o => optHtml(o.label, o.value)).join('');
    setContent(`<div class="wq">
      ${progressBar(pct('p2'))}
      <div class="wq-label">Шаг 2 из ${TOTAL}</div>
      <div class="wq-q">${canon.preliminary.p2.text}</div>
      <div class="wq-opts" id="wq-p2">${opts}</div>
      <div class="wq-nav">
        <button class="wq-back" onclick="renderP1_">← Назад</button>
      </div>
    </div>`);
    // back
    const inner = widget() && widget().querySelector('.edl-widget-quiz-inner');
    if (inner) {
      inner.querySelector('.wq-back').onclick = function () {
        state.phase = 'p1';
        saveState(state);
        renderP1(canon, state);
      };
    }
    bindOpts('wq-p2', function (val) {
      state.p2Option = val;
      state.phase = 'q0';
      saveState(state);
      setTimeout(() => renderQ(canon, state, 0), 200);
    });
  }

  // Основные вопросы
  function renderQ(canon, state, idx) {
    const q = canon.questions[idx];
    const opts = q.options.map(o => optHtml(o.label, o.score)).join('');
    const phase = 'q' + idx;
    setContent(`<div class="wq">
      ${progressBar(pct(phase))}
      <div class="wq-label">Вопрос ${idx + 1} из 12</div>
      <div class="wq-q">${q.text}</div>
      <div class="wq-opts" id="wq-q">${opts}</div>
      <div class="wq-nav">
        <button class="wq-back" id="wq-qback">← Назад</button>
        <button class="wq-link" onclick="window.open('https://elephantdreams.ru/quiz.html','_blank')">Полная версия</button>
      </div>
    </div>`);
    const inner = widget() && widget().querySelector('.edl-widget-quiz-inner');
    if (inner) {
      inner.querySelector('#wq-qback').onclick = function () {
        if (idx === 0) {
          state.phase = 'p2'; saveState(state); renderP2(canon, state);
        } else {
          state.phase = 'q' + (idx - 1); saveState(state); renderQ(canon, state, idx - 1);
        }
      };
    }
    bindOpts('wq-q', function (val) {
      state.answers[q.key] = parseInt(val, 10);
      if (idx < 11) {
        state.phase = 'q' + (idx + 1);
        saveState(state);
        setTimeout(() => renderQ(canon, state, idx + 1), 300);
      } else {
        state.phase = 'result';
        saveState(state);
        finishWidget(canon, state);
      }
    });
  }

  // Завершение
  function finishWidget(canon, state) {
    setContent(`<div class="wq" style="text-align:center;padding:32px 16px;">
      <div style="font-size:2rem;margin-bottom:12px;">⏳</div>
      <div style="font-weight:700;">Считаю Score...</div>
    </div>`);

    const result = MiniCheckupEngine.buildResult(state.answers, state.p2Option, state.segment);
    state.result = result;

    const duration = Math.round((Date.now() - state.startTs) / 1000);
    fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source: 'site_widget',
        segment: state.segment,
        stage_from_p2: state.p2Option,
        answers: state.answers,
        duration_sec: duration,
        consent_marketing: false,
      }),
    })
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (data && data.quiz_session_id) {
        state.quizSessionId = data.quiz_session_id;
        saveState(state);
      }
    })
    .catch(() => {});

    setTimeout(() => renderWidgetResult(canon, state, result), 700);
  }

  // Результат в виджете
  function renderWidgetResult(canon, state, r) {
    const colorMap = { red: '#EF4444', orange: '#F97316', yellow: '#CA8A04', green: '#16A34A' };
    const bgMap    = { red: '#FEF2F2', orange: '#FFF7ED', yellow: '#FEFCE8', green: '#F0FDF4' };
    const sc = r.categoryColor;

    const sessionParam = state.quizSessionId ? `audit_from_score_${state.quizSessionId}` : 'audit';
    const tgLink = `https://t.me/${BOT_USERNAME}?start=${sessionParam}`;

    let bmHtml = '';
    if (r.benchmarkMean != null) {
      const d = r.benchmarkDelta;
      const dStr = (d >= 0 ? '+' : '') + d;
      bmHtml = `<div class="wq-bm">
        Средний для ${r.segmentLabel} на стадии ${r.stageLabel}: <b>${r.benchmarkMean}</b> &nbsp;
        <span style="color:${d > 5 ? '#16A34A' : d < -5 ? '#EF4444' : '#9CA3AF'};font-weight:700;">Δ ${dStr}</span>
      </div>`;
    }

    const gpHtml = r.growthPoints.map((gp, i) =>
      `<div class="wq-gp">
        <div class="wq-gp-num">${i+1} · ${gp.layerLabel}</div>
        <div class="wq-gp-short">${gp.short}</div>
        <div class="wq-gp-act">${gp.action}</div>
      </div>`
    ).join('');

    setContent(`<div class="wq-result">
      ${progressBar(100)}
      <div class="wq-score" style="background:${bgMap[sc]||'#F9FAFB'}">
        <div class="wq-score-num" style="color:${colorMap[sc]||'#111827'}">${r.score}</div>
        <div style="color:#9CA3AF;font-size:0.8rem;">/ 100</div>
        <div class="wq-cat" style="color:${colorMap[sc]||'#111827'}">${r.category}</div>
      </div>

      <div style="font-size:0.8rem;color:#9CA3AF;margin-bottom:10px;">
        ${r.stageLabel} · ${r.segmentDisplay}
      </div>

      ${bmHtml}

      <div style="font-weight:700;font-size:0.875rem;margin-bottom:8px;">3 точки роста:</div>
      ${gpHtml}

      <a href="${tgLink}" target="_blank" rel="noopener" class="wq-cta-p">
        Открыть полный отчёт в Telegram
      </a>
      <div style="text-align:center;color:#9CA3AF;font-size:0.75rem;margin-top:8px;">
        Полный разбор + 3 действия на эту неделю — в боте
      </div>
      <button class="wq-cta-full" onclick="window.open('https://elephantdreams.ru/quiz.html','_blank')">
        Полная версия с PDF → quiz.html
      </button>
    </div>`);
  }

  // ── Option binding ────────────────────────────────────────────────────────
  function bindOpts(containerId, onSelect) {
    // containerId is just a class hint; we query from widget
    const w = widget();
    if (!w) return;
    const container = w.querySelector('#' + containerId) || w.querySelector('.wq-opts');
    if (!container) return;

    function handleClick(e) {
      const opt = e.target.closest('.wq-opt');
      if (!opt) return;
      container.querySelectorAll('.wq-opt').forEach(o => o.classList.remove('sel'));
      opt.classList.add('sel');
      const val = opt.dataset.val;
      setTimeout(() => onSelect(val), 220);
    }

    container.addEventListener('click', handleClick);
    container.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') handleClick(e);
    });
  }

  // ── Routing ───────────────────────────────────────────────────────────────
  function route(canon, state) {
    const { phase } = state;
    // If we have a fresh result (< 24h) — show it directly
    if (phase === 'result' && state.result) {
      return renderWidgetResult(canon, state, state.result);
    }
    if (phase === 'p1') return renderP1(canon, state);
    if (phase === 'p2') return renderP2(canon, state);
    const m = /^q(\d+)$/.exec(phase);
    if (m) return renderQ(canon, state, parseInt(m[1]));
    renderP1(canon, state);
  }

  // ── Init ──────────────────────────────────────────────────────────────────
  waitForDeps(function () {
    injectStyles();
    loadCanon(function (canon) {
      if (!canon) return; // Fail silently

      const saved = loadState();
      const state = saved || defaultState();

      // If prior session was completed — show resume prompt
      if (saved && saved.phase !== 'p1' && saved.phase !== 'result') {
        const qNum = (function () {
          const m = /^q(\d+)$/.exec(saved.phase);
          return m ? parseInt(m[1]) + 1 : 0;
        })();
        setContent(`<div class="wq" style="text-align:center;padding:32px 16px;">
          <div style="font-size:1.5rem;margin-bottom:12px;">👋</div>
          <div style="font-weight:700;margin-bottom:8px;">У вас сохранён прогресс</div>
          <div style="color:#6B7280;font-size:0.875rem;margin-bottom:20px;">
            ${qNum ? `Остановились на вопросе ${qNum}/12` : 'Часть ответов уже есть'}
          </div>
          <button id="wq-resume" style="display:block;width:100%;background:#F97316;color:#fff;font-weight:700;padding:12px;border:none;border-radius:8px;cursor:pointer;margin-bottom:10px;font-size:0.9rem;">Продолжить</button>
          <button id="wq-restart" style="display:block;width:100%;background:#F3F4F6;color:#374151;font-weight:600;padding:10px;border:none;border-radius:8px;cursor:pointer;font-size:0.85rem;">Начать заново</button>
        </div>`);
        const w = widget();
        if (w) {
          w.querySelector('#wq-resume').onclick = function () { route(canon, saved); };
          w.querySelector('#wq-restart').onclick = function () {
            const fresh = defaultState();
            saveState(fresh);
            route(canon, fresh);
          };
        }
        return;
      }

      route(canon, state);
    });
  });
}());
