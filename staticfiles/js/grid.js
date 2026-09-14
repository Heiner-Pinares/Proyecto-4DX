(() => {
  const table = document.getElementById('commitment-sheet');
  if (!table) return;
  const rows = new Map(JSON.parse(document.getElementById('grid-rows').textContent).map(row => [String(row.id), row]));
  const states = JSON.parse(document.getElementById('grid-options').textContent);
  const status = document.getElementById('save-status');
  const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
  let active = null;
  let busy = false;
  const say = (message, error = false) => { status.textContent = message; status.classList.toggle('save-error', error); };
  function redraw(tr, row) {
    rows.set(String(row.id), row); tr.dataset.version = row.version;
    for (const cell of row.cells) {
      const td = tr.querySelector(`[data-field="${cell.name}"]`);
      td.querySelector('.cell-value, .cell-display').textContent = cell.display;
      if (cell.name === 'status') td.dataset.status = cell.value || '';
      if (cell.name === 'puntaje') td.dataset.score = cell.value || '';
    }
  }
  function cancel() {
    if (!active || busy) return;
    const old = active; active = null;
    old.form.remove(); old.button.hidden = false; old.td.classList.remove('editing');
    old.button.focus(); say('Sin cambios pendientes');
  }
  async function save(next = null) {
    if (!active || busy) return;
    const current = active;
    if (!current.form.reportValidity()) return;
    const value = current.kind === 'boolean' ? current.input.value === 'true' : current.input.value;
    if (String(value ?? '') === String(current.cell.value ?? '')) { cancel(); if (next) open(next); return; }
    busy = true; say('Guardando…'); current.td.classList.add('saving');
    for (const element of current.form.elements) element.disabled = true;
    try {
      const response = await fetch(current.tr.dataset.url, {method: 'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRFToken':csrf}, body:JSON.stringify({field:current.cell.name, value, version:current.tr.dataset.version, reason:current.reason ? current.reason.value : ''})});
      if (response.redirected) throw new Error('Tu sesión venció. Abre el portal de nuevo e inicia sesión; el cambio no se guardó.');
      const data = await response.json().catch(() => ({error:'No fue posible guardar. Comprueba tu sesión e inténtalo otra vez.'}));
      if (!response.ok) throw new Error(data.error || 'No se pudo guardar el cambio.');
      current.form.remove(); current.button.hidden = false; current.td.classList.remove('editing'); active = null;
      redraw(current.tr, data.row); say('✓ Cambio guardado'); current.button.focus();
      busy = false; if (next) open(next);
    } catch (error) {
      say(error.message || 'Sin conexión. El cambio sigue pendiente; vuelve a guardar.', true);
      for (const element of current.form.elements) element.disabled = false;
      current.input.focus();
    } finally { busy = false; current.td.classList.remove('saving'); }
  }
  function open(button) {
    if (busy || (active && active.button === button)) return;
    if (active) { save(button); return; }
    const td = button.closest('td'), tr = button.closest('tr');
    const cell = rows.get(tr.dataset.id).cells.find(cell => cell.name === td.dataset.field);
    const form = document.createElement('form'); form.className = 'cell-editor';
    const input = document.createElement(cell.kind === 'textarea' ? 'textarea' : ['select','boolean'].includes(cell.kind) ? 'select' : 'input');
    if (input.tagName === 'INPUT') { input.type = cell.kind === 'number' ? 'number' : cell.kind === 'date' ? 'date' : 'text'; if (cell.kind === 'number') {input.min='0';input.step='0.01';} }
    if (cell.kind === 'select' || cell.kind === 'boolean') {
      const options = cell.kind === 'boolean' ? [{codigo:'true',nombre:'Sí'},{codigo:'false',nombre:'No'}] : [...states];
      if (cell.kind === 'select' && !options.some(s => s.codigo === cell.value)) options.push({codigo:cell.value,nombre:cell.value});
      for (const item of options) {const option = document.createElement('option');option.value=item.codigo;option.textContent=cell.kind === 'select' ? `${item.codigo} · ${item.nombre}` : item.nombre;input.append(option);}
    }
    input.value = cell.value ?? ''; input.setAttribute('aria-label', cell.label);
    if (['tema','iniciativa','tarea','responsable_pyp','status'].includes(cell.name)) input.required=true;
    form.append(input);
    let reason = null;
    if (['primera_fecha','segunda_fecha','tercera_fecha'].includes(cell.name)) {
      reason=document.createElement('input');reason.type='text';reason.placeholder='Motivo del cambio';reason.required=true;reason.setAttribute('aria-label','Motivo del cambio');form.append(reason);
    }
    const actions=document.createElement('div');actions.className='cell-editor-actions';
    const accept=document.createElement('button');accept.type='submit';accept.textContent='Guardar';
    const dismiss=document.createElement('button');dismiss.type='button';dismiss.textContent='Cancelar';dismiss.addEventListener('click',cancel);
    actions.append(accept,dismiss);form.append(actions);
    active={button,td,tr,cell,kind:cell.kind,form,input,reason};button.hidden=true;td.classList.add('editing');td.append(form);
    form.addEventListener('submit',event=>{event.preventDefault();save();});
    form.addEventListener('keydown',event=>{
      if (event.key==='Escape') {event.preventDefault();cancel();}
      if (event.key==='Enter' && !(input.tagName==='TEXTAREA' && event.shiftKey)) {event.preventDefault();save();}
      if (event.key==='Tab' && (!reason || event.target===reason)) {
        event.preventDefault();const buttons=[...table.querySelectorAll('.cell-value')];const next=buttons[buttons.indexOf(button)+(event.shiftKey?-1:1)];save(next || null);
      }
    });
    input.focus();if(input.type==='text'||input.tagName==='TEXTAREA') input.select();say('Editando · Enter para guardar');
  }
  table.addEventListener('click',event=>{const button=event.target.closest('.cell-value');if(button) open(button);});
  table.addEventListener('keydown',event=>{
    if(active||!event.target.matches('.cell-value'))return;
    const buttons=[...table.querySelectorAll('.cell-value')];let next;
    if(event.key==='ArrowRight')next=buttons[buttons.indexOf(event.target)+1];
    if(event.key==='ArrowLeft')next=buttons[buttons.indexOf(event.target)-1];
    if(event.key==='ArrowDown'||event.key==='ArrowUp') {const tr=event.target.closest('tr');const other=event.key==='ArrowDown'?tr.nextElementSibling:tr.previousElementSibling;next=other?.querySelector(`[data-field="${event.target.closest('td').dataset.field}"] .cell-value`);}
    if(next){event.preventDefault();next.focus();}
  });
  window.addEventListener('beforeunload',event=>{if(active){event.preventDefault();event.returnValue='';}});
  for(const tr of table.querySelectorAll('tbody tr[data-id]')) redraw(tr,rows.get(tr.dataset.id));
})();
