/* ============================================
   EDL OS — Mini-Чекап Widget
   5 questions across 4 Founder OS layers + bonus
   Branching follow-ups by keyword detection
   Final synthesis with user-quote injection
   No backend deps; designed to swap in real API.
   ============================================ */

(function () {
  'use strict';

  const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const STORAGE_KEY = 'edl_mc_state_v1';
  const TYPE_SPEED_MS = REDUCED_MOTION ? 0 : 14;
  const TYPING_DELAY_MS = REDUCED_MOTION ? 0 : 700;

  // ── DIALOG SCRIPT ──────────────────────────────
  // Each layer: opening Q + keyword-driven follow-ups + default fallback
  const SCRIPT = [
    {
      id: 'strategy',
      label: 'Стратегия',
      icon: '🎯',
      q: 'Привет. Я ИИ-консультант EDL OS. За 15 минут разберу ваш бизнес по 4 слоям и пришлю короткий отчёт. Начнём со <strong>стратегии</strong>.\n\nКакая ваша главная цель на ближайший год?',
      chips: ['Вырасти ×2 по выручке', 'Поднять маржу', 'Собрать команду'],
      followups: [
        { keys: ['×2', 'x2', 'вырост', 'удво', 'масштаб', 'выручк', 'оборот'], q: 'Понял — рост. На каких клиентах будете расти: текущие, новые сегменты или новый продукт?' },
        { keys: ['маржа', 'прибыл', 'рентабельн'], q: 'Маржа — за счёт каких рычагов: цена, операционка или новые сегменты с большей маржинальностью?' },
        { keys: ['команд', 'найм', 'нанять', 'управлен', 'выйти', 'делегир'], q: 'Какой ключевой рычаг должна закрыть команда — продажи, продукт или операционка?' },
        { keys: ['продукт', 'запустить', 'новое'], q: 'Это новый продукт для текущей аудитории или вход в новый сегмент?' }
      ],
      defaultFollowup: 'А что для вас будет однозначным признаком, что год прошёл хорошо?'
    },
    {
      id: 'funnel',
      label: 'Воронка',
      icon: '📈',
      q: 'Следующий слой — <strong>воронка продаж</strong>.\n\nОткуда сегодня приходят новые клиенты и сколько сделок закрываете в месяц?',
      chips: ['Сарафан и рекомендации', 'Реклама и таргет', 'Холодные продажи / B2B'],
      followups: [
        { keys: ['сарафан', 'рекоменд', 'word-of-mouth', 'wom'], q: 'Сарафан хорош, пока не уперлись в потолок. Что мешает масштабировать — зависимость от 1-2 партнёров или нет процесса просьбы о реферале?' },
        { keys: ['реклам', 'таргет', 'директ', 'яндекс', 'google', 'смм', 'smm'], q: 'Какой средний CAC и сколько касаний от первого касания до сделки?' },
        { keys: ['холодн', 'тендер', 'b2b', 'кп', 'предложен'], q: 'Какая сейчас конверсия от КП к подписанному договору?' },
        { keys: ['сайт', 'лендинг', 'органик', 'seo'], q: 'Какая доля заявок с сайта доходит до сделки и где они отваливаются?' }
      ],
      defaultFollowup: 'Сколько сделок в месяц закрываете и какой у вас средний чек?'
    },
    {
      id: 'ops',
      label: 'Операционка',
      icon: '⚙️',
      q: 'Третий слой — <strong>операционка</strong>.\n\nСколько у вас сотрудников и клиентов в активной работе? Где сейчас самое узкое горлышко?',
      chips: ['Я тяну всё сам', 'Сильные перегружены', 'Команда работает, но медленно'],
      followups: [
        { keys: ['сам', 'один', 'тяну', 'на мне'], q: 'Если вы выпадете на 2 недели — что встанет первым? Продажи, исполнение или коммуникация с клиентами?' },
        { keys: ['перегруж', 'выгора', 'устал', '80', 'тян'], q: 'На ком конкретно держится 80% работы и что мешает разгрузить этого человека?' },
        { keys: ['текучк', 'увольн', 'уход', 'найм проблем'], q: 'Кто чаще уходит — джуны через полгода или сильные через год-два?' },
        { keys: ['процесс', 'регламент', 'руками', 'excel', 'таблиц'], q: 'Что повторяется руками каждую неделю и съедает 5+ часов?' }
      ],
      defaultFollowup: 'Сколько часов в неделю вы лично проводите в операционке, а не в стратегии?'
    },
    {
      id: 'money',
      label: 'Деньги',
      icon: '💰',
      q: 'Четвёртый слой — <strong>деньги</strong>.\n\nКак вы сегодня считаете маржу: по проектам, по клиентам или в целом по месяцу? Где сейчас риск-зона?',
      chips: ['Считаю в Excel руками', 'Вижу только в 1С/бухгалтерии', 'Маржу не считаю по проектам'],
      followups: [
        { keys: ['excel', 'таблиц', 'руками', 'sheet'], q: 'Когда последний раз цифры в таблице сошлись с тем, что реально на счёте?' },
        { keys: ['1с', 'бухгалт', 'фин.отчёт', 'фин отчёт', 'аутсорс'], q: 'Бухгалтерия показывает учёт. А видите ли вы реальную маржу по каждому контракту/клиенту в реальном времени?' },
        { keys: ['не счита', 'никак', 'на глаз', 'примерно'], q: 'Какая доля выручки — от 1-2 крупных клиентов? Это критичный риск.' },
        { keys: ['ндс', 'налог', 'антидробл', '22'], q: 'НДС 22% уже в цене или съедает маржу? Какой запас прочности по кэшу — 1, 3 или 6 месяцев?' },
        { keys: ['кассов', 'разрыв', 'кэш', 'cash'], q: 'Видите ли кассовый разрыв за 30/60/90 дней до его наступления?' }
      ],
      defaultFollowup: 'Знаете ли вы свою маржу с точностью до 2 процентных пунктов?'
    },
    {
      id: 'bonus',
      label: 'Бонус',
      icon: '🔥',
      q: 'И последний вопрос. Что в текущей операционке раздражает вас <strong>больше всего</strong>?',
      chips: ['Постоянное переключение между системами', 'Никто кроме меня не видит цифры', 'Делаю работу за сотрудников'],
      followups: [],
      defaultFollowup: null
    }
  ];

  // ── SUMMARY TEMPLATES ─────────────────────────────
  // Per-layer observation: 2-3 sentences with market anchors + methodology refs
  // (Founder OS · 4 layers · CRAFT · AI Fluency · benchmarks 10-50 SMB РФ)
  function buildLayerObservation(layer, answers) {
    const a = (answers[layer.id] || []).join(' ').toLowerCase();
    const obs = {
      strategy: () => {
        if (/×2|x2|удво|масштаб|выручк|оборот/.test(a)) return 'Цель роста есть — это уже выше среднего по SMB 10–50 человек. По методологии Founder OS рост ×2 одновременно нагружает 3 слоя из 4: стратегию, воронку и операционку. Чекап подсветит, какой слой держит ваш рост — обычно это узкое место в одном из них, а не во всех сразу.';
        if (/маржа|прибыл|рентабельн/.test(a)) return 'Цель по марже — самая частая и самая недооценённая. По нашим разборам (18+ бизнесов в исследовании рынка), в 7 из 10 портфелей есть 2–3 убыточных контракта, которые собственник не видит. Слой «Деньги» Founder OS закрывает эту слепую зону за один чекап.';
        if (/команд|найм|выйти|делегир/.test(a)) return 'Выход основателя из операционки — это не про найм, а про систему. Подход CRAFT (Центр CRAFT, школа инноваций ИКРА) даёт рамку: сначала описываем 3 контура управления, только потом ищем человека под них. Иначе любой найм отскакивает.';
        return 'Цель есть, но не привязана к недельной метрике — это типичная картина у 60–70% SMB. По Founder OS первый шаг — превратить её в 3 ключевые ставки на 12 месяцев, к которым привязаны цифры.';
      },
      funnel: () => {
        if (/сарафан|рекоменд/.test(a)) return 'Сарафан — лучший канал на старте, и худший — после потолка. По нашим наблюдениям, в B2B-услугах 10–50 человек он упирается в 1,5–2 млн ₽/мес и зависит от 1–2 источников. Чтобы перешагнуть, нужен второй платный канал и pipeline на 60–90 дней вперёд — это слой «Воронка» Founder OS.';
        if (/реклам|таргет|директ|яндекс|google/.test(a)) return 'В платном трафике решает LTV по каналу, а не CAC. По типичным РФ-SMB срок выхода в плюс — 4–6 месяцев на канал; без видимости маржи по сделке масштабирование уводит в минус. Бизнес-чекап даёт срез CAC / LTV / Payback за 24 часа.';
        if (/холодн|тендер|b2b|кп/.test(a)) return 'В B2B-цикле побеждает тот, кто видит pipeline по неделям и какие сделки «зависли» больше 14 дней. По данным наших разборов, в холодных продажах 30–40% сделок «зависают» молча — без триггера на действие. EDL OS, слой «Воронка», собирает это утром в Telegram.';
        return 'Воронка без чисел — это вера. По Founder OS управление воронкой = три цифры по сегменту: вход → конверсия → средний чек. Без них любое решение по росту — лотерея.';
      },
      ops: () => {
        if (/сам|один|тяну/.test(a)) return 'Когда основатель — единственная критическая точка, бизнес не масштабируется и не продаётся. По нашим разборам founder-only компаний — 12–18 часов в неделю уходит на повторяющиеся решения, которые можно делегировать. EDL начинает с того, чтобы вынуть вас из 2–3 таких контуров.';
        if (/перегруж|выгора|тян|80/.test(a)) return 'Если 80% работы на 20% людей — это риск потерять 2 ключевых сотрудников за 6–12 месяцев. По AI Fluency Framework (Anthropic) и подходу Big Tech ops, 2–3 регулярных процесса (отчётность, рутина, ответы клиентам) автоматизируются за 1–2 недели и снимают 30–40% перегруза.';
        if (/текучк|увольн|найм/.test(a)) return 'Текучка — симптом, не диагноз. Корень в SMB 10–50 — это перегруз + отсутствие карты «кто чем занят». Чекап даёт эту карту за 1 раунд интервью и подсвечивает, какие проекты систематически перегружают команду.';
        if (/процесс|регламент|руками|excel/.test(a)) return 'Каждый ручной процесс на 5+ часов в неделю — это 250+ часов в год. По методологии Big Tech ops автоматизация таких рутин окупается за 1 квартал, ROI 6–10x. Чекап покажет, какие 2–3 процесса дают максимум на ваших данных.';
        return 'Скрытая загрузка команды — самый недооценённый риск в SMB 10–50. По нашим разборам, видимость нагрузки даёт +20–30% к производительности команды без единого найма.';
      },
      money: () => {
        if (/excel|таблиц|руками/.test(a)) return 'Excel-учёт работает до 20 клиентов. После — расхождения, ошибки округления, скрытые убыточные. По нашим данным, в портфеле 30+ клиентов на ручном учёте 15–25% выручки идёт от контрактов, которые в минусе по марже — видны только после ручной сверки на чекапе.';
        if (/1с|бухгалт/.test(a)) return '1С показывает учёт, а не экономику собственника. По нашим разборам, разрыв между «бухгалтерской» прибылью и реальной маржой по контракту в момент закрытия — 5–15 п.п. EDL, слой «Деньги», закрывает этот разрыв в день сделки, а не в конце квартала.';
        if (/не счита|никак|на глаз/.test(a)) return 'Когда маржа считается «на глаз», в портфеле почти всегда 2–3 убыточных клиента, съедающих 10–20% прибыли. По Founder OS, слой «Деньги» — первый, потому что без него остальные три слоя работают вслепую. Видно за 1 чекап.';
        if (/ндс|налог|антидробл|22/.test(a)) return 'НДС 22% с 1 января 2026 и антидробление — это пересмотр маржи по каждому клиенту. По нашим оценкам, в малом B2B-сервисе до 30–40% контрактов потребуют пересмотра цены либо ухода. Чекап-Plus 14 000 ₽ включает раздел «НДС-флажок 2026» с зоной риска по вашей выручке.';
        if (/кассов|разрыв|кэш/.test(a)) return 'Кассовый разрыв виден за 3 недели до факта, если есть прогноз cash-flow на 30/60/90 дней. Без прогноза — узнаёте в день, когда нужно платить зарплату. EDL собирает прогноз из реальных коннекторов (1С, банк) — это уровень Диагностики/Спринта, но картинку «зон риска» можно дать уже на Чекапе.';
        return 'Маржа с точностью до проекта — это разница между управлением и догадками. По Founder OS, без слоя «Деньги» три остальных слоя работают вслепую. Чекап даёт картинку за 24 часа.';
      },
      bonus: () => {
        if (/переключ|систем|вкладк/.test(a)) return 'Это и есть главное обещание EDL OS — одна утренняя сводка в Telegram вместо 10 систем. Бортовой компьютер для бизнеса 10–50 человек.';
        if (/никто|не видит/.test(a)) return 'Когда цифры только у вас в голове — бизнес не делегируется. EDL делает их общим языком для команды через утренний бриф в Telegram — без новых паролей и IT-отдела.';
        if (/делаю работу/.test(a)) return 'Работа «за сотрудников» — следствие отсутствия процесса и видимости, а не лени команды. Чекап начинает с диагноза: какие 2–3 регламента дадут максимум на ваших данных.';
        return null;
      }
    };
    try { return obs[layer.id](); } catch (_) { return null; }
  }

  function buildSummary(answers) {
    const obs = SCRIPT.filter(l => l.id !== 'bonus').map(l => ({
      id: l.id, label: l.label, icon: l.icon,
      heard: (answers[l.id] || [])[0] || '',
      observation: buildLayerObservation(l, answers)
    }));
    const bonusObs = buildLayerObservation(SCRIPT.find(l => l.id === 'bonus'), answers);
    const recs = pickRecommendations(answers);
    return { layers: obs, bonusObs, recs };
  }

  function pickRecommendations(answers) {
    const all = Object.values(answers).flat().join(' ').toLowerCase();
    const recs = [];
    if (/×2|удво|масштаб|выручк/.test(all)) recs.push('Зафиксировать 3 ключевые ставки на 12 месяцев (рамка Founder OS) и привязать к ним недельные метрики.');
    if (/маржа|прибыл|рентабельн/.test(all) || /excel|1с|не счита/.test(all)) recs.push('Построить отчёт «маржа по клиенту за квартал» — типично подсвечивает 2–3 нерентабельных контракта на 10–20% прибыли.');
    if (/сарафан|рекоменд/.test(all)) recs.push('Запустить второй канал привлечения — в SMB 10–50 это снимает риск концентрации и пробивает потолок 1,5–2 млн ₽/мес.');
    if (/перегруж|выгора|тян|сам/.test(all)) recs.push('Выбрать 2–3 ручных процесса > 5 часов в неделю и автоматизировать — ROI 6–10x за квартал по подходу Big Tech ops.');
    if (/ндс|налог|антидробл/.test(all)) recs.push('Пересчитать маржу по клиентам после НДС 22% (с 1 января 2026) — 30–40% контрактов уйдут под пересмотр цены.');
    if (/кассов|разрыв|кэш/.test(all)) recs.push('Внедрить прогноз cash-flow на 30/60/90 дней — кассовый разрыв виден за 3 недели до факта.');
    if (recs.length === 0) recs.push(
      'Зафиксировать стартовую картину по 4 слоям Founder OS: стратегия, воронка, операционка, деньги — 1 экран, 1 страница.',
      'Выделить 1 убыточного клиента и 1 перегруженного сотрудника как фокус первой итерации.'
    );
    return recs.slice(0, 3);
  }

  // ── DOM utils ──────────────────────────
  const $ = (id) => document.getElementById(id);
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  function scrollToBottom(el) {
    requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
  }

  function appendUserMsg(body, text) {
    const wrap = document.createElement('div');
    wrap.className = 'mc-msg mc-msg--user';
    wrap.innerHTML = `<div class="mc-bubble"></div>`;
    wrap.querySelector('.mc-bubble').textContent = text;
    body.appendChild(wrap);
    scrollToBottom(body);
  }

  async function appendAiMsg(body, html, opts = {}) {
    // Show typing first
    const typingWrap = document.createElement('div');
    typingWrap.className = 'mc-msg mc-msg--ai';
    typingWrap.innerHTML = `<div class="mc-typing"><span></span><span></span><span></span></div>`;
    body.appendChild(typingWrap);
    scrollToBottom(body);
    await sleep(opts.delay ?? TYPING_DELAY_MS);
    typingWrap.remove();

    const wrap = document.createElement('div');
    wrap.className = 'mc-msg mc-msg--ai';
    const bubbleClass = opts.label ? 'mc-bubble mc-bubble--layer' : 'mc-bubble';
    wrap.innerHTML = `<div class="${bubbleClass}">${opts.label ? `<span class="mc-bubble__label">${opts.label}</span>` : ''}<span class="mc-bubble__text"></span></div>`;
    body.appendChild(wrap);
    const target = wrap.querySelector('.mc-bubble__text');
    await typeHtml(target, html);
    scrollToBottom(body);

    if (opts.chips && opts.chips.length) {
      const chipsWrap = document.createElement('div');
      chipsWrap.className = 'mc-msg mc-msg--ai';
      chipsWrap.innerHTML = `<div style="max-width:88%;"><div class="mc-chips"></div></div>`;
      const chipsEl = chipsWrap.querySelector('.mc-chips');
      opts.chips.forEach(label => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'mc-chip';
        b.textContent = label;
        b.addEventListener('click', () => {
          chipsWrap.remove();
          opts.onChip && opts.onChip(label);
        });
        chipsEl.appendChild(b);
      });
      body.appendChild(chipsWrap);
      scrollToBottom(body);
    }
    return wrap;
  }

  async function typeHtml(target, html) {
    if (TYPE_SPEED_MS === 0) {
      target.innerHTML = html;
      return;
    }
    // Tokenize html into text/tag tokens; type only text chars
    const tokens = [];
    let buf = '';
    let inTag = false;
    for (const ch of html) {
      if (ch === '<') { if (buf) tokens.push({t:'text', v:buf}); buf=ch; inTag=true; continue; }
      if (ch === '>' && inTag) { buf+=ch; tokens.push({t:'tag', v:buf}); buf=''; inTag=false; continue; }
      buf += ch;
    }
    if (buf) tokens.push({t:'text', v:buf});
    let rendered = '';
    const cursor = '<span class="mc-cursor"></span>';
    for (const tok of tokens) {
      if (tok.t === 'tag') { rendered += tok.v; target.innerHTML = rendered + cursor; continue; }
      for (const ch of tok.v) {
        rendered += ch;
        target.innerHTML = rendered + cursor;
        await sleep(TYPE_SPEED_MS);
      }
    }
    target.innerHTML = rendered;
  }

  function pickFollowup(layer, answer) {
    const lower = answer.toLowerCase();
    for (const f of layer.followups || []) {
      if (f.keys.some(k => lower.includes(k))) return f.q;
    }
    return layer.defaultFollowup;
  }

  // ── State + flow ──────────────────────────────
  function freshState() {
    return {
      step: 0,                  // index in SCRIPT
      stage: 'q',               // 'q' (waiting answer to opening q) | 'followup' (waiting answer to follow-up) | 'done'
      answers: {},              // {layerId: [first, followup]}
      startedAt: Date.now()
    };
  }

  let state = freshState();
  let body, input, send, progressBar;

  function persist() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (_) {}
  }
  function clearPersist() {
    try { localStorage.removeItem(STORAGE_KEY); } catch (_) {}
  }

  function setProgress(pct) {
    if (progressBar) progressBar.style.width = pct + '%';
  }

  async function askCurrent() {
    const layer = SCRIPT[state.step];
    if (!layer) return finalize();
    setProgress(Math.round((state.step / SCRIPT.length) * 100));
    await appendAiMsg(body, layer.q, {
      label: `${layer.icon}  ${layer.label} · ${state.step + 1}/${SCRIPT.length}`,
      chips: layer.chips,
      onChip: (label) => handleUserInput(label)
    });
    input.focus();
  }

  async function handleUserInput(text) {
    text = (text || '').trim();
    if (!text) return;
    appendUserMsg(body, text);
    const layer = SCRIPT[state.step];
    state.answers[layer.id] = state.answers[layer.id] || [];
    state.answers[layer.id].push(text);
    persist();
    track('mc_answer', { layer: layer.id, stage: state.stage, len: text.length });

    if (state.stage === 'q') {
      const fu = pickFollowup(layer, text);
      if (fu) {
        state.stage = 'followup';
        persist();
        await appendAiMsg(body, fu);
        input.focus();
        return;
      }
    }
    // Move to next layer
    state.step += 1;
    state.stage = 'q';
    persist();
    if (state.step >= SCRIPT.length) return finalize();
    await sleep(REDUCED_MOTION ? 0 : 400);
    askCurrent();
  }

  async function finalize() {
    setProgress(100);
    state.stage = 'done';
    persist();
    track('mc_completed', { durationSec: Math.round((Date.now() - state.startedAt) / 1000) });

    // Hide composer immediately — dialog is done, no more input
    const composer = $('mc-composer');
    if (composer) composer.style.display = 'none';

    const summary = buildSummary(state.answers);

    // 1) Intro bubble — frames the result as ИИ-интерпретация, not a verdict
    await appendAiMsg(body,
      'Готово. Собрал предварительный разбор по 4 слоям <strong>Founder OS</strong> — Стратегия · Воронка · Операционка · Деньги. Это ИИ-интерпретация на основе ваших ответов; полные цифры по вашему бизнесу — в Бизнес-чекапе.',
      { delay: 500 }
    );

    // 2) Per-layer observations as separate chat bubbles
    for (const layer of summary.layers) {
      if (!layer.observation) continue;
      let html = '';
      if (layer.heard) {
        html += `<span class="mc-quote">Услышал: «${escapeHtml(truncate(layer.heard, 140))}»</span>`;
      }
      html += layer.observation;
      await appendAiMsg(body, html, {
        label: `${layer.icon}  ${layer.label}`,
        delay: 450
      });
    }

    // 3) Bonus observation (if any) — plain bubble
    if (summary.bonusObs) {
      await appendAiMsg(body, '<strong>P.S.</strong> ' + summary.bonusObs, { delay: 400 });
    }

    // 4) Recommendations as a single bubble with ordered list
    const recsHtml = '<strong>Что сделал бы в первую очередь:</strong>'
      + '<ol class="mc-recs">'
      + summary.recs.map(r => `<li>${r}</li>`).join('')
      + '</ol>';
    await appendAiMsg(body, recsHtml, { delay: 500 });

    // 5) Final CTA card — rendered as a stream message (full-width, no horizontal overflow)
    await sleep(REDUCED_MOTION ? 0 : 500);
    renderCtaStream();
  }

  function renderCtaStream() {
    const wrap = document.createElement('div');
    wrap.className = 'mc-msg mc-msg--ai mc-msg--cta';
    wrap.innerHTML = `
      <div class="mc-cta-card">
        <div class="mc-cta-card__text">
          Хотите увидеть это <strong>с цифрами по вашему бизнесу</strong>?<br>
          <strong>Бизнес-чекап 9 000 ₽</strong> — 20 вопросов в боте, PDF-разбор на 10 страниц + 5 рекомендаций, готово за 24 часа.<br>
          <span class="mc-cta-card__sub">Plus 14 000 ₽: 15 страниц, 7 рекомендаций, раздел «НДС-флажок 2026» и персональное 15-мин видео от Кати через 24 ч после оплаты.</span><br>
          <strong>Безусловный возврат 14 дней — один клик в боте.</strong>
        </div>
        <a href="audit.html" class="mc-cta-card__btn" data-cta-type="audit" data-cta-location="mini_checkup">Перейти к Бизнес-чекапу 9 000 ₽ →</a>
        <a href="https://t.me/edl_os" target="_blank" rel="noopener" class="mc-cta-card__secondary">Не готов(а) сейчас — подпишусь на Telegram-канал</a>
        <form class="mc-email-form" id="mc-email-form">
          <label class="mc-email-form__label" for="mc-email">Прислать этот разбор на email + добавить в рассылку с разборами клиентов:</label>
          <div class="mc-email-form__row">
            <input type="email" id="mc-email" class="mc-email-form__input" placeholder="you@company.ru" required>
            <button type="submit" class="mc-email-form__submit">Прислать</button>
          </div>
          <div class="mc-email-form__success">✓ Принято. Письмо придёт в течение 5 минут.</div>
        </form>
      </div>
    `;
    body.appendChild(wrap);
    scrollToBottom(body);

    const form = $('mc-email-form');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const email = $('mc-email').value.trim();
        if (!email) return;
        try {
          const leads = JSON.parse(localStorage.getItem('edl_mc_leads') || '[]');
          leads.push({ email, at: new Date().toISOString(), answers: state.answers });
          localStorage.setItem('edl_mc_leads', JSON.stringify(leads));
        } catch (_) {}
        track('mc_email_lead', { domain: email.split('@')[1] || '' });
        form.classList.add('is-sent');
      });
    }
    wrap.querySelectorAll('[data-cta-type]').forEach(a => {
      a.addEventListener('click', () => track('cta_clicked', {
        cta_type: a.dataset.ctaType,
        cta_location: a.dataset.ctaLocation
      }));
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  function truncate(s, n) {
    return s.length > n ? s.slice(0, n - 1) + '…' : s;
  }

  function track(event, payload) {
    if (window.EDLTrack) window.EDLTrack(event, payload);
  }

  // ── Open / Close ──────────────────────────────
  let lastFocusedEl = null;

  function openModal(opts = {}) {
    const modal = $('mc-modal');
    if (!modal) return;
    lastFocusedEl = document.activeElement;
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('mc-modal-open');
    track('mc_opened', { source: opts.source || 'unknown' });

    // Try restore — if user had a session today and not done, offer resume
    let resumed = false;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        const ageHours = (Date.now() - (saved.startedAt || 0)) / 36e5;
        if (saved && saved.step > 0 && saved.stage !== 'done' && ageHours < 24) {
          state = saved;
          resumed = true;
        }
      }
    } catch (_) {}

    if (!resumed) {
      state = freshState();
      body.innerHTML = '';
      const composer = $('mc-composer');
      if (composer) composer.style.display = '';
      setProgress(0);
    } else {
      // Replay last AI question for context
      body.innerHTML = '';
      track('mc_resumed', { step: state.step });
    }
    askCurrent();
    setTimeout(() => input.focus(), 100);
  }

  function closeModal() {
    const modal = $('mc-modal');
    if (!modal) return;
    modal.classList.remove('is-open');
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('mc-modal-open');
    if (lastFocusedEl) lastFocusedEl.focus();
    track('mc_closed', { step: state.step, stage: state.stage });
  }

  // ── Init ──────────────────────────
  function init() {
    body = $('mc-body');
    input = $('mc-input');
    send = $('mc-send');
    progressBar = $('mc-progress-bar');
    const closeBtn = $('mc-close');
    const modal = $('mc-modal');
    if (!modal || !body) return;

    // Open triggers
    document.querySelectorAll('[data-mc-open]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        openModal({ source: btn.dataset.mcOpen || 'cta' });
      });
    });

    // Close
    closeBtn && closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && modal.classList.contains('is-open')) closeModal();
    });

    // Send
    function trySend() {
      const v = input.value.trim();
      if (!v) return;
      input.value = '';
      autoResize();
      handleUserInput(v);
    }
    send.addEventListener('click', trySend);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        trySend();
      }
    });
    // Auto-resize textarea
    function autoResize() {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 140) + 'px';
    }
    input.addEventListener('input', autoResize);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Public API for debugging / future API integration
  window.EDLMiniCheckup = {
    open: openModal,
    close: closeModal,
    reset: () => { state = freshState(); clearPersist(); }
  };
})();
