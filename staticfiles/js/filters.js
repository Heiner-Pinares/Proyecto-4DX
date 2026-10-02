(() => {
  document.querySelectorAll('.date-stage-dropdown').forEach(dropdown => {
    const summary = dropdown.querySelector('summary');
    const selection = dropdown.querySelector('#date-stage-selection');
    const all = dropdown.querySelector('.date-stage-all');
    const inputs = [...dropdown.querySelectorAll('input[type=checkbox]')];
    const update = () => {
      const labels = [...dropdown.querySelectorAll('input:checked')].map(input => input.parentElement.textContent.trim());
      selection.textContent = labels.length ? labels.join(', ') : 'Todas';
      all.setAttribute('aria-pressed', String(labels.length === 0));
    };
    all.addEventListener('click', () => { inputs.forEach(input => { input.checked = false; }); update(); });
    dropdown.addEventListener('change', update);
    dropdown.addEventListener('keydown', event => {
      if (event.key === 'Escape') { dropdown.open = false; summary.focus(); event.preventDefault(); }
    });
    document.addEventListener('click', event => {
      if (!dropdown.contains(event.target)) dropdown.open = false;
    });
    dropdown.addEventListener('focusout', event => {
      if (event.relatedTarget && !dropdown.contains(event.relatedTarget)) dropdown.open = false;
    });
    update();
  });
})();
