/* Gráficos SVG con datos del backend, sin dependencias externas. */
const svgNS='http://www.w3.org/2000/svg';
function node(tag,attrs={},text=''){const e=document.createElementNS(svgNS,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);e.textContent=text;return e;}
const source=document.getElementById('chart-data');
if(source){
 const colors=['#e71924','#009fdf','#ffcb00','#12ad89','#9c82bc','#ff67b9'];
 JSON.parse(source.textContent).forEach((chart,index)=>{
  const section=document.createElement('section');section.className='panel padded chart';
  const h=document.createElement('h2');h.textContent=chart.title;section.append(h);
  const container=index<4?document.getElementById('charts'):document.getElementById('more-charts')||document.getElementById('charts');
  const values=chart.values.map(v=>Number(v)||0),n=values.length,max=Math.max(...values,1),unit=chart.unit??(chart.title.includes('Cumplimiento')||chart.title.includes('cumplimiento')?'%':'');
  const fmt=v=>new Intl.NumberFormat('es-PE',{maximumFractionDigits:1}).format(v)+unit;
  if(!n){const p=document.createElement('p');p.textContent='No hay datos para estos filtros.';section.append(p);container.append(section);return;}
  const svg=node('svg',{viewBox:`0 0 540 ${chart.type?'250':Math.max(190,n*40+20)}`,role:'img','aria-label':chart.title});
  if(chart.type==='donut'){
   const total=values.reduce((a,b)=>a+b,0);let offset=0;
   svg.append(node('circle',{cx:125,cy:120,r:72,fill:'none',stroke:'#edf1f7','stroke-width':30}));
   values.forEach((v,i)=>{const len=total?v/total*452.39:0;const arc=node('circle',{cx:125,cy:120,r:72,fill:'none',stroke:colors[i%6],'stroke-width':30,'stroke-dasharray':`${len} 452.39`,'stroke-dashoffset':-offset,transform:'rotate(-90 125 120)'});arc.append(node('title',{},`${chart.labels[i]}: ${v}`));svg.append(arc);offset+=len;svg.append(node('circle',{cx:263,cy:55+i*35,r:5,fill:colors[i%6]}));svg.append(node('text',{x:278,y:60+i*35,'font-size':13,fill:'#425a76'},`${chart.labels[i]} · ${total?(v/total*100).toFixed(1):0}% (${v})`));});
   svg.append(node('text',{x:125,y:123,'text-anchor':'middle','font-size':29,fill:'#14243d'},String(total)));svg.append(node('text',{x:125,y:146,'text-anchor':'middle','font-size':12,fill:'#6b819f'},'Total'));
  }else if(chart.type==='line'||chart.type==='vertical'){
   const top=chart.unit==='%'?Math.max(100,max):Math.max(1,Math.ceil(max/4)*4);
   for(let i=0;i<=4;i++){const y=190-i*40;svg.append(node('line',{x1:38,x2:522,y1:y,y2:y,stroke:'#edf1f6'}));svg.append(node('text',{x:32,y:y+4,'text-anchor':'end','font-size':10,fill:'#6b819f'},fmt(top*i/4)));}
   const coords=values.map((v,i)=>[chart.type==='vertical'?50+(i+.5)*460/n:45+i*460/Math.max(n-1,1),190-v/top*160]);
   if(chart.type==='line')svg.append(node('polyline',{points:coords.map(p=>p.join(',')).join(' '),fill:'none',stroke:'#287994','stroke-width':2}));
   coords.forEach(([x,y],i)=>{const mark=chart.type==='line'?node('circle',{cx:x,cy:y,r:4,fill:'#287994'}):node('rect',{x:x-Math.min(64,330/n)/2,y,width:Math.min(64,330/n),height:190-y,rx:4,fill:colors[i%6]});mark.append(node('title',{},`${chart.labels[i]}: ${fmt(values[i])}`));svg.append(mark);svg.append(node('text',{x,y:y-9,'text-anchor':'middle','font-size':11,fill:'#3e5874'},fmt(values[i])));
    if(n<=8||i%Math.ceil(n/8)===0||i===n-1){const label=chart.labels[i];svg.append(node('text',{x,y:214,'text-anchor':'middle','font-size':10,fill:'#526b8a'},label.length>23?label.slice(0,22)+'…':label));}
   });
  }else{values.forEach((v,i)=>{const y=i*40+10;svg.append(node('text',{x:0,y:y+16,'font-size':11,fill:'#425a76'},chart.labels[i].slice(0,26)));svg.append(node('rect',{x:185,y,width:285*v/max,height:22,rx:4,fill:colors[1]}));svg.append(node('text',{x:190+285*v/max,y:y+16,'font-size':11},fmt(v)));});}
  section.append(svg);const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Ver datos';details.append(summary);chart.labels.forEach((label,i)=>{const p=document.createElement('p');p.textContent=`${label}: ${fmt(values[i])}`;details.append(p);});section.append(details);container.append(section);
 });
}
for(const link of document.querySelectorAll('[data-sort]')){const url=new URL(location.href),key=link.dataset.sort;url.searchParams.set('orden',url.searchParams.get('orden')===key?'-'+key:key);url.searchParams.delete('page');link.href=url.toString();}
