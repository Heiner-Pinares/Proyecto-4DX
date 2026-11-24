(() => {
  const NS = 'http://www.w3.org/2000/svg';
  const read = id => { const node = document.getElementById(id); return node ? JSON.parse(node.textContent) : null; };
  const el = (tag, attrs = {}, text = '') => { const node = document.createElementNS(NS, tag); Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value)); node.textContent = text; return node; };
  const fmt = value => new Intl.NumberFormat('es-PE', {maximumFractionDigits: 1}).format(Number(value) || 0);
  const base = (label, height = 280) => el('svg', {viewBox: `0 0 900 ${height}`, role: 'img', 'aria-label': label});
  const empty = (root, message = 'No hay datos para el periodo seleccionado.') => { const p = document.createElement('p'); p.className = 'empty'; p.textContent = message; root?.append(p); };

  function axes(svg, top, bottom, left, right, max = 100, suffix = '%') {
    for (let index = 0; index <= 5; index++) {
      const value = max * index / 5, y = bottom - (bottom - top) * index / 5;
      svg.append(el('line', {x1:left, x2:right, y1:y, y2:y, class:'executive-grid'}));
      svg.append(el('text', {x:left - 12, y:y + 4, 'text-anchor':'end', class:'executive-axis'}, `${fmt(value)}${suffix}`));
    }
  }

  function lineChart(rootId, labels, values, {target = null, color = '#1677ee', suffix = '%'} = {}) {
    const root = document.getElementById(rootId); if (!root) return;
    if (!labels?.length) return empty(root);
    const svg = base(root.getAttribute('aria-label') || 'Evolución');
    const left=58, right=875, top=32, bottom=218, max=Math.max(100, target || 0, ...values.map(Number));
    axes(svg, top, bottom, left, right, max, suffix);
    if (target !== null) {
      const y = bottom - Number(target) / max * (bottom - top);
      svg.append(el('line', {x1:left,x2:right,y1:y,y2:y,class:'executive-target'}));
      svg.append(el('text',{x:right-3,y:y-8,'text-anchor':'end',class:'executive-target-label'},`Meta ${fmt(target)} ${suffix}`));
    }
    const points = values.map((value,index) => [labels.length === 1 ? (left+right)/2 : left+(right-left)*index/(labels.length-1), bottom-Number(value)/max*(bottom-top)]);
    svg.append(el('polyline',{points:points.map(point=>point.join(',')).join(' '),fill:'none',stroke:color,'stroke-width':3,'stroke-linecap':'round','stroke-linejoin':'round'}));
    points.forEach(([x,y],index)=>{svg.append(el('circle',{cx:x,cy:y,r:6,fill:'#fff',stroke:color,'stroke-width':3}));svg.append(el('text',{x,y:y-13,'text-anchor':'middle',class:'executive-value'},`${fmt(values[index])}${suffix}`));svg.append(el('text',{x,y:252,'text-anchor':'middle',class:'executive-label'},labels[index]));});
    root.append(svg);
  }

  function barChart(rootId, labels, values, {target=95}={}) {
    const root=document.getElementById(rootId);if(!root)return;if(!labels?.length)return empty(root);
    const svg=base('Cumplimiento mensual'),left=58,right=875,top=30,bottom=220,max=100;axes(svg,top,bottom,left,right,max,'%');
    const targetY=bottom-target/max*(bottom-top);svg.append(el('line',{x1:left,x2:right,y1:targetY,y2:targetY,class:'executive-target'}));svg.append(el('text',{x:right-3,y:targetY-8,'text-anchor':'end',class:'executive-target-label'},`Meta ${target} %`));
    const slot=(right-left)/labels.length,width=Math.min(95,slot*.58);
    values.forEach((value,index)=>{const x=left+slot*(index+.5)-width/2,height=Number(value)/max*(bottom-top),tone=Number(value)>=80?'#24a866':'#f3a3aa';svg.append(el('rect',{x,y:bottom-height,width,height,rx:2,fill:tone}));svg.append(el('text',{x:x+width/2,y:bottom-height-10,'text-anchor':'middle',class:Number(value)>=80?'executive-value good-text':'executive-value bad-text'},`${fmt(value)} %`));svg.append(el('text',{x:x+width/2,y:252,'text-anchor':'middle',class:'executive-label'},labels[index]));});root.append(svg);
  }

  function stacked(rootId,data){const root=document.getElementById(rootId);if(!root)return;if(!data?.labels?.length)return empty(root);const svg=base('Vencimientos por próximo corte',270),left=48,right=875,top=28,bottom=205,max=Math.max(4,...data.counts);axes(svg,top,bottom,left,right,max,'');const slot=(right-left)/data.labels.length,width=Math.min(95,slot*.5);data.counts.forEach((total,index)=>{const risk=Math.min(Number(data.risks[index]),Number(total)),safe=Number(total)-risk,x=left+slot*(index+.5)-width/2,safeH=safe/max*(bottom-top),riskH=risk/max*(bottom-top);svg.append(el('rect',{x,y:bottom-safeH,width,height:safeH,fill:'#1677ee'}));svg.append(el('rect',{x,y:bottom-safeH-riskH,width,height:riskH,fill:'#f0a800'}));svg.append(el('text',{x:x+width/2,y:bottom-safeH-riskH-9,'text-anchor':'middle',class:'executive-value'},total));svg.append(el('text',{x:x+width/2,y:242,'text-anchor':'middle',class:'executive-label'},data.labels[index]));});root.append(svg);}

  function horizontal(rootId,data){const root=document.getElementById(rootId);if(!root)return;if(!data?.labels?.length)return empty(root);const svg=base('Antigüedad de vencidos',270),max=Math.max(1,...data.values);data.labels.forEach((label,index)=>{const y=25+index*55,width=500*Number(data.values[index])/max;svg.append(el('text',{x:10,y:y+19,class:'executive-label'},label));svg.append(el('rect',{x:245,y,width,height:30,fill:'#e6242c'}));svg.append(el('text',{x:260+width,y:y+20,class:'executive-value'},data.values[index]));});root.append(svg);}

  function heatmap(rootId,data){const root=document.getElementById(rootId);if(!root)return;if(!data?.labels?.length)return empty(root);const table=document.createElement('table');table.className='heatmap';const head=document.createElement('thead'),hr=document.createElement('tr');['Jefatura',...data.labels].forEach(label=>{const th=document.createElement('th');th.textContent=label;hr.append(th);});head.append(hr);const body=document.createElement('tbody');data.offices.forEach(office=>{const row=document.createElement('tr'),name=document.createElement('th');name.textContent=office.name;row.append(name);office.values.forEach(value=>{const td=document.createElement('td');td.textContent=value===null?'—':`${fmt(value)} %`;td.dataset.level=value===null?'none':value>=80?'high':value>=70?'medium':value>=50?'low':'critical';row.append(td);});body.append(row);});table.append(head,body);root.append(table);}

  const weekly=read('weekly-data');if(weekly)lineChart('weekly-cut-chart',weekly.labels,weekly.values,{target:95});
  const upcoming=read('upcoming-cut-data');if(upcoming)stacked('upcoming-cut-chart',upcoming);
  const age=read('overdue-age-data');if(age)horizontal('overdue-age-chart',age);
  const historical=read('historical-data');if(historical){barChart('monthly-compliance-chart',historical.labels,historical.compliance);lineChart('reschedule-rate-chart',historical.labels,historical.reschedule_rate,{target:null});heatmap('office-heatmap',historical);}
})();
