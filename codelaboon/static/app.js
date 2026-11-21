const params=new URLSearchParams(location.search);
const requestedTask=params.get('task');
const requestedProvider=params.get('provider');
const $=s=>document.querySelector(s);let token='',providers=[],busy=false,discovery=0;
let sessions=[];try{sessions=JSON.parse(localStorage.getItem('codelaboon.chats')||'[]');if(!Array.isArray(sessions))sessions=[]}catch{}
let current=null,controller=null,showArchived=false;
function saveDraft(){if(!current)return;try{localStorage.setItem('codelaboon.draft.'+current.id,$('#prompt').value);localStorage.setItem('codelaboon.activeDraft',JSON.stringify({chat:current,text:$('#prompt').value}))}catch{}}
function restoreDraft(){try{$('#prompt').value=localStorage.getItem('codelaboon.draft.'+current.id)||''}catch{}}
$('#prompt').addEventListener('input',saveDraft);
window.addEventListener('beforeunload',saveDraft);
function persist(){try{localStorage.setItem('codelaboon.chats',JSON.stringify(sessions))}catch{showError('Browser storage is full. Export your conversation to keep a copy.')}}
function showError(text){if($('#error').textContent!==text)$('#error').textContent=text;$('#error').hidden=!text}
async function api(path,options){const r=await fetch(path,options);const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data}
function newChat(){if(busy)return;saveDraft();current={id:crypto.randomUUID(),title:'New conversation',provider:$('#provider').value,model:$('#model').value,messages:[]};render();$('#prompt').value='';$('#prompt').focus();document.body.classList.remove('show-sidebar')}
function render(){document.body.classList.toggle('has-conversation',!!current?.messages.length);$('#session-count').textContent=sessions.filter(s=>!!s.archived===showArchived).length;const nav=$('#sessions');nav.replaceChildren();for(const s of sessions.filter(s=>!!s.archived===showArchived&&s.title.toLowerCase().includes($('#history-search').value.toLowerCase()))){const b=document.createElement('button');b.textContent=s.title;b.className=s.id===current?.id?'active':'';b.onclick=async()=>{if(busy)return;saveDraft();current=s;restoreDraft();$('#provider').value=s.provider;await loadModels(s.model);render();document.body.classList.remove('show-sidebar')};nav.append(b)}$('#title').textContent=current?.title||'New conversation';$('#archive').textContent=current?.archived?'Restore':'Archive';$('#welcome').hidden=!!current?.messages.length;const messages=$('#messages');messages.replaceChildren();for(const m of current?.messages||[]){const item=document.createElement('article');item.className='message '+m.role;const role=document.createElement('div');role.className='role';role.textContent=m.role==='user'?'You':current?.taskId?'Orchestrator':m.route||'codelaboon';item.append(role);const content=document.createElement('div');content.className='content';const parts=m.content.split(/```[^\n]*\n([\s\S]*?)```/g);parts.forEach((part,i)=>{const el=document.createElement(i%2?'pre':'span');el.textContent=part;content.append(el)});item.append(content);const copy=document.createElement('button');copy.className='copy';copy.textContent='Copy';copy.onclick=async()=>{try{await navigator.clipboard.writeText(m.content);copy.textContent='Copied'}catch{showError('Clipboard unavailable. Select and copy the message.')}};item.append(copy);messages.append(item)}}
function fillProviders(selected){
 const picker=$('#provider');
 picker.replaceChildren(...providers.map(p=>new Option((p.label||p.name)+(p.keyless?' · keyless':p.configured?'':p.name==='claude_browser'?' · setup required':' · needs key'),p.name)));
 if(providers.some(p=>p.name===selected))picker.value=selected;
}
async function loadModels(preferred){const version=++discovery;const provider=$('#provider').value;$('#qoder-alert').hidden=provider!=='qoder';$('#claude-browser-link').hidden=provider!=='claude_browser';$('#model').replaceChildren(new Option('Loading models…',''));$('#send').disabled=true;showError('');try{const data=await api('/api/models?provider='+encodeURIComponent(provider));if(version!==discovery)return;$('#model').replaceChildren(...data.models.map(m=>new Option(data.names?.[m]||m,m)));if(!data.models.length)$('#model').append(new Option('No models available',''));if(data.models.includes(preferred))$('#model').value=preferred;const p=providers.find(p=>p.name===provider);$('#connection').textContent=provider==='free'?'Routes across available free models':provider==='claude_browser'?(data.models.length?'Firefox add-on required':'Setup required'):p?.keyless?'No key required':p?.configured?'Provider configured':'API key needed';if(!data.models.length&&provider!=='claude_browser')showError('No models found. Configure this provider or refresh the catalogue.')}catch(e){if(version===discovery)showError(e.message)}finally{if(version===discovery)$('#send').disabled=busy||!$('#model').value}}
$('#provider').onchange=()=>{if(current?.messages.length)newChat();loadModels()};$('#refresh').onclick=()=>loadModels($('#model').value);$('#new').onclick=newChat;$('#menu').onclick=()=>{document.body.classList.toggle(innerWidth<=800?'show-sidebar':'hide-sidebar')};$('#theme').onclick=()=>{document.body.classList.toggle('light');localStorage.setItem('codelaboon.theme',document.body.classList.contains('light')?'light':'dark')};try{if(localStorage.getItem('codelaboon.theme')==='light')document.body.classList.add('light')}catch{}
for(const b of document.querySelectorAll('[data-prompt]'))b.onclick=()=>{$('#prompt').value=b.dataset.prompt;$('#prompt').focus()};
$('#prompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('#composer').requestSubmit()}};document.addEventListener('keydown',e=>{if(e.altKey&&e.key.toLowerCase()==='n'){e.preventDefault();newChat()}});
$('#composer').onsubmit=async e=>{e.preventDefault();const text=$('#prompt').value.trim();if(busy||!text||!$('#model').value)return;if(!current)newChat();const chat=current;chat.provider=$('#provider').value;chat.model=$('#model').value;const messages=[...chat.messages,{role:'user',content:text}];busy=true;$('#send').disabled=true;$('#provider').disabled=true;$('#model').disabled=true;$('#refresh').disabled=true;$('#compose-label').textContent='Waiting for '+(providers.find(p=>p.name===chat.provider)?.label||chat.provider)+'…';showError('');try{chat.messages=messages;render();$('#thread').scrollTop=$('#thread').scrollHeight;controller=new AbortController();$('#stop').hidden=false;const data=await api('/api/chat',{signal:controller.signal,method:'POST',headers:{'Content-Type':'application/json','X-Codelaboon-Token':token},body:JSON.stringify({provider:chat.provider,model:chat.model,messages})});chat.messages.push({role:'assistant',content:data.reply,route:data.route});if(!sessions.includes(chat)){chat.title=text.slice(0,45);sessions.unshift(chat)}persist();$('#prompt').value='';saveDraft();render();$('#thread').scrollTop=$('#thread').scrollHeight}catch(err){chat.messages=messages.slice(0,-1);render();showError(err.name==='AbortError'?chat.provider==='claude_browser'?'Stopped waiting. Claude.ai may still finish in Firefox.':chat.provider==='free'?'Stopped waiting. The selected provider may still finish.':'Stopped waiting. The provider may still finish and bill the request.':err.message)}finally{$('#stop').hidden=true;controller=null;busy=false;$('#send').disabled=!$('#model').value;$('#provider').disabled=false;$('#model').disabled=false;$('#refresh').disabled=false;$('#compose-label').textContent='Conversation stays in this browser';$('#prompt').focus()}};
$('#export').onclick=()=>{if(!current?.messages.length){showError('Start a conversation before exporting.');return}const blob=new Blob([JSON.stringify(current,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='codelaboon-chat.json';a.click();URL.revokeObjectURL(url)};
(async()=>{try{const data=await api('/api/providers');token=data.token;providers=data.providers;fillProviders();const ready=providers.find(p=>p.configured&&p.name!=='free');if(ready)$('#provider').value=ready.name;newChat();try{const draft=JSON.parse(localStorage.getItem('codelaboon.activeDraft')||'null');if(draft?.chat&&providers.some(p=>p.name===draft.chat.provider)&&Array.isArray(draft.chat.messages)&&typeof draft.text==='string'){current=sessions.find(s=>s.id===draft.chat.id)||draft.chat;$('#provider').value=current.provider;$('#prompt').value=draft.text;render()}}catch{}if(requestedProvider==='claude_browser'&&providers.some(p=>p.name==='claude_browser')){$('#provider').value='claude_browser';newChat()}await loadModels(current?.model);await refreshTaskChats(true)}catch(e){showError(e.message)}})();

for(const button of document.querySelectorAll('[data-auth]')){const provider=button.dataset.auth,label=button.textContent;button.onclick=async()=>{button.disabled=true;button.textContent='Complete sign-in in your browser?';try{await api('/api/auth/'+provider,{method:'POST',headers:{'X-Codelaboon-Token':token}});const poll=setInterval(async()=>{try{const state=await api('/api/auth/status?provider='+provider);if(state.status==='pending'){if(state.user_code)showError('GitHub: open '+state.verification_uri+' and enter '+state.user_code);return;}clearInterval(poll);button.disabled=false;button.textContent=label;if(state.status==='connected'){const data=await api('/api/providers');providers=data.providers;fillProviders(provider);await loadModels()}else showError(provider+' sign-in did not complete. Retry, or run codelaboon login '+provider+' in a terminal.')}catch(e){clearInterval(poll);button.disabled=false;showError(e.message)}},1500)}catch(e){button.disabled=false;button.textContent=label;showError(e.message)}}}

$('#stop').onclick=()=>controller?.abort();
$('#history-search').oninput=render;
$('#archived').onclick=()=>{showArchived=!showArchived;$('#archived').textContent=showArchived?'Show active':'Show archived';render()};
$('#archive').onclick=()=>{if(busy||!current||!sessions.includes(current))return;current.archived=!current.archived;persist();newChat()};
$('#rename').onclick=()=>{if(busy||!current||!sessions.includes(current))return;const title=prompt('Conversation name',current.title);if(title?.trim()){current.title=title.trim().slice(0,100);persist();render()}};

$('#rail-new').onclick=newChat;
$('#rail-library').onclick=()=>$('#menu').click();
for(const action of document.querySelectorAll('.action-menu button'))action.addEventListener('click',()=>document.querySelector('.actions').open=false);
document.addEventListener('click',event=>{if(!event.target.closest('.actions'))document.querySelector('.actions').open=false});

$('#provider-settings').onclick=()=>{if(providers.some(p=>p.name===$('#provider').value)&&[...$('#key-provider').options].some(o=>o.value===$('#provider').value))$('#key-provider').value=$('#provider').value;$('#provider-key').value='';$('#provider-key-error').textContent='';$('#provider-dialog').showModal()};
$('#close-provider').onclick=()=>{$('#provider-key').value='';$('#provider-dialog').close()};
$('#provider-key-form').onsubmit=async event=>{
 event.preventDefault();$('#save-provider').disabled=true;
 const provider=$('#key-provider').value;
 try{await api('/api/providers/configure',{method:'POST',headers:{'Content-Type':'application/json','X-Codelaboon-Token':token},body:JSON.stringify({provider,api_key:$('#provider-key').value})});$('#provider-key').value='';$('#provider-dialog').close();const data=await api('/api/providers');providers=data.providers;fillProviders(provider);await loadModels()}
 catch(error){$('#provider-key-error').textContent=error.message}finally{$('#save-provider').disabled=false}
};

$('#prompt').addEventListener('keydown',event=>{if(event.key==='ArrowUp'&&!event.shiftKey&&!$('#prompt').value){const previous=[...(current?.messages||[])].reverse().find(row=>row.role==='user');if(previous){event.preventDefault();$('#prompt').value=previous.content;saveDraft()}}});

// Task threads use the same library, renderer and composer as regular chats.
let taskChats=[],taskState=null,taskLoading=false;
const taskPendingMessages=new Map();
const regularRender=render;
render=function(){
 regularRender();
 const active=!!current?.taskId;document.body.classList.toggle('task-chat',active);
 let context=$('#task-context');
 if(!context){context=document.createElement('div');context.id='task-context';context.className='toolbar';context.hidden=true;$('.toolbar').after(context)}
 context.hidden=!active;
 $('#archive').disabled=active;$('#rename').disabled=active;
 if(active){
  $('#send').disabled=busy;$('#compose-label').textContent='Saved to this task \u00b7 Replies arrive automatically';
  context.replaceChildren();const heading=document.createElement('h1');heading.className='task-chat-title';heading.textContent=current.title;context.append(heading);const label=document.createElement('span');label.textContent='Orchestrator \u00b7 '+(taskState?.activity||'Loading')+' \u00b7 Worker '+(taskState?.worker?.paused?'paused':taskState?.worker?.running?'running':'stopped');context.append(label);
  const controls=[...(!taskState?.worker?.running?[['Start worker','start',true]]:[]),...(taskState?.worker?.paused?[['Resume worker','resume',true]]:[]),...(taskState?.activity==='paused'?[['Resume task','resume',false]]:!['completed','stopped'].includes(taskState?.activity)?[['Pause task','pause',false]]:[])];
  for(const [label,action,worker] of controls){
   const b=document.createElement('button');b.textContent=label;b.disabled=worker&&action==='start'&&!!taskState?.worker?.running;b.onclick=async()=>{try{await taskRequest(worker?'/api/tasks/worker':'/api/tasks/control',worker?{action}:{task:current.taskId,action});await refreshTaskChats()}catch(e){showError(e.message)}};context.append(b)
  }
  const open=document.createElement('button');open.textContent='Open in engine';open.id='open-native-task';open.onclick=()=>TaskActions.open(current.taskId,taskState?.task?.engine);context.append(open);
  const remove=document.createElement('button');remove.textContent='Delete task';remove.id='delete-chat-task';remove.onclick=()=>TaskActions.remove(current.taskId);context.append(remove);
  const link=document.createElement('a');link.href='/tasks?task='+encodeURIComponent(current.taskId);link.textContent='Task controls';context.append(link);
 }
 if(!showArchived)for(const task of taskChats.filter(t=>t.title.toLowerCase().includes($('#history-search').value.toLowerCase()))){
  const button=document.createElement('button');button.textContent=task.title;button.title='Task conversation \u00b7 '+task.state;button.className=task.id===current?.taskId?'active':'';button.dataset.task=task.id;button.onclick=()=>openTaskChat(task.id).catch(e=>showError(e.message));$('#sessions').append(button)
 }
 $('#session-count').textContent=sessions.filter(s=>!!s.archived===showArchived).length+(showArchived?0:taskChats.length);
};
function taskRequest(path,body){return api(path,{method:'POST',headers:{'Content-Type':'application/json','X-Codelaboon-Token':token},body:JSON.stringify(body)})}
async function openTaskChat(identity){
 if(busy)return;saveDraft();
 const value=await api('/api/task-chat?task='+encodeURIComponent(identity),{headers:{'X-Codelaboon-Token':token}});
 taskState=value;current={id:'task:'+identity,taskId:identity,title:value.task.title,messages:value.messages.filter(m=>!m.note)};
 history.replaceState(null,'','/?task='+encodeURIComponent(identity));restoreDraft();render();showError(value.latest_error||'');
 document.body.classList.remove('show-sidebar');$('#thread').scrollTop=$('#thread').scrollHeight;
}
async function refreshTaskChats(initial=false){
 if(!token||taskLoading)return;taskLoading=true;
 try{
  const state=await api('/api/tasks',{headers:{'X-Codelaboon-Token':token}});const listChanged=JSON.stringify(taskChats.map(t=>[t.id,t.title,t.state]))!==JSON.stringify(state.tasks.map(t=>[t.id,t.title,t.state]));taskChats=state.tasks;TaskActions.configure(token,state.engines);
  if(current?.taskId&&!taskChats.some(t=>t.id===current.taskId)){current=null;taskState=null;newChat();showError('This task was deleted.');return}
  const selected=initial?requestedTask:current?.taskId;
  if(selected){
   if(current?.taskId!==selected)await openTaskChat(selected);
   else{const value=await api('/api/task-chat?task='+encodeURIComponent(selected),{headers:{'X-Codelaboon-Token':token}});if(current?.taskId!==selected)return;const thread=$('#thread'),atBottom=thread.scrollHeight-thread.scrollTop-thread.clientHeight<100;
    const changed=JSON.stringify(current.messages)!==JSON.stringify(value.messages.filter(m=>!m.note));const stateChanged=taskState?.activity!==value.activity||taskState?.worker?.running!==value.worker.running||taskState?.worker?.paused!==value.worker.paused;taskState=value;current.messages=value.messages.filter(m=>!m.note);current.title=value.task.title;if(changed||stateChanged||listChanged)render();if(changed&&atBottom)thread.scrollTop=thread.scrollHeight;
    showError(value.latest_error||'')}
  }else if(initial||listChanged)render();
 }catch(e){if(current?.taskId)showError(e.message)}finally{taskLoading=false}
}
$('#composer').addEventListener('submit',async e=>{
 if(!current?.taskId)return;e.preventDefault();e.stopImmediatePropagation();const text=$('#prompt').value.trim();if(busy||!text)return;
 busy=true;$('#send').disabled=true;const identity=current.taskId;
 try{let pending=taskPendingMessages.get(identity);if(!pending||pending.text!==text){pending={task:identity,text,mode:'guidance',message_id:crypto.randomUUID()};taskPendingMessages.set(identity,pending)}const result=await taskRequest('/api/tasks/messages',pending);taskPendingMessages.delete(identity);$('#prompt').value='';saveDraft();await refreshTaskChats();showError(result.execution_error||'')}
 catch(error){showError(error.message)}finally{busy=false;render();$('#prompt').focus()}
},true);
const normalNewChat=newChat;
newChat=function(){if(busy)return;history.replaceState(null,'','/');taskState=null;normalNewChat();$('#compose-label').textContent='Conversation stays in this browser';$('#send').disabled=!$('#model').value};
$('#new').onclick=newChat;
setInterval(()=>refreshTaskChats(),2500);

document.addEventListener('task-deleted',event=>{
 const identity=event.detail.task;try{localStorage.removeItem('codelaboon.draft.task:'+identity);const draft=JSON.parse(localStorage.getItem('codelaboon.activeDraft')||'null');if(draft?.chat?.taskId===identity)localStorage.removeItem('codelaboon.activeDraft')}catch{}
 taskPendingMessages.delete(identity);if(current?.taskId===identity){current=null;taskState=null;newChat()}refreshTaskChats();showError('')
});
document.addEventListener('task-opened',event=>{showError('');const note=document.createElement('p');note.className='task-action-notice';note.setAttribute('role','status');note.textContent=event.detail.message;$('#task-context')?.append(note);setTimeout(()=>note.remove(),6000)});
