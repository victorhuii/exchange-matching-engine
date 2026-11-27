const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const crypto=require('node:crypto');
const html=fs.readFileSync('web/index.html','utf8');
const source=fs.readFileSync('web/app.js','utf8');
const emptyState={sequence:0,bids:[],asks:[],orders:[],trades:[],balances:{}};
function harness(){
  const nodes=new Map();
  const element=(id)=>({id,value:'',innerHTML:'',textContent:'',disabled:false,hidden:false,dataset:{},
    classList:{add(){},remove(){},toggle(){}},setAttribute(){},addEventListener(){}});
  for(const match of html.matchAll(/\bid="([^"]+)"/g))nodes.set(match[1],element(match[1]));
  const tabs=['live','replay','benchmark'].map((view)=>({...element(view),dataset:{view}}));
  const context=vm.createContext({console,crypto,setInterval,clearInterval,
    document:{getElementById(id){assert.ok(nodes.has(id),'missing HTML ID '+id);return nodes.get(id);},querySelectorAll(selector){return selector==='.tab'?tabs:[...nodes.values()];},body:element('body')},
    fetch:async()=>({ok:true,json:async()=>structuredClone(emptyState)})});
  vm.runInContext(source,context);
  return {context,nodes};
}
test('empty book renders without invalid chart coordinates',async()=>{
  const h=harness();await new Promise(setImmediate);
  assert.match(h.nodes.get('live-depth').innerHTML,/book is empty/);
  assert.doesNotMatch(h.nodes.get('live-depth').innerHTML,/NaN|Infinity/);
  assert.match(h.nodes.get('orders-table').innerHTML,/Submit a limit order/);
  assert.equal(h.nodes.get('demo-button').disabled,false);
});
test('participant markup is escaped and large cash retains integer precision',async()=>{
  const h=harness();await new Promise(setImmediate);
  h.context.state={...structuredClone(emptyState),sequence:1,bids:[{price:10000,quantity:5,orders:1}],orders:[{order_id:'o',participant:'<img src=x>',side:'buy',price:10000,quantity:5}],balances:{alice:{cash:'999999999999999999',inventory:0}}};
  vm.runInContext('renderLive(state)',h.context);
  assert.doesNotMatch(h.nodes.get('orders-table').innerHTML,/<img/);
  assert.match(h.nodes.get('orders-table').innerHTML,/&lt;img/);
  assert.match(h.nodes.get('balances-table').innerHTML,/999,999,999,999,999,999/);
  assert.doesNotMatch(h.nodes.get('live-depth').innerHTML,/NaN|Infinity/);
});
test('API failures restore controls and expose an error',async()=>{
  const h=harness();await new Promise(setImmediate);
  h.context.fetch=async()=>({ok:false,status:503,json:async()=>({error:'storage unavailable'})});
  await vm.runInContext("task(async()=>{await api('/api/snapshot',{})})",h.context);
  assert.equal(h.nodes.get('message').className,'error');
  assert.equal(h.nodes.get('message').textContent,'storage unavailable');
  assert.equal(h.nodes.get('snapshot-button').disabled,false);
});
