/*
 * NaBandeja: utilitários das telas internas.
 *
 * - Tempo real: WebSocket /ws/orders/ ou polling de /tempo-real/eventos/
 *   (conforme o servidor). Cada evento vira o evento DOM "nb:event" no <body>;
 *   partes da tela com hx-trigger="nb:event from:body" se atualizam sozinhas (htmx).
 * - Sons: avisos curtos gerados no navegador (sem arquivos).
 * - Toast: mensagens rápidas, sempre como texto (nunca HTML).
 */
(function () {
  'use strict';

  const NB = (window.NB = window.NB || {});

  // ------------------------------------------------------------ toast
  const ICONS = { success: 'bi-check-circle', error: 'bi-x-circle', warning: 'bi-exclamation-triangle', info: 'bi-info-circle' };
  const COLORS = { success: 'bg-manjericao', error: 'bg-pimenta', warning: 'bg-[#8A5A12]', info: 'bg-carvao' };

  function toastContainer() {
    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container fixed bottom-3 inset-x-3 md:inset-x-auto md:right-4 md:bottom-4 z-[80] flex flex-col items-stretch md:items-end gap-2 pointer-events-none';
      container.setAttribute('role', 'status');
      container.setAttribute('aria-live', 'polite');
      document.body.appendChild(container);
    }
    return container;
  }

  NB.toast = function (message, type = 'info', duration = 3500) {
    const toast = document.createElement('div');
    toast.className = `toast-enter px-4 py-3 rounded-2xl shadow-float flex items-center gap-3 text-white pointer-events-auto max-w-md ${COLORS[type] || COLORS.info}`;
    const icon = document.createElement('i');
    icon.className = `bi ${ICONS[type] || ICONS.info} text-lg`;
    const text = document.createElement('span');
    text.className = 'font-medium';
    icon.setAttribute('aria-hidden', 'true');
    text.textContent = message;
    toast.append(icon, text);
    toastContainer().appendChild(toast);
    setTimeout(() => {
      toast.style.transition = 'all .3s ease-out';
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  };
  window.showToast = NB.toast; // compatibilidade com templates antigos

  // ------------------------------------------------------------ confirmação
  // <form data-confirm-message="..."> e hx-confirm="..." usam o <dialog> da base.
  NB.confirm = function (message) {
    const dialog = document.getElementById('nbConfirm');
    if (!dialog || typeof dialog.showModal !== 'function') return Promise.resolve(window.confirm(message));
    document.getElementById('nbConfirmMessage').textContent = message;
    return new Promise((resolve) => {
      dialog.addEventListener('close', () => resolve(dialog.returnValue === 'ok'), { once: true });
      dialog.returnValue = '';
      dialog.showModal();
    });
  };
  window.showConfirmModal = NB.confirm;

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.dataset.confirmMessage) return;
    if (form.dataset.confirmed === '1') { delete form.dataset.confirmed; return; }
    event.preventDefault();
    if (await NB.confirm(form.dataset.confirmMessage)) {
      form.dataset.confirmed = '1';
      form.requestSubmit ? form.requestSubmit(event.submitter) : form.submit();
    }
  }, true);

  document.addEventListener('htmx:confirm', (event) => {
    if (!event.detail.question) return;
    event.preventDefault();
    NB.confirm(event.detail.question).then((ok) => { if (ok) event.detail.issueRequest(true); });
  });

  // ------------------------------------------------------------ sons
  let audioCtx = null;
  NB.beep = function (kind = 'new') {
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const notes = { new: [880, 1175], ready: [660, 880, 1320], call: [988, 740, 988] }[kind] || [880];
      notes.forEach((freq, index) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.value = freq;
        const start = audioCtx.currentTime + index * 0.18;
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(0.35, start + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.16);
        osc.connect(gain).connect(audioCtx.destination);
        osc.start(start);
        osc.stop(start + 0.17);
      });
    } catch (err) {
      /* navegador sem áudio: ignora */
    }
  };
  // Navegadores só liberam áudio depois de um toque na tela.
  document.addEventListener('pointerdown', () => {
    if (!audioCtx) {
      try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch (err) { /* sem áudio */ }
    }
  }, { once: true });

  // ------------------------------------------------------------ tempo real
  // O mesmo contrato em qualquer servidor: eventos com id crescente.
  // - WebSocket (ASGI): chegam na hora;
  // - polling: GET /tempo-real/eventos/?desde=<id> (WSGI, PythonAnywhere ou WebSocket fora do ar).
  // O cursor evita repetir e perder eventos; cada um vira "nb:event" com o tipo real
  // (order.created, table.call...), então sons e avisos funcionam nos dois modos.
  const RT = { mode: 'off', cursor: 0, pollMs: 4000, timer: null, polling: false, inFlight: false, retries: 0, wsFailures: 0, wsPausedUntil: 0, socketOpen: false };
  const HIDDEN_POLL_MS = 15000;
  const SAFETY_REFRESH_MS = 60000;
  const WS_GIVE_UP_AFTER = 3;
  const WS_PAUSE_MS = 5 * 60000;

  function setStatus(ok) {
    document.querySelectorAll('[data-realtime-status]').forEach((el) => {
      el.dataset.online = ok ? '1' : '0';
      el.title = !ok ? 'Sem conexão: tentando de novo' : RT.socketOpen ? 'Tempo real conectado' : `Atualizando a cada ${RT.pollMs / 1000} s`;
      el.classList.toggle('bg-emerald-500', ok);
      el.classList.toggle('bg-amber-400', !ok);
    });
  }

  function emit(detail) {
    document.body.dispatchEvent(new CustomEvent('nb:event', { detail }));
  }

  function deliver(event) {
    if (event.id) {
      if (event.id <= RT.cursor) return;
      RT.cursor = event.id;
    }
    emit(event);
  }

  async function pollOnce() {
    if (RT.inFlight) return;
    RT.inFlight = true;
    try {
      const response = await fetch(`/tempo-real/eventos/?desde=${RT.cursor}`, {
        credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' },
      });
      if (response.status === 401) { stopPolling(); setStatus(false); return; } // sessão expirou
      if (!response.ok) { if (!RT.socketOpen) setStatus(false); return; }
      const data = await response.json();
      if (data.reset) {
        RT.cursor = data.cursor || 0;
        emit({ type: 'poll' }); // ficou muito tempo fora: recarrega tudo
      } else {
        (data.events || []).forEach(deliver);
        if (data.cursor > RT.cursor) RT.cursor = data.cursor;
      }
      if (!RT.socketOpen) setStatus(RT.mode === 'polling');
    } catch (err) {
      if (!RT.socketOpen) setStatus(false);
    } finally {
      RT.inFlight = false;
    }
  }

  async function pollLoop() {
    if (!RT.polling) return;
    await pollOnce();
    if (RT.polling) RT.timer = setTimeout(pollLoop, document.hidden ? HIDDEN_POLL_MS : RT.pollMs);
  }

  function startPolling() {
    if (RT.polling) return;
    RT.polling = true;
    pollLoop();
  }

  function stopPolling() {
    RT.polling = false;
    clearTimeout(RT.timer);
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && RT.polling) { clearTimeout(RT.timer); pollLoop(); }
  });

  function connect() {
    const wait = RT.wsPausedUntil - Date.now();
    if (wait > 0) { setTimeout(connect, wait); return; }
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    let socket;
    let opened = false;
    try {
      socket = new WebSocket(`${scheme}://${location.host}/ws/orders/`);
    } catch (err) {
      startPolling();
      return;
    }
    socket.onopen = () => {
      opened = true;
      RT.socketOpen = true;
      RT.retries = 0;
      RT.wsFailures = 0;
      stopPolling();
      setStatus(true);
      pollOnce(); // recupera o que chegou enquanto estava desconectado
    };
    socket.onmessage = (message) => {
      let data;
      try { data = JSON.parse(message.data); } catch (err) { return; }
      if (data.type === 'connection.ready') return;
      deliver(data);
    };
    socket.onclose = () => {
      RT.socketOpen = false;
      setStatus(false);
      startPolling();
      if (!opened && RT.mode === 'auto' && ++RT.wsFailures >= WS_GIVE_UP_AFTER) {
        // Servidor sem WebSocket: fica no polling e só tenta de novo daqui a pouco.
        RT.wsFailures = 0;
        RT.wsPausedUntil = Date.now() + WS_PAUSE_MS;
      }
      RT.retries += 1;
      setTimeout(connect, Math.min(30000, 1000 * 2 ** Math.min(RT.retries, 5)));
    };
  }

  NB.startRealtime = function () {
    const body = document.body;
    let mode = body.dataset.realtime;
    if (!mode || mode === 'off') return;
    if (mode === '1') mode = 'auto'; // templates antigos
    RT.mode = mode;
    RT.cursor = Number(body.dataset.realtimeCursor || 0);
    RT.pollMs = Math.max(2, Number(body.dataset.realtimePoll || 4)) * 1000;
    setStatus(false);
    // Segurança: atualiza as telas de tempos em tempos mesmo sem eventos.
    setInterval(() => emit({ type: 'poll' }), SAFETY_REFRESH_MS);
    if (mode !== 'polling' && 'WebSocket' in window) connect(); else startPolling();
  };

  // ------------------------------------------------------------ htmx
  document.addEventListener('htmx:responseError', (event) => {
    const text = event.detail.xhr && event.detail.xhr.responseText;
    let message = 'Não foi possível concluir a ação.';
    try { message = JSON.parse(text).message || message; } catch (err) { /* resposta não-JSON */ }
    NB.toast(message, 'error');
  });
  document.addEventListener('htmx:sendError', () => NB.toast('Sem conexão com o sistema. Tente de novo.', 'error'));

  // ------------------------------------------------------------ utilidades
  NB.money = (value) => Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

  NB.minutesSince = function (iso) {
    return Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  };

  // Atualiza contadores "há X min" a cada 30 s.
  function tickTimers() {
    document.querySelectorAll('[data-since]').forEach((el) => {
      const minutes = NB.minutesSince(el.dataset.since);
      el.textContent = minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)}h${String(minutes % 60).padStart(2, '0')}`;
      const late = Number(el.dataset.lateAfter || 0);
      if (late) el.closest('[data-late-card]')?.classList.toggle('ring-4', minutes >= late);
    });
  }
  setInterval(tickTimers, 30000);
  document.addEventListener('htmx:afterSettle', tickTimers);
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-autohide]').forEach((toast) => setTimeout(() => {
      toast.style.transition = 'opacity .3s ease-out';
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, 4000));
    // Mensagens do servidor no cabeçalho HX-Trigger: {"nb:toast": {"message": "...", "type": "success"}}
    document.body.addEventListener('nb:toast', (event) => NB.toast(event.detail.message, event.detail.type || 'success'));
    tickTimers();
    NB.startRealtime();
  });
})();
