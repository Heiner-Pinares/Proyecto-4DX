(() => {
  const panel = document.getElementById('ai-panel');
  const launcher = document.getElementById('ai-launcher');
  if (!panel || !launcher) return;

  const messages = document.getElementById('ai-messages');
  const form = document.getElementById('ai-form');
  const question = document.getElementById('ai-question');
  const status = document.getElementById('ai-status');
  const send = form.querySelector('.ai-send');
  const csrf = form.querySelector('[name=csrfmiddlewaretoken]').value;
  let conversationId = null;
  let busy = false;
  let historyLoaded = false;

  const setOpen = open => {
    panel.classList.toggle('open', open);
    panel.setAttribute('aria-hidden', String(!open));
    launcher.setAttribute('aria-expanded', String(open));
    sessionStorage.setItem('portal4dx.ai.open', open ? '1' : '0');
    if (open) {
      loadHistory();
      setTimeout(() => question.focus(), 120);
    }
  };

  const scrollEnd = () => { messages.scrollTop = messages.scrollHeight; };
  const clearRendered = () => { messages.replaceChildren(); };

  const appendInline = (container, text) => {
    const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
    parts.forEach(part => {
      if (part.startsWith('`') && part.endsWith('`')) {
        const code = document.createElement('code'); code.textContent = part.slice(1, -1); container.append(code);
      } else if (part.startsWith('**') && part.endsWith('**')) {
        const strong = document.createElement('strong'); strong.textContent = part.slice(2, -2); container.append(strong);
      } else container.append(document.createTextNode(part));
    });
  };

  const renderSafeMarkdown = (container, value) => {
    const lines = String(value || '').replace(/\r/g, '').split('\n');
    let list = null, code = null;
    for (let index = 0; index < lines.length; index += 1) {
      const line = lines[index];
      if (line.startsWith('```')) {
        if (code) { container.append(code); code = null; } else { code = document.createElement('pre'); }
        list = null; continue;
      }
      if (code) { code.textContent += (code.textContent ? '\n' : '') + line; continue; }
      const next = lines[index + 1] || '';
      if (line.includes('|') && /^\s*\|?\s*:?-{3,}/.test(next)) {
        const table = document.createElement('table');
        const parseRow = row => row.replace(/^\s*\||\|\s*$/g, '').split('|').map(cell => cell.trim());
        const head = document.createElement('thead'), headRow = document.createElement('tr');
        parseRow(line).forEach(value => { const th = document.createElement('th'); appendInline(th, value); headRow.append(th); });
        head.append(headRow); table.append(head); index += 1;
        const body = document.createElement('tbody');
        while (index + 1 < lines.length && lines[index + 1].includes('|') && lines[index + 1].trim()) {
          index += 1;
          const row = document.createElement('tr');
          parseRow(lines[index]).forEach(value => { const td = document.createElement('td'); appendInline(td, value); row.append(td); });
          body.append(row);
        }
        table.append(body); container.append(table); list = null; continue;
      }
      const item = line.match(/^\s*[-*]\s+(.+)/);
      if (item) {
        if (!list) { list = document.createElement('ul'); container.append(list); }
        const li = document.createElement('li'); appendInline(li, item[1]); list.append(li); continue;
      }
      list = null;
      if (!line.trim()) continue;
      const heading = line.match(/^(#{1,3})\s+(.+)/);
      const node = document.createElement(heading ? `h${Math.min(heading[1].length + 2, 5)}` : 'p');
      appendInline(node, heading ? heading[2] : line);
      container.append(node);
    }
    if (code) container.append(code);
  };

  const copyText = async value => {
    if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(value);
    const field = document.createElement('textarea');
    field.value = value; field.setAttribute('readonly', ''); field.style.position = 'fixed'; field.style.opacity = '0';
    document.body.append(field); field.select();
    const copied = document.execCommand('copy'); field.remove();
    if (!copied) throw new Error('copy unavailable');
  };

  const addMessage = (role, content) => {
    const article = document.createElement('article'); article.className = `ai-message ${role}`;
    const bubble = document.createElement('div'); renderSafeMarkdown(bubble, content); article.append(bubble);
    if (role === 'assistant') {
      const copy = document.createElement('button'); copy.type = 'button'; copy.className = 'ai-copy'; copy.textContent = 'Copiar';
      copy.addEventListener('click', async () => {
        try { await copyText(content); copy.textContent = 'Copiado'; }
        catch { copy.textContent = 'No se pudo copiar'; }
        setTimeout(() => { copy.textContent = 'Copiar'; }, 1600);
      });
      bubble.append(copy);
    }
    messages.append(article); scrollEnd();
  };

  const request = async (url, options = {}) => {
    const response = await fetch(url, {credentials: 'same-origin', ...options});
    let data;
    try { data = await response.json(); } catch { data = {success: false, error: 'El servidor devolvió una respuesta no válida.'}; }
    if (!response.ok || !data.success) throw new Error(data.error || 'No se pudo completar la solicitud.');
    return data;
  };

  const loadHistory = async () => {
    if (historyLoaded) return;
    historyLoaded = true;
    try {
      const data = await request(panel.dataset.historyUrl);
      conversationId = data.conversation_id;
      if (data.messages?.length) {
        clearRendered();
        data.messages.forEach(message => addMessage(message.role, message.content));
      }
    } catch (error) { status.textContent = error.message; }
  };

  const setBusy = value => {
    busy = value; send.disabled = value; question.disabled = value;
    status.textContent = value ? 'El asistente está pensando…' : '';
  };

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const text = question.value.trim();
    if (!text || busy) return;
    addMessage('user', text); question.value = ''; setBusy(true);
    try {
      const data = await request(panel.dataset.chatUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
        body: JSON.stringify({pregunta: text, conversation_id: conversationId}),
      });
      conversationId = data.conversation_id; addMessage('assistant', data.respuesta);
    } catch (error) {
      status.textContent = error.message;
      addMessage('error', error.message);
    } finally { setBusy(false); question.focus(); }
  });

  question.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); }
  });
  launcher.addEventListener('click', () => setOpen(!panel.classList.contains('open')));
  panel.querySelectorAll('[data-ai-action]').forEach(button => button.addEventListener('click', async () => {
    const action = button.dataset.aiAction;
    if (action === 'close' || action === 'minimize') setOpen(false);
    if (action === 'expand') panel.classList.toggle('expanded');
    if (action === 'clear' && !busy) {
      try {
        await request(panel.dataset.clearUrl, {method: 'POST', headers: {'X-CSRFToken': csrf}});
        conversationId = null; clearRendered(); addMessage('assistant', 'Nueva conversación iniciada. ¿En qué puedo ayudarte?'); status.textContent = '';
      } catch (error) { status.textContent = error.message; }
    }
  }));
  panel.querySelectorAll('.ai-suggestions button').forEach(button => button.addEventListener('click', () => { question.value = button.textContent; question.focus(); }));
  if (sessionStorage.getItem('portal4dx.ai.open') === '1') setOpen(true);
})();
