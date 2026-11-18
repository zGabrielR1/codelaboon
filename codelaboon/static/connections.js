const $=s=>document.querySelector(s);
let token='',connections=[],selectedKey='',loading=false;
const names={mistral_labs:"Mistral Labs",chatgpt:'ChatGPT',claude:'Claude',gemini:'Google Gemini',freebuff:'Freebuff',qoder:'Qoder',copilot:'GitHub Copilot',vercel:'Vercel AI Gateway',howtofix:'HowToFix',wusrouter:'WusRouter',groq:'Groq',cerebras:'Cerebras',openrouter:'OpenRouter',nvidia:'NVIDIA',luna:'Luna'};
try{if(localStorage.getItem('codelaboon.theme')==='light')document.body.classList.add('light')}catch{}
async function request(path,body){const response=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Codelaboon-Token':token},...(body?{body:JSON.stringify(body)}:{})});const value=await response.json();if(!response.ok)throw Error(value.error||'Connection request failed');return value}
function error(text){$('#connection-error').textContent=text;$('#connection-error').hidden=!text}
const browserSetup=$('#claude-browser-setup');
const browserTest=$('#claude-browser-test');
const browserStatus=$('#claude-browser-status');
let browserEnabled=false,browserWorking=false;
function renderBrowser(state){
 $('#claude-browser').hidden=!state;
 browserEnabled=!!state?.enabled;
 browserSetup.disabled=browserWorking;
 browserTest.disabled=browserWorking||!browserEnabled;
 if(!browserWorking&&!browserStatus.textContent){
  browserStatus.textContent=browserEnabled?'Enabled locally. Test the Firefox connection before chatting.':'Enable the provider to get the add-on path.';
 }
}
async function browserAction(action){
 browserWorking=true;browserSetup.disabled=true;browserTest.disabled=true;
 browserStatus.textContent=action==='test'?'Waiting for Firefox and Claude.ai…':'Preparing the local add-on…';
 try{
  const value=await request('/api/claude-browser/'+action,{});
  if(action==='setup'){
   browserEnabled=true;
   $('#claude-browser-manifest').value=value.manifest;
   $('#claude-browser-steps').hidden=false;
   browserStatus.textContent='Provider enabled. Load the add-on in Firefox, then test the connection.';
  }else{
   browserStatus.textContent='Connection verified. Claude.ai returned a reply.';
   $('#claude-browser-chat').hidden=false;
  }
 }catch(e){browserStatus.textContent=e.message}
 finally{browserWorking=false;browserSetup.disabled=false;browserTest.disabled=!browserEnabled}
}
browserSetup.onclick=()=>browserAction('setup');
browserTest.onclick=()=>browserAction('test');
$('#claude-browser-copy').onclick=async()=>{
 const path=$('#claude-browser-manifest');
 try{await navigator.clipboard.writeText(path.value);browserStatus.textContent='Manifest path copied.'}
 catch{path.focus();path.select();browserStatus.textContent='Manifest path selected. Use your copy shortcut.'}
};
function render(){
 for(const [kind,target] of [['account','#account-connections'],['key','#key-connections']]){
  const list=$(target);list.replaceChildren();
  for(const connection of connections.filter(c=>c.kind===kind)){
   const row=document.createElement('div');row.className='connection-row';row.dataset.provider=connection.id;
   const name=document.createElement('span');name.className='connection-name';name.textContent=names[connection.id]||connection.id;
   const status=document.createElement('span');const pending=connection.login?.status==='pending';status.className='connection-status'+(connection.configured?' connected':'');
   status.textContent=pending?'Waiting for browser authorization':connection.login?.status==='failed'?'Sign-in needs another try':connection.configured?'Connected on this computer':'Not connected';
   const button=document.createElement('button');button.textContent=kind==='key'?(connection.configured?'Replace key':'Add key'):(connection.configured?'Sign in again':'Sign in');button.disabled=pending;
   button.onclick=async()=>{if(kind==='key'){selectedKey=connection.id;$('#connection-key-title').textContent='Connect '+name.textContent;$('#connection-key').value='';$('#connection-key-error').textContent='';$('#connection-key-dialog').showModal();$('#connection-key').focus();return}
    button.disabled=true;error('');try{await request('/api/auth/'+connection.id,{});await refresh()}catch(e){error(e.message);button.disabled=false}};
   row.append(name,status,button);
   if(pending||connection.login?.status==='failed'){
    const detail=document.createElement('div');detail.className='connection-detail';
    const link=connection.login?.verification_uri;if(link&&/^https?:\/\//.test(link)){const a=document.createElement('a');a.href=link;a.target='_blank';a.rel='noopener noreferrer';a.textContent='Open sign-in page';detail.append(a)}
    if(connection.login?.user_code){const code=document.createElement('strong');code.className='connection-code';code.textContent=connection.login.user_code;detail.append(code)}
    const message=document.createElement('div');message.textContent=connection.login?.message||'Complete sign-in in the provider page. This page updates automatically.';detail.append(message);row.append(detail)
   }
   list.append(row)
  }
 }
}
async function refresh(){if(loading||!token)return;loading=true;try{const value=await request('/api/connections');error('');renderBrowser(value.claude_browser);const next=JSON.stringify(value.connections);if(next!==JSON.stringify(connections)){connections=value.connections;render()}}catch(e){error(e.message)}finally{loading=false}}
$('#refresh-connections').onclick=refresh;
$('#cancel-connection-key').onclick=()=>{$('#connection-key-dialog').close();$('#connection-key').value=''};
$('#connection-key-dialog').addEventListener('close',()=>{$('#connection-key').value=''});
$('#connection-key-form').onsubmit=async event=>{event.preventDefault();$('#save-connection-key').disabled=true;try{await request('/api/providers/configure',{provider:selectedKey,api_key:$('#connection-key').value});$('#connection-key').value='';$('#connection-key-dialog').close();await refresh()}catch(e){$('#connection-key-error').textContent=e.message}finally{$('#save-connection-key').disabled=false}};
(async()=>{try{token=(await request('/api/session')).token;await refresh()}catch(e){error(e.message)}})();
setInterval(()=>{if(!document.hidden&&connections.some(c=>c.login?.status==='pending'))refresh()},1500);

window.addEventListener('focus',refresh);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});
