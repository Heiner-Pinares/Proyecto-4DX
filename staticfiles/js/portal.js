/* Gráficos SVG locales, accesibles y sin dependencias de CDN. */
const svgNS = 'http://www.w3.org/2000/svg';
function node(tag, attrs = {}, text = '') {const e = document.createElementNS(svgNS, tag); for (const [k,v] of Object.entries(attrs)) e.setAttribute(k,v); e.textContent=text; return e;}
const source = document.getElementById('chart-data');
if (source) {
  const theme = getComputedStyle(document.documentElement);
  const palette = ['--cyan','--pink','--yellow','--orange','--red','--black'].map(name => theme.getPropertyValue(name).trim());
  for (const chart of JSON.parse(source.textContent)) {
    const section = document.createElement('section');section.className='panel padded chart';
    const title=document.createElement('h2');title.textContent=chart.title;section.append(title);
    if (!chart.values.length) {const p=document.createElement('p');p.textContent='No hay datos para estos filtros.';section.append(p);document.getElementById('charts').append(section);continue;}
    const max=Math.max(...chart.values,1), n=chart.values.length;
    const svg=node('svg',{viewBox:`0 0 540 ${chart.type==='donut'||chart.type==='line'?230:Math.max(180,n*42+20)}`,role:'img','aria-label':chart.title});
    if(chart.type==='donut') {
      const total=chart.values.reduce((a,b)=>a+b,0)||1;let offset=0;
      chart.values.forEach((v,i)=>{svg.append(node('circle',{cx:140,cy:110,r:74,fill:'none',stroke:palette[i%palette.length],'stroke-width':30,'stroke-dasharray':`${v/total*465} 465`,'stroke-dashoffset':-offset,transform:'rotate(-90 140 110)'}));offset+=v/total*465;svg.append(node('text',{x:265,y:36+i*27,fill:'#000000','font-size':14},`${chart.labels[i]}: ${v}`));});svg.append(node('text',{x:140,y:119,'text-anchor':'middle','font-size':30,fill:'#000000'},String(chart.values.reduce((a,b)=>a+b,0))));
    } else if(chart.type==='line') {
      const coords=chart.values.map((v,i)=>[40+i*450/Math.max(n-1,1),180-v/max*140]);svg.append(node('polyline',{points:coords.map(p=>p.join(',')).join(' '),fill:'none',stroke:palette[0],'stroke-width':3}));coords.forEach(([x,y],i)=>{svg.append(node('circle',{cx:x,cy:y,r:5,fill:palette[0]}));svg.append(node('text',{x,y:y-12,'text-anchor':'middle','font-size':12},`${chart.values[i]}%`));svg.append(node('text',{x,y:207,'text-anchor':'middle','font-size':10},chart.labels[i].slice(0,7)));});
    } else {
      chart.values.forEach((v,i)=>{const y=i*42+12;svg.append(node('text',{x:0,y:y+16,'font-size':12,fill:'#000000'},chart.labels[i].length>25?chart.labels[i].slice(0,24)+'…':chart.labels[i]));svg.append(node('rect',{x:185,y,width:295*v/max,height:23,rx:4,fill:palette[0]}));svg.append(node('text',{x:190+295*v/max,y:y+16,'font-size':12},String(v)));});
    }
    section.append(svg);
    const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Ver datos';details.append(summary);
    chart.labels.forEach((label,i)=>{const p=document.createElement('p');p.textContent=`${label}: ${chart.values[i]}`;details.append(p);});section.append(details);document.getElementById('charts').append(section);
  }
}
for (const link of document.querySelectorAll('[data-sort]')) {const url=new URL(location.href);const key=link.dataset.sort;url.searchParams.set('orden',url.searchParams.get('orden')===key?'-'+key:key);link.href=url.toString();}
