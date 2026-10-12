/*
 * NaBandeja: utilitários das telas internas.
 *
 * - Tempo real: WebSocket /ws/orders/. Cada evento vira o evento DOM
 *   "nb:event" no <body>; partes da tela com hx-trigger="nb:event from:body"
 *   se atualizam sozinhas (htmx). Sem WebSocket, dispara "nb:event" a cada
 *   POLL_MS (polling).
 * - Sons: avisos curtos gerados no navegador (sem arquivos).
 * - Toast: mensagens rápidas, sempre como texto (nunca HTML).
 */
(function () {
  'use strict';

  const POLL_MS = 8000;
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
  let socket = null;
  let pollTimer = null;
  let retries = 0;

  function setStatus(online) {
    document.querySelectorAll('[data-realtime-status]').forEach((el) => {
      el.dataset.online = online ? '1' : '0';
      el.title = online ? 'Tempo real conectado' : 'Atualizando a cada poucos segundos';
      el.classList.toggle('bg-emerald-500', online);
      el.classList.toggle('bg-amber-400', !online);
    });
  }

  function emit(detail) {
    document.body.dispatchEvent(new CustomEvent('nb:event', { detail }));
  }

  function startPolling() {
    if (!pollTimer) pollTimer = setInterval(() => emit({ type: 'poll' }), POLL_MS);
  }

  function stopPolling() {
    clearInterval(pollTimer);
    pollTimer = null;
  }

  function connect() {
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    try {
      socket = new WebSocket(`${scheme}://${location.host}/ws/orders/`);
    } catch (err) {
      startPolling();
      return;
    }
    socket.onopen = () => { retries = 0; stopPolling(); setStatus(true); };
    socket.onmessage = (message) => {
      let data;
      try { data = JSON.parse(message.data); } catch (err) { return; }
      if (data.type === 'connection.ready') return;
      emit(data);
    };
    socket.onclose = () => {
      setStatus(false);
      startPolling();
      retries += 1;
      setTimeout(connect, Math.min(30000, 1000 * 2 ** Math.min(retries, 5)));
    };
  }

  NB.startRealtime = function () {
    if (!document.body.dataset.realtime) return;
    setStatus(false);
    if ('WebSocket' in window) connect(); else startPolling();
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
