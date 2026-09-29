import {test,after,before} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {Miniflare,convertV4MiniflareOptions} from 'miniflare';
const mf=new Miniflare(convertV4MiniflareOptions({modules:true,scriptPath:'.wrangler/test/index.js',compatibilityDate:'2026-09-28',compatibilityFlags:['nodejs_compat'],d1Databases:['DB'],r2Buckets:['SCREENSHOTS'],durableObjects:{CONTROL:{className:'ControlSession',useSQLite:true}},bindings:{CONTROL_TOKEN:'test'}}));
let db;
before(async()=>{
  db=await mf.getD1Database('DB');
  for(const statement of (await readFile('schema.sql','utf8')).split(';').filter(s=>s.trim())) await db.prepare(statement).run();
});
after(()=>mf.dispose());
const request=(path,body)=>mf.dispatchFetch('https://example.com'+path,{method:body?'POST':'GET',headers:{'x-control-token':'test','content-type':'application/json'},body:body?JSON.stringify(body):undefined});

test('hibernating pings update live presence without database writes',async()=>{
  const res=await mf.dispatchFetch('https://example.com/ws?agent_id=idle-test',{headers:{Upgrade:'websocket','x-control-token':'test','x-firetrace-protocol':'2'}});
  const ws=res.webSocket;
  const messages=[];
  ws.addEventListener('message',event=>messages.push(event.data));
  ws.accept();
  const until=async predicate=>{
    const deadline=Date.now()+3000;
    while(!predicate() && Date.now()<deadline) await new Promise(r=>setTimeout(r,10));
    assert.ok(predicate(),'expected WebSocket response');
  };
  try {
    await until(()=>messages.some(m=>m.includes('hibernation-heartbeat')));
    await db.prepare("UPDATE agent_state SET last_seen=1 WHERE agent_id='idle-test'").run();
    const before=await db.prepare('SELECT COUNT(*) AS n FROM events').first();
    for(let i=0;i<5;i++) ws.send('firetrace:ping');
    await until(()=>messages.filter(m=>m==='firetrace:pong').length===5);
    const state=await (await request('/api/state?agent_id=idle-test')).json();
    assert.equal(state.state.connected,true);
    assert.ok(state.state.last_seen>1);
    assert.equal((await db.prepare("SELECT last_seen FROM agent_state WHERE agent_id='idle-test'").first()).last_seen,1);
    assert.deepEqual(await db.prepare('SELECT COUNT(*) AS n FROM events').first(),before);
    await db.prepare("INSERT INTO commands(id,agent_id,action,status,created_at,finished_at,result_json) VALUES ('finished','idle-test','wait','done',1,2,'{}')").run();
    ws.send(JSON.stringify({type:'started',id:'finished',started_at:1}));
    await new Promise(r=>setTimeout(r,100));
    assert.equal((await db.prepare("SELECT status FROM commands WHERE id='finished'").first()).status,'done');
    let executions=0;
    ws.addEventListener('message',event=>{
      let message; try {message=JSON.parse(event.data);} catch {return;}
      if(message.type!=='command') return;
      executions++;
      ws.send(JSON.stringify({type:'started',id:message.command.id,started_at:1}));
      ws.send(JSON.stringify({type:'result',id:message.command.id,ok:true,started_at:1,finished_at:2,result:{executions}}));
    });
    const command={agent_id:'idle-test',id:'single-execution',action:'wait',require_online:true,wait_ms:2000};
    const first=await (await request('/api/rpc',command)).json();
    assert.equal(first.status,'done');
    const duplicate=await (await request('/api/rpc',command)).json();
    assert.equal(duplicate.status,'done');
    assert.equal(executions,1);
  } finally {ws.close();}
});

test('offline immediate RPC is not queued for later browser execution',async()=>{
  const response=await request('/api/rpc',{agent_id:'offline',id:'offline-command',action:'click',args:{x:1,y:1},require_online:true,wait_ms:0});
  assert.equal(response.status,503);
  const row=await db.prepare("SELECT status FROM commands WHERE id='offline-command'").first();
  assert.equal(row.status,'error');
});
