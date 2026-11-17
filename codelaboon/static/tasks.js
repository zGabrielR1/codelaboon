'use strict';
const $=selector=>document.querySelector(selector);
const drafts=new Map();
let logAttempt='',conversationVersion=0;
try{for(const [key,value] of Object.entries(JSON.parse(sessionStorage.getItem('codelaboon.taskDrafts')||'{}')))if(typeof value==='string')drafts.set(key,value)}catch{}
function saveDrafts(){try{sessionStorage.setItem('codelaboon.taskDrafts',JSON.stringify(Object.fromEntries(drafts)))}catch{}}
const pendingMessages=new Map();const lastSentMessages=new Map();
let token='',state=null,selectedId=new URL(location.href).searchParams.get('task')||'',refreshing=false,autoScroll=true,logController=null,reviewed=null;
try{if(localStorage.getItem('codelaboon.theme')==='light')document.body.classList.add('light')}catch{}
$('#ops-theme').onclick=()=>{document.body.classList.toggle('light');try{localStorage.setItem('codelaboon.theme',document.body.classList.contains('light')?'light':'dark')}catch{}};
async function api(path,options={}){
  const response=await fetch(path,{...options,headers:{'X-Codelaboon-Token':token,...options.headers}});
  const value=await response.json();if(!response.ok)throw Error(value.error||'Task operation failed');return value;
}
function notice(message){$('#ops-error span').textContent=message;$('#ops-error').hidden=!message}
function taskState(task){return task.state||'queued'}
function attention(task){return /failed|retry|interrupted/.test(taskState(task))}
function pill(element,task){element.textContent=taskState(task);element.className='state-pill'+(attention(task)?' attention':taskState(task)==='active attempt'?' running':'')}
function engineCompatibility(){return !!state?.worker.running&&!state.worker.service?.features?.includes('task-engine-selection')}
function renderList(){
  const query=$('#task-filter').value.toLowerCase();
  const filter=$('#task-state-filter').value;
  const tasks=(state?.tasks||[]).filter(task=>filter==='all'||(filter==='attention'?attention(task):filter==='active'?taskState(task)==='active attempt':filter==='finished'?['completed','stopped'].includes(taskState(task)):taskState(task)==='paused')).filter(task=>[task.id,task.title,task.project,task.engine].some(value=>String(value).toLowerCase().includes(query)));
  $('#task-total').textContent=String(tasks.length);
  const list=$('#task-list');const ids=tasks.map(task=>task.id).join('|');
  if(list.dataset.ids!==ids){
    list.replaceChildren();list.dataset.ids=ids;
    for(const task of tasks){
      const button=document.createElement('a');button.className='task-row';button.dataset.id=task.id;
      button.href='/tasks?task='+encodeURIComponent(task.id);
      button.innerHTML='<span class="task-name"></span><span class="task-subline"><span class="state-pill"></span><span class="task-cycle-count"></span></span><span class="task-row-meta"></span>';
      button.onclick=event=>{if(event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;event.preventDefault();selectTask(task.id)};list.append(button);
    }
    if(!tasks.length){const empty=document.createElement('div');empty.className='ops-empty';empty.textContent=query?'No matching tasks.':'No tasks queued. Queue one fixed objective with an independent verification command.';list.append(empty)}
  }
  for(const task of tasks){
    const button=[...list.querySelectorAll('.task-row')].find(row=>row.dataset.id===task.id);
    button.classList.toggle('selected',task.id===selectedId);if(task.id===selectedId)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
    button.querySelector('.task-name').textContent=task.title;
    pill(button.querySelector('.state-pill'),task);
    button.querySelector('.task-cycle-count').textContent=(task.cycles_completed||0)+' verified';
    button.querySelector('.task-row-meta').textContent=task.engine+' · '+task.project.split(/[\\/]/).filter(Boolean).pop();
  }
}
function selected(){return state?.tasks.find(task=>task.id===selectedId)}
async function selectTask(identity,push=true){
  if(selectedId!==identity)logAttempt='';selectedId=identity;logController?.abort();
  if(push){const url=new URL(location.href);if(identity)url.searchParams.set('task',identity);else url.searchParams.delete('task');history.pushState({},'',url)}
  renderList();renderDetail();await loadLogs();await loadConversation();
  if(identity)$('#detail-title')?.focus({preventScroll:true});
}
window.addEventListener('popstate',()=>selectTask(new URL(location.href).searchParams.get('task')||'',false));
function renderDetail(){
  const task=selected();const detail=$('#task-detail');
  document.body.classList.toggle('task-open',!!task);
  const overviewHeading=$('.ops-header h1');
  if(task)overviewHeading?.remove();
  else if(!overviewHeading){const heading=document.createElement('h1');heading.textContent='Continuous work';$('.ops-brand').after(heading)}
  if(!task){detail.dataset.task='';detail.innerHTML='<div class="ops-empty"><h2></h2><p></p></div>';detail.querySelector('h2').textContent=selectedId?'Task unavailable':'Open a task conversation';detail.querySelector('p').textContent=selectedId?'This task ID was not found in this worker configuration. Choose another task or refresh.':'Select a task to watch its orchestrator, read live output and send guidance.';return}
  if(detail.dataset.task!==task.id){
    detail.dataset.task=task.id;
    detail.innerHTML='<div class="chat-navigation"><button id="back-tasks">Back to tasks</button><div class="chat-tools"><button id="open-attempts">Attempts</button><button id="open-task-settings">Models &amp; prompts</button><button id="open-task-changes">Changes</button><span id="chat-live">Live task conversation</span></div></div><div class="detail-top"><h1 id="detail-title" tabindex="-1"></h1><span id="detail-state" class="state-pill"></span></div><div class="task-id-row"><code id="detail-id"></code><button id="copy-task-id">Copy ID</button></div><details class="task-information"><summary>Task details, scope and checks</summary><p id="detail-project" class="detail-project"></p><dl class="cycle-strip"><div><dt>Verified cycles</dt><dd id="detail-cycles" class="cycle-number">0</dd></div><div><dt>Engine</dt><dd id="detail-engine"></dd></div><div><dt>Latest attempt</dt><dd id="detail-attempt"></dd></div></dl><details><summary>Objective and authorized scope</summary><dl class="policy-values"><dt>Objective</dt><dd id="detail-objective"></dd><dt>Scope</dt><dd id="detail-scope"></dd></dl></details><details><summary>Permissions and verification</summary><dl class="policy-values"><dt>Profile</dt><dd id="detail-profile"></dd><dt>Permissions</dt><dd id="detail-permissions"></dd><dt>Elevation</dt><dd id="detail-elevation"></dd><dt>Scope reviewer</dt><dd id="detail-reviewer"></dd><dt>Cycle policy</dt><dd id="detail-budget"></dd></dl><pre id="detail-checks"></pre><div id="detail-privilege" hidden><p class="field-note">This task needs a reviewed native privilege case. The browser does not approve or run elevation.</p><pre id="privilege-command"></pre></div></details></details><div class="task-controls"><button id="task-retry">Retry failed</button><button id="task-pause">Pause</button><button id="task-resume">Resume</button><button id="task-stop" class="stop-control">Stop task</button></div><p id="task-control-note" class="task-controls-note"></p><section class="task-conversation" aria-label="Task conversation"><div id="conversation-feed" role="log" aria-label="Task messages" aria-live="polite"></div><form id="message-form"><label for="task-message">Intervene in this task</label><textarea id="task-message" rows="3" maxlength="4096" required placeholder="Guide the next attempt within the authorized scope..."></textarea><div class="composer-actions"><select id="message-mode" aria-label="Message delivery"><option value="guidance">Guide next attempt</option><option value="note">Save note only</option></select><button class="primary" id="send-message">Send</button></div><p id="message-hint" class="field-note"></p><p id="message-error" role="alert"></p></form></section><details><summary>Raw attempt output</summary><div class="log-heading"><h3>Latest attempt output</h3><label><input id="follow-output" type="checkbox"> Follow output</label></div><p id="log-meta" class="log-meta">Waiting for attempt output…</p><pre id="task-log" class="log-output" aria-label="Latest task output">No output yet.</pre></details>';
    $('#open-attempts').onclick=openAttempts;$('#open-task-settings').onclick=openTaskSettings;$('#open-task-changes').onclick=openTaskChanges;
    $('#back-tasks').onclick=()=>selectTask('');
    $('#task-message').value=drafts.get(task.id)||'';$('#task-message').oninput=()=>{drafts.set(task.id,$('#task-message').value);saveDrafts()};$('#task-message').onkeydown=event=>{if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)&&!event.isComposing){event.preventDefault();$('#message-form').requestSubmit()}if(event.key==='ArrowUp'&&!event.shiftKey&&!$('#task-message').value){const last=lastSentMessages.get(task.id);if(last){event.preventDefault();$('#task-message').value=last;drafts.set(task.id,last);saveDrafts()}}};$('#message-form').onsubmit=sendMessage;
    $('#follow-output').checked=autoScroll;$('#follow-output').onchange=()=>autoScroll=$('#follow-output').checked;
    $('#copy-task-id').onclick=async()=>{try{await navigator.clipboard.writeText(selectedId);$('#copy-task-id').textContent='Copied'}catch{notice('Clipboard unavailable. Select and copy the task ID.')}};
    for(const action of ['pause','resume','stop','retry'])$('#task-'+action).onclick=()=>controlTask(action);
  }
  const compatible=!state.worker.running||state.worker.service?.features?.includes('operator-interventions');
  const canGuide=compatible&&task.elevation==='none'&&!['completed','stopped'].includes(taskState(task));
  $('#message-mode option[value=guidance]').disabled=!canGuide;if(!canGuide)$('#message-mode').value='note';
  $('#message-hint').textContent=canGuide?'Guidance joins the next attempt. Active work continues. Pause to hold later attempts; scope and verification stay fixed.':task.elevation!=='none'?'Notes only: elevated execution is an immutable reviewed case.':'Notes only until the worker is restarted at a safe checkpoint, or for finished tasks.';
  $('#chat-live').textContent=taskState(task)==='active attempt'?'Orchestrator running - live output':taskState(task);$('#detail-title').textContent=task.title;$('#detail-id').textContent=task.id;$('#detail-project').textContent=task.project;
  pill($('#detail-state'),task);$('#detail-cycles').textContent=String(task.cycles_completed||0);
  $('#detail-engine').textContent=task.engine+(task.swarm?.workers>1?' · limit '+task.swarm.workers:'');
  $('#detail-attempt').textContent=task.last_attempt?task.last_attempt.status+(task.last_attempt.exit_code!==undefined?' · exit '+task.last_attempt.exit_code:''):'Not started';
  const finished=['stopped','completed'].includes(taskState(task));
  $('#task-retry').textContent=task.retry_pending?'Retry queued':'Retry failed';
  $('#task-retry').disabled=task.retry_pending||!task.swarm||task.elevation!=='none'||!attention(task)||taskState(task)==='interrupted attempt'||(state.worker.running&&!state.worker.service?.features?.includes('task-retry'));
  $('#task-pause').disabled=finished||taskState(task)==='paused';$('#task-resume').disabled=finished||taskState(task)!=='paused';$('#task-stop').disabled=finished;
  $('#task-control-note').textContent=task.cooldown_seconds?'Retry cooldown: '+task.cooldown_seconds+' seconds. Inspect the output before retrying.':task.elevation!=='none'?'Waiting for native approval. Each elevated case authorizes one verified cycle.':'Pause and stop allow active cycles and checks to finish first.';
  $('#detail-objective').textContent=task.objective;$('#detail-scope').textContent=task.scope||'No explicit scope recorded';
  $('#detail-profile').textContent=task.profile;$('#detail-permissions').textContent=task.permissions+' native tool permissions';$('#detail-elevation').textContent=task.elevation==='none'?'No separate OS elevation requested':task.elevation+' · separate native approval required';
  $('#detail-reviewer').textContent=task.supervision?.enabled?'Configured local reviewer':'Not enabled';
  $('#detail-budget').textContent=task.swarm?task.swarm.timeout+'s timeout · '+task.swarm.interval+'s interval · '+(task.swarm.cycles||'unlimited')+' verified cycles':'One queued task';
  $('#detail-checks').textContent=JSON.stringify(task.verification,null,2);
  $('#detail-privilege').hidden=task.elevation==='none';$('#privilege-command').textContent='codelaboon privilege worker-case '+task.id+'\n# Review the printed case, then approve it in your terminal.';
}
async function loadLogs(){
  const identity=selectedId;if(!identity||!selected())return;
  logController?.abort();logController=new AbortController();
  try{
    const data=await api('/api/tasks/logs?task='+encodeURIComponent(identity)+(logAttempt?'&attempt='+encodeURIComponent(logAttempt):''),{signal:logController.signal});
    if(identity!==selectedId||!$('#task-log'))return;
    const log=$('#task-log');const previous=log.scrollTop;
    const text=data.text||'No output yet. Waiting for the next attempt.';
    if(log.textContent!==text){log.textContent=text;log.scrollTop=autoScroll?log.scrollHeight:previous}
    $('#log-meta').textContent=data.attempt?'Attempt '+data.attempt+(data.truncated?' · last 16 KiB':''):'No attempts recorded';
  }catch(error){if(error.name!=='AbortError'&&identity===selectedId&&$('#log-meta'))$('#log-meta').textContent='Could not refresh output. '+error.message}
}
async function refresh(){
  if(refreshing)return;refreshing=true;$('#ops-refresh').disabled=true;
  try{
    state=await api('/api/tasks');
    // Preserve the requested task route, including a useful unavailable-task state.
    const count=state.tasks.length;const needs=state.tasks.filter(attention).length;
    $('#worker-summary').textContent=(state.worker.paused?'Worker paused':state.worker.running?'Worker online':'Worker stopped')+' · '+count+' task'+(count===1?'':'s')+(needs?' · '+needs+' need'+(needs===1?'s':'')+' attention':'');
    $('#worker-action').disabled=!state.configured;$('#worker-action').textContent=!state.worker.running?'Start worker':state.worker.paused?'Resume worker':'Pause scheduling';
    $('#ops-version').textContent='Core '+state.version;
    $('#worker-compatibility').hidden=!engineCompatibility();
    $('#worker-compatibility').textContent='This running worker predates engine selection. Existing work is unchanged. Restart the worker when its current work can finish before queueing another engine.';
    $('#ops-updated').textContent='Updated '+new Date().toLocaleTimeString();notice('');renderList();renderDetail();await loadLogs();await loadConversation();
  }catch(error){notice('Could not refresh task state. '+error.message+' The last displayed state may be stale.')}
  finally{refreshing=false;$('#ops-refresh').disabled=false}
}
async function controlTask(action){
  const task=selected();if(!task)return;
  if(action==='stop'&&!confirm('Stop '+task.id+'? Active work may finish first. A stopped swarm needs a newly queued task to restart.'))return;
  for(const button of document.querySelectorAll('.task-controls button'))button.disabled=true;
  try{const receipt=await api('/api/tasks/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task:task.id,action})});await refresh();notice(receipt.message)}
  catch(error){notice(error.message);renderDetail()}
}
function setEngine(){
  const engine=state?.engines.find(row=>row.id===$('#task-engine').value);
  if(engine?.native_account)$('#task-model').value='devin/account-default';else if($('#task-model').value.startsWith('devin/'))$('#task-model').value='free';
  $('#task-workers').max=engine?.worker_limit||1;$('#task-workers').value=engine?.native_swarm?4:1;$('#task-workers').readOnly=!engine?.native_swarm;
  $('#engine-note').textContent=engine?.native_account?'Uses your signed-in Devin/Windsurf account and its quota/pricing. Choose devin/account-default or devin/MODEL. Independent checks still determine success.':engine?.native_swarm?'Jcode provides the native worker pool. The limit is a ceiling, not a count of active agents.':'This engine runs one portable coordinator per cycle. It uses the same policy, independent checks, task controls and monitoring.';
}
$('#new-task').onclick=()=>{
  if(!state){notice('Wait for task state to load, then retry.');return}
  $('#task-engine').replaceChildren(...state.engines.map(engine=>{const blocked=engineCompatibility()&&engine.id!=='jcode';const option=new Option(engine.id+(!engine.installed?' · not installed':blocked?' · worker restart needed':''),engine.id);option.disabled=!engine.installed||blocked;return option}));
  const available=state.engines.find(engine=>engine.installed&&(!engineCompatibility()||engine.id==='jcode'));
  $('#task-engine').value=available?.id||'';$('#review-task').disabled=!available;$('#task-project').value=$('#task-project').value||state.workspace;
  $('#task-fields').hidden=false;$('#task-review').hidden=true;$('#review-task').hidden=false;$('#confirm-task').hidden=true;$('#edit-task').hidden=true;$('#task-form-error').hidden=true;setEngine();$('#task-dialog').showModal();
};
$('#task-engine').onchange=setEngine;$('#close-task').onclick=()=>$('#task-dialog').close();
$('#edit-task').onclick=()=>{$('#task-fields').hidden=false;$('#task-review').hidden=true;$('#review-task').hidden=false;$('#confirm-task').hidden=true;$('#edit-task').hidden=true;reviewed=null};
$('#task-form').onsubmit=event=>{
  event.preventDefault();$('#task-form-error').hidden=true;
  try{
    const checks=JSON.parse($('#task-checks').value);
    if(!Array.isArray(checks)||!checks.length||checks.some(argv=>!Array.isArray(argv)||!argv.length||argv.some(part=>typeof part!=='string'||!part)))throw Error('Use nonempty JSON argument arrays for verification.');
    const full=$('#task-full').checked;const elevation=$('#task-elevation').value;
    if(elevation!=='none'&&!full)throw Error('An elevation request requires explicit full-permission acknowledgement.');
    const allowed=$('#task-paths').value.split('\n').map(line=>line.trim()).filter(Boolean);
    if(allowed.length&&!$('#task-supervise').checked)throw Error('A file allowlist requires the configured local scope reviewer.');
    reviewed={request_id:crypto.randomUUID(),objective:$('#task-objective').value,project:$('#task-project').value,scope:$('#task-scope').value,engine:$('#task-engine').value,model:$('#task-model').value,workers:Number($('#task-workers').value),timeout:Number($('#task-timeout').value),interval:Number($('#task-interval').value),cycles:Number($('#task-cycles').value),checks,profile:$('#task-profile').value,permissions:full?'full':'default',confirm_full:full,elevation,supervise:$('#task-supervise').checked,allowed_paths:allowed};
    if($('#queue-planner-mode').value!=='worker'||$('#queue-planner-model').value!=='free'||$('#queue-worker-system').value||$('#queue-planner-system').value){reviewed.execution_settings={worker_model:reviewed.model,orchestrator_mode:$('#queue-planner-mode').value,orchestrator_model:$('#queue-planner-model').value,worker_system_prompt:$('#queue-worker-system').value,orchestrator_system_prompt:$('#queue-planner-system').value}}
    const values=$('#review-values');values.replaceChildren();
    for(const [label,value] of [['Objective',reviewed.objective],['Project',reviewed.project],['Authorized scope',reviewed.scope],['Execution',reviewed.engine+' · '+reviewed.model+' · '+reviewed.workers+' worker limit'],['Budget',reviewed.timeout+'s per cycle · '+reviewed.interval+'s between cycles · '+(reviewed.cycles||'unlimited')+' verified cycles'],['Planning and prompts',reviewed.execution_settings?JSON.stringify(reviewed.execution_settings,null,2):'Embedded coordinator / native default instructions'],['Policy',reviewed.profile+' · '+reviewed.permissions+' permissions · elevation '+reviewed.elevation],['Verification',JSON.stringify(checks,null,2)]]){const dt=document.createElement('dt');dt.textContent=label;const dd=document.createElement('dd');dd.textContent=value;values.append(dt,dd)}
    $('#task-fields').hidden=true;$('#task-review').hidden=false;$('#review-task').hidden=true;$('#confirm-task').hidden=false;$('#edit-task').hidden=false;$('#confirm-task').textContent=elevation==='none'?'Queue and start worker':'Queue awaiting native approval';
  }catch(error){$('#task-form-error').textContent=error.message;$('#task-form-error').hidden=false}
};
$('#confirm-task').onclick=async()=>{
  if(!reviewed)return;$('#confirm-task').disabled=true;$('#edit-task').disabled=true;$('#task-form-error').hidden=true;
  try{const result=await api('/api/tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(reviewed)});$('#task-dialog').close();reviewed=null;await refresh();await selectTask(result.task);if(!result.worker_started)notice(result.message)}
  catch(error){$('#task-form-error').textContent=error.message;$('#task-form-error').hidden=false}
  finally{$('#confirm-task').disabled=false;$('#edit-task').disabled=false}
};
$('#task-state-filter').onchange=renderList;$('#task-filter').oninput=renderList;$('#ops-refresh').onclick=refresh;$('#ops-retry').onclick=refresh;$('#live-refresh').onchange=()=>{if($('#live-refresh').checked)refresh()};
(async()=>{try{const session=await api('/api/session');token=session.token;$('#ops-version').textContent='Core '+session.version;$('#task-elevation').replaceChildren(new Option('Current OS account','none'),new Option(session.platform==='Windows'?'Administrator case (native approval)':'Root case (native approval)',session.platform==='Windows'?'administrator':'root'));await refresh()}catch(error){notice(error.message)}})();
setInterval(()=>{if($('#live-refresh').checked&&!document.hidden)refresh()},2000);

async function loadConversation(){
  const identity=selectedId;if(!identity)return;const version=++conversationVersion;
  try{
    const data=await api('/api/tasks/messages?task='+encodeURIComponent(identity));
    if(identity!==selectedId||version!==conversationVersion||!$('#conversation-feed'))return;
    if(data.messages.length)lastSentMessages.set(identity,data.messages[data.messages.length-1].text);
    const feed=$('#conversation-feed');const nearBottom=feed.scrollHeight-feed.scrollTop-feed.clientHeight<64;const previousScroll=feed.scrollTop;const first=!feed.dataset.signature;const output=$('#task-log')?.textContent||'';const signature=JSON.stringify(data)+output;
    if(feed.dataset.signature===signature)return;
    const task=selected();const rows=[{created:0,role:'You / objective',text:task.objective},
      ...data.events.map(row=>({...row,role:'Orchestrator / execution update'})),
      ...data.messages.map(row=>({...row,role:'You',delivery:row.delivery}))].sort((a,b)=>a.created-b.created);
    feed.replaceChildren();
    for(const row of rows){const article=document.createElement('article');article.className='conversation-message '+(row.role==='You'?'from-user':'from-worker');const label=document.createElement('strong');label.textContent=row.role;const stamp=document.createElement('time');if(row.created){stamp.dateTime=new Date(row.created*1000).toISOString();stamp.textContent=new Date(row.created*1000).toLocaleString();article.append(stamp)}const text=document.createElement('p');text.textContent=row.text;article.append(label,text);if(row.delivery){const receipt=document.createElement('small');receipt.textContent=row.delivery;article.append(receipt)}feed.append(article)}
    if(output&&!output.startsWith('No output yet.')){const article=document.createElement('article');article.className='conversation-message';const label=document.createElement('strong');label.textContent=logAttempt?'Worker / attempt '+logAttempt:'Worker / latest captured output';const text=document.createElement('pre');text.className='conversation-output';text.textContent=output;article.append(label,text);feed.append(article)}
    feed.dataset.signature=signature;feed.scrollTop=autoScroll&&(nearBottom||first)?feed.scrollHeight:previousScroll;
  }catch(error){if(identity===selectedId&&$('#message-error'))$('#message-error').textContent='Conversation unavailable: '+error.message}
}
async function sendMessage(event){
  event.preventDefault();const identity=selectedId;const text=$('#task-message').value;const button=$('#send-message');button.disabled=true;$('#message-error').textContent='';
  const mode=$('#message-mode').value;let message=pendingMessages.get(identity);
  if(!message||message.text!==text||message.mode!==mode){message={task:identity,message_id:crypto.randomUUID(),text,mode};pendingMessages.set(identity,message)}
  try{await api('/api/tasks/messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(message)});lastSentMessages.set(identity,text);pendingMessages.delete(identity);drafts.delete(identity);saveDrafts();if(identity===selectedId)$('#task-message').value='';await loadConversation()}
  catch(error){if(identity===selectedId)$('#message-error').textContent=error.message}
  finally{if(identity===selectedId)button.disabled=false}
}

let editingTask='',editingRevision='';
async function openTaskSettings(){
  const identity=selectedId;if(!identity)return;
  try{
    const row=await api('/api/tasks/settings?task='+encodeURIComponent(identity));
    const choices=await api('/api/tasks/models');
    editingTask=identity;editingRevision=row.revision;
    $('#settings-task-id').textContent=identity;
    for(const [key,id] of Object.entries({worker_model:'settings-worker',orchestrator_mode:'settings-mode',orchestrator_model:'settings-planner',worker_system_prompt:'settings-system',orchestrator_system_prompt:'settings-planner-system'}))$('#'+id).value=row.values[key];
    $('#task-model-choices').replaceChildren(...choices.models.map(model=>new Option(model.id,model.id)));
    $('#settings-receipt').textContent='Desired revision: '+row.revision+' / Latest attempt revision: '+(row.latest_attempt?.settings?.revision||'original defaults');
    $('#settings-status').textContent=row.reason||'Save for the next attempt. Active work keeps its captured configuration. Scope, permissions and checks stay fixed.';
    $('#settings-save').disabled=!row.editable;$('#settings-error').textContent='';$('#task-settings-dialog').showModal();
  }catch(error){notice(error.message)}
}
$('#close-settings').onclick=()=>$('#task-settings-dialog').close();
$('#task-settings-form').onsubmit=async event=>{
  event.preventDefault();$('#settings-save').disabled=true;
  const values={worker_model:$('#settings-worker').value,orchestrator_mode:$('#settings-mode').value,orchestrator_model:$('#settings-planner').value,worker_system_prompt:$('#settings-system').value,orchestrator_system_prompt:$('#settings-planner-system').value};
  try{await api('/api/tasks/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task:editingTask,expected_revision:editingRevision,values})});$('#task-settings-dialog').close();await refresh()}
  catch(error){$('#settings-error').textContent=error.message;$('#settings-save').disabled=false}
};
async function openTaskChanges(){
  const identity=selectedId;if(!identity)return;
  $('#task-changes-dialog').showModal();$('#changes-content').textContent='Reading project Git state...';
  try{
    const row=await api('/api/tasks/changes?task='+encodeURIComponent(identity));
    $('#changes-content').textContent=row.notice+'\n\n'+(row.available?'Git HEAD: '+row.head:'Git metadata unavailable. Initialize a Git repository to inspect changes.')+'\n\n'+row.status+'\n'+row.stat+'\n'+row.diff+(row.truncated?'\n[Output truncated]':'')+'\n\nLatest attempt observation:\n'+JSON.stringify(row.attempt_observation,null,2);
  }catch(error){$('#changes-content').textContent=error.message}
}
$('#close-changes').onclick=()=>$('#task-changes-dialog').close();

async function openAttempts(){
 const identity=selectedId;$('#attempt-dialog').showModal();const list=$('#attempt-list');list.textContent='Loading attempts…';
 try{const data=await api('/api/tasks/attempts?task='+encodeURIComponent(identity));list.replaceChildren();
 const latest=document.createElement('button');latest.textContent='Follow latest attempt';latest.onclick=()=>{if(selectedId!==identity)return;logAttempt='';$('#attempt-dialog').close();loadLogs()};list.append(latest);
 for(const row of data.attempts){const button=document.createElement('button');button.textContent=new Date((row.started||0)*1000).toLocaleString()+' · '+(row.engine||row.harness||'worker')+' · '+row.stage+' · '+row.status+(row.exit_code!==undefined?' · exit '+row.exit_code:'');button.title=row.id;button.onclick=()=>{if(selectedId!==identity)return;logAttempt=row.id;$('#attempt-dialog').close();loadLogs()};list.append(button)}
 if(!data.attempts.length){const empty=document.createElement('p');empty.textContent='No attempts yet.';list.append(empty)}
 }catch(error){list.textContent=error.message}
}
$('#close-attempts').onclick=()=>$('#attempt-dialog').close();

$('#worker-action').onclick=async()=>{
 if(!state)return;const action=!state.worker.running?'start':state.worker.paused?'resume':'pause';
 if(action!=='pause'&&!confirm('Start or resume the background worker? All ready queued tasks may run under their existing permissions.'))return;
 $('#worker-action').disabled=true;
 try{const result=await api('/api/tasks/worker',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});await refresh();notice(result.message)}catch(error){notice(error.message);$('#worker-action').disabled=false}
};
