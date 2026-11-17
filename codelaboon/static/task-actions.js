// Shared task actions for the normal chat and the operations view.
(()=>{
 let token='',engines=[];
 const dialog=document.createElement('dialog');dialog.id='task-action-dialog';dialog.innerHTML='<form id="task-action-form"><h2 id="task-action-title"></h2><p id="task-action-description"></p><label id="task-action-engine-label">Engine<select id="task-action-engine"></select></label><p id="task-action-error" role="alert"></p><div class="dialog-actions"><button type="button" id="task-action-cancel">Cancel</button><button type="submit" id="task-action-confirm">Continue</button></div></form>';document.body.append(dialog);
 const $=s=>dialog.querySelector(s);let task='',action='';
 $('#task-action-cancel').onclick=()=>dialog.close();
 async function show(identity,mode,preferred){
  task=identity;action=mode;$('#task-action-error').textContent='';
  const remove=mode==='delete';$('#task-action-title').textContent=remove?'Delete this task?':'Open task in an engine';
  $('#task-action-description').textContent=remove?'Remove this task from your conversations and stop future cycles. Active work and checks finish safely. Project files and local attempt logs are kept.':'Continue this same conversation in a native terminal. Task history and connections are shared.';
  $('#task-action-engine-label').hidden=remove;$('#task-action-confirm').textContent=remove?'Delete task':'Open engine';
  const supported=['opencode','omp','kilo','jcode','codex','claude','crush'];const rows=engines.filter(e=>e.installed&&supported.includes(e.id));
  $('#task-action-engine').replaceChildren(...rows.map(e=>new Option(e.id,e.id)));
  if(rows.some(e=>e.id===preferred))$('#task-action-engine').value=preferred;
  $('#task-action-confirm').disabled=!remove&&!rows.length;
  if(!remove&&!rows.length)$('#task-action-error').textContent='No native engine is installed. Install an engine from the terminal first.';
  dialog.showModal();$('#task-action-cancel').focus()
 }
 $('#task-action-form').onsubmit=async event=>{
  event.preventDefault();const button=$('#task-action-confirm');button.disabled=true;
  try{const response=await fetch(action==='delete'?'/api/tasks/control':'/api/tasks/open',{method:'POST',headers:{'Content-Type':'application/json','X-Codelaboon-Token':token},body:JSON.stringify(action==='delete'?{task,action:'delete'}:{task,engine:$('#task-action-engine').value})});const value=await response.json();if(!response.ok)throw Error(value.error||'Task action failed');dialog.close();document.dispatchEvent(new CustomEvent(action==='delete'?'task-deleted':'task-opened',{detail:value}))}
  catch(e){$('#task-action-error').textContent=e.message}finally{button.disabled=false}
 };
 window.TaskActions={configure(value,rows){token=value;engines=rows||[]},open:(identity,preferred)=>show(identity,'open',preferred),remove:identity=>show(identity,'delete')};
})();
