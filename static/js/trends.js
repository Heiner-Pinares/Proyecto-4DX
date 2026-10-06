(() => {
  const source = document.getElementById('trend-data');
  const root = document.getElementById('executive-trends');
  if (!source || !root) return;

  const data = JSON.parse(source.textContent);
  const labels = data.labels || [];
  const ns = 'http://www.w3.org/2000/svg';
  const svgNode = (tag, attributes = {}, text = '') => {
    const element = document.createElementNS(ns, tag);
    for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
    element.textContent = text;
    return element;
  };
  const format = value => new Intl.NumberFormat('es-PE', {maximumFractionDigits: 1}).format(Number(value) || 0);
  const panel = (title, subtitle) => {
    const section = document.createElement('section');
    section.className = 'panel trend-panel';
    const header = document.createElement('header');
    header.className = 'trend-header';
    header.innerHTML = `<div><h2>${title}</h2><p>${subtitle}</p></div>`;
    section.append(header);
    return {section, header};
  };
  const chip = (label, value, tone) => {
    const element = document.createElement('span');
    element.className = `trend-chip ${tone}`;
    element.innerHTML = `<small>${label}</small><strong>${value}</strong>`;
    return element;
  };
  const detailsTable = (columns, rows) => {
    const details = document.createElement('details');
    details.className = 'trend-data';
    const summary = document.createElement('summary');
    summary.textContent = 'Ver datos';
    const tableWrap = document.createElement('div');
    tableWrap.className = 'table-wrap';
    const table = document.createElement('table');
    const head = document.createElement('thead');
    head.innerHTML = `<tr>${columns.map(column => `<th>${column}</th>`).join('')}</tr>`;
    const body = document.createElement('tbody');
    for (const row of rows) body.innerHTML += `<tr>${row.map(value => `<td>${value}</td>`).join('')}</tr>`;
    table.append(head, body); tableWrap.append(table); details.append(summary, tableWrap);
    return details;
  };

  if (!labels.length) {
    const {section} = panel('Evolución mensual', 'Primera fecha de vencimiento');
    const empty = document.createElement('p');
    empty.className = 'empty';
    empty.textContent = 'No hay compromisos con primera fecha para los filtros seleccionados.';
    section.append(empty); root.append(section); return;
  }

  const latest = data.ultimo;
  const comparison = panel('Compromisos cumplidos vs. reprogramados', 'Comparativo mensual según la primera fecha de vencimiento');
  const comparisonSummary = document.createElement('div');
  comparisonSummary.className = 'trend-summary';
  comparisonSummary.append(
    chip(latest.label, `${latest.cumplidos} cumplidos`, 'green'),
    chip('Reprogramados', latest.reprogramados, 'amber')
  );
  comparison.header.append(comparisonSummary);
  const legend = document.createElement('div');
  legend.className = 'trend-legend';
  legend.innerHTML = '<span class="green">Cumplidos en primera fecha</span><span class="amber">Reprogramados</span>';
  comparison.section.append(legend);

  const firstSvg = svgNode('svg', {viewBox: '0 0 1000 390', role: 'img', 'aria-label': 'Comparación mensual de compromisos cumplidos en primera fecha y reprogramados'});
  const firstMax = Math.max(...data.cumplidos, ...data.reprogramados, 1);
  const firstTop = Math.max(4, Math.ceil(firstMax / 4) * 4);
  const left = 62, right = 975, top = 35, bottom = 292, plotHeight = bottom - top;
  for (let tick = 0; tick <= 4; tick++) {
    const value = firstTop * tick / 4;
    const y = bottom - plotHeight * tick / 4;
    firstSvg.append(svgNode('line', {x1:left, x2:right, y1:y, y2:y, class:'trend-grid'}));
    firstSvg.append(svgNode('text', {x:left - 12, y:y + 4, 'text-anchor':'end', class:'trend-axis'}, format(value)));
  }
  const group = (right - left) / labels.length;
  const width = Math.min(34, group * .28);
  labels.forEach((label, index) => {
    const center = left + group * (index + .5);
    const values = [data.cumplidos[index], data.reprogramados[index]];
    const fills = ['#21865f', '#f0a500'];
    values.forEach((value, position) => {
      const height = Number(value) / firstTop * plotHeight;
      const x = center + (position ? 3 : -width - 3);
      const bar = svgNode('rect', {x, y:bottom - height, width, height, rx:3, fill:fills[position]});
      bar.append(svgNode('title', {}, `${label}: ${value}`));
      firstSvg.append(bar);
      if (value) firstSvg.append(svgNode('text', {x:x + width / 2, y:bottom - height - 8, 'text-anchor':'middle', class:'trend-value'}, value));
    });
    firstSvg.append(svgNode('text', {x:center, y:322, 'text-anchor':'middle', class:'trend-label'}, label));
    firstSvg.append(svgNode('text', {x:center, y:350, 'text-anchor':'middle', class:'trend-total'}, `Total: ${data.totales[index]}`));
  });
  comparison.section.append(firstSvg);
  const firstNote = document.createElement('div');
  firstNote.className = 'trend-callout success';
  firstNote.innerHTML = `<strong>${latest.label}:</strong> ${latest.cumplidos} de ${latest.total} compromisos se cumplieron en primera fecha (${format(latest.cumplimiento)} %).`;
  comparison.section.append(firstNote);
  comparison.section.append(detailsTable(
    ['Mes', 'Total', 'Cumplidos en primera fecha', 'Reprogramados'],
    labels.map((label, index) => [label, data.totales[index], data.cumplidos[index], data.reprogramados[index]])
  ));
  root.append(comparison.section);

  const target = panel('Cumplimiento en primera fecha vs. meta', 'Evolución mensual del indicador');
  const cards = document.createElement('div');
  cards.className = 'trend-kpis';
  cards.append(
    chip('Último mes', `${format(latest.cumplimiento)} %`, 'plain'),
    chip('Meta promedio', `${format(data.meta)} %`, 'plain'),
    chip(latest.brecha > 0 ? 'Brecha a la meta' : 'Meta superada', `${format(Math.abs(latest.brecha))} pp`, latest.brecha > 0 ? 'amber' : 'green')
  );
  target.section.append(cards);
  const secondLegend = document.createElement('div');
  secondLegend.className = 'trend-legend';
  secondLegend.innerHTML = `<span class="green line">Cumplimiento mensual</span><span class="amber dashed">Meta ${format(data.meta)} %</span>`;
  target.section.append(secondLegend);

  const secondSvg = svgNode('svg', {viewBox:'0 0 1000 360', role:'img', 'aria-label':'Cumplimiento mensual en primera fecha comparado con la meta'});
  const percentTop = Math.max(100, Math.ceil(Number(data.meta) / 10) * 10);
  const pTop = 30, pBottom = 285, pHeight = pBottom - pTop;
  for (let tick = 0; tick <= 5; tick++) {
    const value = percentTop * tick / 5;
    const y = pBottom - pHeight * tick / 5;
    secondSvg.append(svgNode('line', {x1:left, x2:right, y1:y, y2:y, class:'trend-grid'}));
    secondSvg.append(svgNode('text', {x:left - 12, y:y + 4, 'text-anchor':'end', class:'trend-axis'}, `${format(value)} %`));
  }
  const targetY = pBottom - Number(data.meta) / percentTop * pHeight;
  secondSvg.append(svgNode('line', {x1:left, x2:right, y1:targetY, y2:targetY, class:'target-line'}));
  secondSvg.append(svgNode('text', {x:left + 4, y:targetY - 9, class:'target-label'}, `Meta: ${format(data.meta)} %`));
  const points = data.cumplimiento.map((value, index) => {
    const x = labels.length === 1 ? (left + right) / 2 : left + (right - left) * index / (labels.length - 1);
    return [x, pBottom - Number(value) / percentTop * pHeight];
  });
  secondSvg.append(svgNode('polyline', {points:points.map(point => point.join(',')).join(' '), class:'compliance-line'}));
  points.forEach(([x, y], index) => {
    secondSvg.append(svgNode('circle', {cx:x, cy:y, r:6, class:'compliance-point'}));
    secondSvg.append(svgNode('text', {x, y:y - 13, 'text-anchor':'middle', class:'trend-value'}, `${format(data.cumplimiento[index])} %`));
    secondSvg.append(svgNode('text', {x, y:318, 'text-anchor':'middle', class:'trend-label'}, labels[index]));
  });
  target.section.append(secondSvg);
  const previous = data.cumplimiento.length > 1 ? Number(data.cumplimiento[data.cumplimiento.length - 2]) : null;
  const movement = previous === null ? '' : latest.cumplimiento > previous ? ' mejoró y' : latest.cumplimiento < previous ? ' disminuyó y' : '';
  const targetNote = document.createElement('div');
  targetNote.className = `trend-callout ${latest.brecha > 0 ? 'warning' : 'success'}`;
  targetNote.textContent = latest.brecha > 0
    ? `En ${latest.label}, el cumplimiento${movement} está ${format(latest.brecha)} puntos porcentuales por debajo de la meta.`
    : `En ${latest.label}, el cumplimiento alcanzó o superó la meta por ${format(Math.abs(latest.brecha))} puntos porcentuales.`;
  target.section.append(targetNote);
  target.section.append(detailsTable(
    ['Mes', 'Cumplimiento', 'Meta'],
    labels.map((label, index) => [label, `${format(data.cumplimiento[index])} %`, `${format(data.meta)} %`])
  ));
  root.append(target.section);
})();
