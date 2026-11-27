'use strict';
const $=(id)=>document.getElementById(id);
const escape=(value)=>String(value).replace(/[&<>"']/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const format=(value)=>Number(value).toLocaleString();
let live, replay, frame=0, timer=null, busy=false, pending=null;
const cancellations=new Map();

function message(text,error=false){
  $('message').hidden=false;$('message').className=error?'error':'';
  $('message').textContent=text;
}
async function api(path,body){
  const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const result=await response.json();
  if(!response.ok){const error=new Error(result.error||'Request failed');error.status=response.status;throw error;}
  return result;
}
async function task(fn){
  if(busy)return;busy=true;document.body.classList.add('busy');
  document.querySelectorAll('button,input,select').forEach((e)=>{e.disabled=true;});
  try{await fn();}catch(error){message(error.message,true);}
  finally{busy=false;document.body.classList.remove('busy');document.querySelectorAll('button,input,select').forEach((e)=>{e.disabled=false;});}
}
const empty=(columns,text)=>'<tr><td colspan="'+columns+'" class="empty">'+escape(text)+'</td></tr>';
const metric=(label,value)=>'<div class="metric"><span>'+escape(label)+'</span><strong>'+escape(value)+'</strong></div>';

function depth(state,id){
  const max=Math.max(1,...state.bids.slice(0,8).map((l)=>l.quantity),...state.asks.slice(0,8).map((l)=>l.quantity));
  let svg='<line x1="450" x2="450" y1="10" y2="224" stroke="#dde3e8"/>';
  for(let i=0;i<8;i++){
    const bid=state.bids[i],ask=state.asks[i],y=22+i*26;
    if(bid){const width=310*bid.quantity/max;svg+='<rect x="'+(390-width)+'" y="'+y+'" width="'+width+'" height="17" rx="2" fill="#598d78"/><text class="chart-label" x="440" y="'+(y+13)+'" text-anchor="end">'+bid.price+'</text><text class="chart-label" x="65" y="'+(y+13)+'" text-anchor="end">'+bid.quantity+'</text>';}
    if(ask){const width=310*ask.quantity/max;svg+='<rect x="510" y="'+y+'" width="'+width+'" height="17" rx="2" fill="#c88981"/><text class="chart-label" x="460" y="'+(y+13)+'">'+ask.price+'</text><text class="chart-label" x="835" y="'+(y+13)+'">'+ask.quantity+'</text>';}
  }
  if(!state.bids.length&&!state.asks.length)svg='<text class="chart-label" x="450" y="120" text-anchor="middle">The book is empty. Submit an order or run the simulated flow.</text>';
  $(id).innerHTML=svg;
}

function renderBook(state,prefix){
  const volume=state.trades.reduce((sum,t)=>sum+t.quantity,0);
  $(prefix+'-metrics').innerHTML=metric('Accepted commands',format(state.sequence))+metric('Resting orders',format(state.orders.length))+metric('Executions',format(state.trades.length))+metric('Traded units',format(volume));
  $(prefix+'-spread').textContent=state.bids.length&&state.asks.length?'Spread '+(state.asks[0].price-state.bids[0].price)+' ticks':'Waiting for both sides';
  depth(state,prefix+'-depth');
  for(const side of ['bids','asks'])$(prefix+'-'+side).innerHTML=state[side].slice(0,8).map((l)=>'<tr><td class="'+(side==='bids'?'buy':'sell')+'">'+format(l.price)+'</td><td>'+format(l.quantity)+'</td><td>'+l.orders+'</td></tr>').join('')||empty(3,'No resting '+side);
}

function renderLive(state){
  live=state;renderBook(state,'live');
  $('orders-table').innerHTML=state.orders.map((o)=>'<tr><td>'+escape(o.order_id)+'</td><td>'+escape(o.participant)+'</td><td class="'+o.side+'">'+o.side+'</td><td>'+format(o.price)+'</td><td>'+format(o.quantity)+'</td><td><button class="cancel" data-cancel="'+escape(o.order_id)+'">Cancel</button></td></tr>').join('')||empty(6,'Submit a limit order to start.');
  $('trades-table').innerHTML=state.trades.slice(-40).reverse().map((t)=>'<tr><td>'+t.trade_id+'</td><td>'+escape(t.buyer)+'</td><td>'+escape(t.seller)+'</td><td>'+format(t.price)+'</td><td>'+format(t.quantity)+'</td><td>'+escape(t.maker)+'</td></tr>').join('')||empty(6,'No executions yet.');
  $('balances-table').innerHTML=Object.entries(state.balances).map(([owner,b])=>'<tr><td>'+escape(owner)+'</td><td>'+format(b.inventory)+'</td><td>'+escape(BigInt(b.cash).toLocaleString())+'</td></tr>').join('')||empty(3,'Balances appear after a trade.');
}

function stopReplay(){clearInterval(timer);timer=null;$('play-button').textContent='Play replay';}
function renderReplay(){
  if(!replay)return;
  const event=replay[frame],c=event.command,r=event.result;
  $('replay-slider').max=replay.length-1;$('replay-slider').value=frame;
  $('replay-position').textContent=(frame+1)+' / '+replay.length+' commands';
  const action=c.type==='cancel'?'cancel '+c.order_id:c.side+' '+c.quantity+' at '+c.price+' ticks ('+c.tif+')';
  $('replay-command').textContent=c.participant+': '+action+'. Filled '+r.filled+', resting '+r.resting+', cancelled '+r.cancelled+'.';
  renderBook(event.state,'replay');
}
function renderBenchmark(data){
  if(!data){$('benchmark-content').innerHTML='<p>No benchmark recorded. Run python3 -m scripts.benchmark.</p>';return;}
  const rows=Object.entries(data.results).map(([name,r])=>'<tr><td>'+(name==='memory'?'Memory-only C++':'Journal + fsync')+'</td><td>'+format(Math.round(r.commands_per_second))+'</td><td>'+r.latency_us.p50.toFixed(3)+' µs</td><td>'+r.latency_us.p95.toFixed(3)+' µs</td><td>'+r.latency_us.p99.toFixed(3)+' µs</td></tr>').join('');
  const sample=data.results.memory;
  $('benchmark-content').innerHTML='<div class="table-wrap"><table><thead><tr><th>Processing path</th><th>Commands / s</th><th>p50</th><th>p95</th><th>p99</th></tr></thead><tbody>'+rows+'</tbody></table></div><p class="benchmark-note">'+format(sample.commands)+' commands, '+sample.trades+' trades, '+sample.cancels+' cancellations and up to '+sample.max_resting_orders+' resting orders. One recorded run; no warmup.</p><p class="benchmark-note">'+escape(data.workload)+'</p><p class="benchmark-note">'+escape(data.timing)+'</p><p class="benchmark-note"><strong>Machine:</strong> '+escape(data.machine)+'<br><strong>Compiler:</strong> '+escape(data.compiler)+'<br><strong>Build:</strong> <code>'+escape(data.build_flags)+'</code></p><p class="notice">These are small-book local measurements. IPC, HTTP and exchange queueing delays are not included. The durable path uses per-command fsync; filesystem and storage hardware affect the result.</p>';
}

document.querySelectorAll('.tab').forEach((button)=>button.addEventListener('click',()=>{
  stopReplay();
  document.querySelectorAll('.tab').forEach((tab)=>{const active=tab===button;tab.classList.toggle('active',active);tab.setAttribute('aria-pressed',String(active));});
  for(const view of ['live','replay','benchmark'])$(view+'-view').hidden=view!==button.dataset.view;
  if(button.dataset.view==='live')task(async()=>renderLive(await api('/api/state')));
  if(button.dataset.view==='replay')task(async()=>{if(!replay)replay=await api('/api/replay');renderReplay();});
  if(button.dataset.view==='benchmark')task(async()=>renderBenchmark(await api('/api/benchmark')));
}));
$('order-form').addEventListener('submit',(event)=>{
  event.preventDefault();const values=Object.fromEntries(new FormData(event.target));
  task(async()=>{
    if(!pending){const id=crypto.randomUUID();pending={...values,type:'order',price:Number(values.price),quantity:Number(values.quantity),request_id:id,order_id:id.slice(0,8)};}
    let data;
    try{data=await api('/api/command',pending);}
    catch(error){if(error.status&&error.status<500)pending=null;else error.message+=' Submit again to retry the original saved order; keep this page open.';throw error;}
    pending=null;renderLive(data.state);
    message('Command '+data.result.sequence+' accepted. Filled '+data.result.filled+', resting '+data.result.resting+', cancelled '+data.result.cancelled+'. Bridge round trip '+data.bridge_roundtrip_us.toFixed(0)+' µs (includes IPC, excludes HTTP).');
  });
});
$('orders-table').addEventListener('click',(event)=>{
  const button=event.target.closest('[data-cancel]');if(!button)return;
  const o=live.orders.find((order)=>order.order_id===button.dataset.cancel);
  task(async()=>{
    if(!cancellations.has(o.order_id))cancellations.set(o.order_id,crypto.randomUUID());
    const data=await api('/api/command',{type:'cancel',request_id:cancellations.get(o.order_id),order_id:o.order_id,participant:o.participant});
    cancellations.delete(o.order_id);renderLive(data.state);message('Order cancelled and journaled.');
  });
});
$('demo-button').addEventListener('click',()=>task(async()=>{const data=await api('/api/demo',{});renderLive(data.state);message('100 synthetic participant commands journaled. Every response matched the independent reference.');}));
$('snapshot-button').addEventListener('click',()=>task(async()=>{const data=await api('/api/snapshot',{});message('Materialized snapshot saved at command '+data.sequence+'.');}));
$('recover-button').addEventListener('click',()=>task(async()=>{const data=await api('/api/recover',{});renderLive(data.state);message(data.identical?'Recovery verified: book, trades and balances are identical.':'Recovered state differs from memory; inspect the exported session.',!data.identical);}));
$('replay-slider').addEventListener('input',(event)=>{frame=Number(event.target.value);renderReplay();});
$('play-button').addEventListener('click',()=>{
  if(!replay)return;
  if(timer){stopReplay();return;}
  if(frame>=replay.length-1)frame=0;
  $('play-button').textContent='Pause replay';
  timer=setInterval(()=>{if(busy)return;frame=Math.min(frame+1,replay.length-1);renderReplay();if(frame>=replay.length-1)stopReplay();},400);
});
task(async()=>renderLive(await api('/api/state')));
