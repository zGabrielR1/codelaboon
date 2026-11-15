'use strict';
// Connect only to the isolated test editor's loopback debugging endpoint.
const port=Number(process.argv[2]);
const mode=process.argv[3];
async function inspect(target) {
  const ws=new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((ok,bad)=>{ws.onopen=ok;ws.onerror=bad;});
  const pending=new Map();let sequence=0;const contexts=[];
  ws.onmessage=event=>{const msg=JSON.parse(event.data);if(msg.method==='Runtime.executionContextCreated')contexts.push(msg.params.context.id);
    if(msg.id&&pending.has(msg.id)){const [ok,bad]=pending.get(msg.id);pending.delete(msg.id);msg.error?bad(new Error(msg.error.message)):ok(msg.result);}};
  const send=(method,params={})=>new Promise((ok,bad)=>{const id=++sequence;pending.set(id,[ok,bad]);ws.send(JSON.stringify({id,method,params}));});
  try {
    await send('Runtime.enable');await new Promise(r=>setTimeout(r,100));
    for(const contextId of contexts) {
      const expression=mode==='reply' ? 'document.body?.innerText.includes("Fixture reply: accepted.")' : `(()=>{const node=[...document.querySelectorAll('textarea,[contenteditable]:not([contenteditable="false"])')].find(n=>(n.value||n.textContent||'').includes('IDE_BACKEND_PROBE'));if(!node)return false;node.focus();return true;})()`;
      let result;
      try {result=await send('Runtime.evaluate',{expression,contextId,returnByValue:true});} catch {continue;}
      if(process.env.CODELABOON_VSCODE_PROBE_DEBUG==='1' && result.result?.value!==true) {
        const debug=await send('Runtime.evaluate',{expression:JSON.stringify('')+' || JSON.stringify({title:document.title,text:document.body?.innerText.slice(-1600),editable:[...document.querySelectorAll(\'textarea,[contenteditable]\')].map(n=>n.value||n.textContent)})',contextId,returnByValue:true});console.error(target.url,contextId,debug.result?.value);
      }
      if(result.result?.value===true) {
        if(mode==='send') {await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});}
        return true;
      }
    }
    return false;
  } finally {ws.close();}
}
(async()=>{
  const targets=await (await fetch('http://127.0.0.1:'+port+'/json/list')).json();
  for(const target of targets.filter(t=>t.webSocketDebuggerUrl)) if(await inspect(target)){console.log('matched');return;}
  process.exitCode=1;
})().catch(error=>{console.error(error.message);process.exitCode=1;});
setTimeout(()=>process.exit(2),5000).unref();
