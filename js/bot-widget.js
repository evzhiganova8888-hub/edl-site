(function () {
  'use strict';

  var SESSION_KEY = 'edl_widget_session';
  var DISMISSED_KEY = 'edl_widget_dismissed';
  var API_BASE = 'https://api.elephantdreams.ru/widget';
  var TRIGGER_TIME_MS = 30000;
  var TRIGGER_SCROLL_PCT = 30;

  function genId() {
    return 'w_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
  }

  function getSessionId() {
    var s = localStorage.getItem(SESSION_KEY);
    if (!s) { s = genId(); localStorage.setItem(SESSION_KEY, s); }
    return s;
  }

  var sessionId = getSessionId();
  var isOpen = false;
  var messages = [];
  var eventSource = null;

  /* ── Build DOM ── */
  var bubble = document.createElement('button');
  bubble.className = 'bw-bubble';
  bubble.setAttribute('aria-label', 'Открыть чат с ассистентом EDL OS');
  bubble.innerHTML = '💬';

  var container = document.createElement('div');
  container.className = 'bw-container bw-hidden';
  container.innerHTML =
    '<div class="bw-header">' +
      '<div class="bw-header__title">' +
        '<img src="/assets/logo-192.png" alt="EDL OS">' +
        '<div><span class="bw-header__name">EDL OS</span><span class="bw-header__status">онлайн</span></div>' +
      '</div>' +
      '<button class="bw-header__close" aria-label="Закрыть чат">✕</button>' +
    '</div>' +
    '<div class="bw-messages" id="bw-msgs"></div>' +
    '<div class="bw-input-row">' +
      '<input type="text" id="bw-input" placeholder="Напишите сообщение..." autocomplete="off">' +
      '<button id="bw-send" disabled>→</button>' +
    '</div>';

  document.body.appendChild(bubble);
  document.body.appendChild(container);

  var msgsEl = document.getElementById('bw-msgs');
  var inputEl = document.getElementById('bw-input');
  var sendBtn = document.getElementById('bw-send');

  /* ── Render ── */
  function renderInitial() {
    msgsEl.innerHTML =
      '<div class="bw-initial">' +
        '<p>🤖 Здравствуйте! Я ассистент EDL OS — бортового компьютера для бизнеса 10–50 человек.</p>' +
        '<p>Чем помочь?</p>' +
        '<div class="bw-quick-btns">' +
          '<button data-q="Что такое EDL OS?">Что такое EDL OS?</button>' +
          '<button data-q="Пройти Founder OS Score">Пройти Founder OS Score</button>' +
          '<button data-q="Сколько стоит?">Сколько стоит?</button>' +
          '<button data-q="Связаться с менеджером">Связаться с менеджером</button>' +
        '</div>' +
      '</div>';
    msgsEl.querySelectorAll('.bw-quick-btns button').forEach(function(btn) {
      btn.addEventListener('click', function() { sendMessage(btn.getAttribute('data-q')); });
    });
  }

  function appendMessage(role, text, buttons) {
    var el = document.createElement('div');
    el.className = 'bw-msg bw-msg--' + role;
    el.appendChild(renderText(text));
    if (buttons && buttons.length) {
      var btnsDiv = document.createElement('div');
      btnsDiv.className = 'bw-msg-btns';
      buttons.forEach(function(b) {
        var btn = document.createElement('button');
        btn.textContent = b.label;
        btn.addEventListener('click', function() { sendMessage(b.callback); });
        btnsDiv.appendChild(btn);
      });
      el.appendChild(btnsDiv);
    }
    msgsEl.appendChild(el);
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }

  function renderText(text) {
    var frag = document.createDocumentFragment();
    var pdfRe = /\[(.+?)\]\((https?:\/\/.+?\.pdf)\)/g;
    var last = 0, m;
    while ((m = pdfRe.exec(text)) !== null) {
      if (m.index > last) {
        frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      }
      var a = document.createElement('a');
      a.className = 'bw-pdf-card';
      a.href = m[2];
      a.download = '';
      a.textContent = '📄 ' + m[1];
      frag.appendChild(a);
      last = m.index + m[0].length;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    return frag;
  }

  /* ── SSE ── */
  function subscribeSSE() {
    if (eventSource) eventSource.close();
    eventSource = new EventSource(API_BASE + '/stream/' + sessionId);
    eventSource.onmessage = function(ev) {
      try {
        var data = JSON.parse(ev.data);
        if (messages.length === 0) { msgsEl.innerHTML = ''; }
        messages.push({role: 'bot', text: data.text});
        appendMessage('bot', data.text, data.buttons);
      } catch(e) {}
    };
    eventSource.onerror = function() { 
      eventSource.close(); 
      appendError();
    };
  }

  function appendError() {
    var el = document.createElement('div');
    el.className = 'bw-msg bw-msg--bot';
    el.innerHTML = '<span style="color:#dc2626;">⚠️ Бот временно недоступен.</span> Напишите нам напрямую в <a href="https://t.me/edl_os" target="_blank" style="color:#FF6B1A; font-weight:600;">Telegram @edl_os</a>.';
    msgsEl.appendChild(el);
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }

  /* ── Send ── */
  function sendMessage(text) {
    if (!text || !text.trim()) return;
    if (messages.length === 0) { msgsEl.innerHTML = ''; }
    messages.push({role: 'user', text: text});
    appendMessage('user', text);
    inputEl.value = '';
    sendBtn.disabled = true;

    fetch(API_BASE + '/message', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({session_id: sessionId, text: text, page_referrer: location.href})
    }).then(res => {
      if (!res.ok) throw new Error('Network response was not ok');
    }).catch(function(){
      appendError();
    });
  }

  /* ── Open / Close ── */
  function open() {
    if (isOpen) return;
    isOpen = true;
    bubble.classList.add('bw-hidden');
    container.classList.remove('bw-hidden');
    if (messages.length === 0) {
      renderInitial();
      subscribeSSE();
    }
  }

  function close() {
    isOpen = false;
    container.classList.add('bw-hidden');
    bubble.classList.remove('bw-hidden');
    sessionStorage.setItem(DISMISSED_KEY, 'true');
    if (eventSource) { eventSource.close(); eventSource = null; }
  }

  bubble.addEventListener('click', open);
  container.querySelector('.bw-header__close').addEventListener('click', close);

  inputEl.addEventListener('input', function() {
    sendBtn.disabled = !inputEl.value.trim();
  });
  inputEl.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey && inputEl.value.trim()) {
      e.preventDefault();
      sendMessage(inputEl.value);
    }
  });
  sendBtn.addEventListener('click', function() {
    if (inputEl.value.trim()) sendMessage(inputEl.value);
  });

  /* ── Cumulative trigger ── */
  (function() {
    if (sessionStorage.getItem(DISMISSED_KEY) === 'true') return;
    var timeOnPage = 0;
    var scrollDepth = 0;
    var triggered = false;

    var timer = setInterval(function() {
      if (!triggered) timeOnPage += 1000;
    }, 1000);

    function onScroll() {
      var doc = document.documentElement;
      var pct = (window.scrollY / (doc.scrollHeight - window.innerHeight)) * 100;
      if (pct > scrollDepth) scrollDepth = pct;
    }
    window.addEventListener('scroll', onScroll, {passive: true});

    var checker = setInterval(function() {
      if (!triggered && timeOnPage >= TRIGGER_TIME_MS && scrollDepth >= TRIGGER_SCROLL_PCT) {
        triggered = true;
        clearInterval(timer);
        clearInterval(checker);
        window.removeEventListener('scroll', onScroll);
        open();
        /* send /start greeting */
        fetch(API_BASE + '/message', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({session_id: sessionId, text: '/start', page_referrer: location.href})
        }).catch(function(){});
      }
    }, 1000);
  })();

})();
