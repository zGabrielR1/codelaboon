'use strict';
const {spawn}=require('child_process');
const path=require('path');
const engines=['opencode','codex','kilo','claude','omp','jcode','crush'];
function createActions(vscode,run,refresh,output) {
  const folder=()=>vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const agent=()=>vscode.window.showQuickPick(engines,{title:'Choose a session engine'});
  async function source() {
    const engine=await agent();if(!engine)return;
    const mode=await vscode.window.showQuickPick(['Choose session file','Enter native session ID'],{title:'Import from '+engine});
    if(!mode)return;
    if(mode==='Choose session file') {
      const files=await vscode.window.showOpenDialog({canSelectMany:false,filters:{'Session files':['json','jsonl']},title:'Choose '+engine+' session'});
      return files?.[0]?{engine,source:files[0].fsPath}:undefined;
    }
    const id=await vscode.window.showInputBox({title:engine+' session ID',prompt:'Read the session from this agent’s ordinary local profile',ignoreFocusOut:true});
    return id?.trim()?{engine,source:id.trim()}:undefined;
  }
  async function chooseSession(selected) {
    if(selected?.id)return selected;
    const rows=JSON.parse(await run(['sessions','list','--json']));
    if(!rows.length){vscode.window.showInformationMessage('No shared sessions yet. Use Import Session first.');return;}
    return vscode.window.showQuickPick(rows.map(row=>({label:row.title,description:row.cwd,detail:row.id,...row})),{title:'Choose a shared session',matchOnDescription:true});
  }
  async function destination(engine) {
    const extension=['opencode','kilo','jcode','crush'].includes(engine)?'json':'jsonl';
    return vscode.window.showSaveDialog({defaultUri:vscode.Uri.file(path.join(folder()||require('os').homedir(),'session-'+engine+'.'+extension)),filters:{'Native session':[extension]},title:'Export for '+engine});
  }
  async function model(engine) {
    if(!['opencode','kilo'].includes(engine))return [];
    const value=await vscode.window.showInputBox({title:'Destination provider/model',prompt:'Optional: select a model configured in the independent target agent. Leave blank to choose when resuming.'});
    if(value===undefined)return;
    return value.trim()?['--model',value.trim()]:[];
  }
  async function finished(args) {
    const result=await run(args);output.appendLine(result);output.show(true);refresh();
    vscode.window.showInformationMessage('Session export complete. Native resume instructions are in the Codelaboon Sessions output.');
  }
  return {
    async importSession() {
      const from=await source();if(!from)return;
      const id=(await run(['sessions','import','--engine',from.engine,'--source',from.source])).trim();
      refresh();vscode.window.showInformationMessage('Session imported. Shared ID: '+id);
    },
    async exportSession(selected) {
      const session=await chooseSession(selected);if(!session)return;
      const engine=await agent();if(!engine)return;
      const options=await model(engine);if(!options)return;
      const file=await destination(engine);if(!file)return;
      await finished(['sessions','export',session.id,'--engine',engine,'--output',file.fsPath,...options]);
    },
    async convertSession() {
      const from=await source();if(!from)return;
      const engine=await agent();if(!engine)return;
      const options=await model(engine);if(!options)return;
      const file=await destination(engine);if(!file)return;
      await finished(['sessions','convert','--from',from.engine,'--source',from.source,'--to',engine,'--output',file.fsPath,...options]);
    },
    async resumeSession(selected) {
      const session=await chooseSession(selected);if(!session)return;
      const engine=await agent();if(!engine)return;
      return {session,engine};
    }
  };
}
function register(vscode,context,cli) {
  const output=vscode.window.createOutputChannel('Codelaboon Sessions');
  const changed=new vscode.EventEmitter();context.subscriptions.push(output,changed);
  const children=new Set();context.subscriptions.push({dispose:()=>{for(const child of children)child.kill();}});
  function run(args) {
    return new Promise((resolve,reject)=>{
      const child=spawn(cli,args,{cwd:vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,windowsHide:true});
      children.add(child);child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8');
      let stdout='',stderr='';let settled=false;
      const timeout=setTimeout(()=>{child.kill();reject(new Error('Session operation timed out'));},120000);
      child.stdout.on('data',data=>{stdout+=data.toString();if(stdout.length>8*1024*1024)child.kill();});
      child.stderr.on('data',data=>{stderr=(stderr+data.toString()).slice(-16000);});
      child.on('error',error=>{children.delete(child);clearTimeout(timeout);settled=true;reject(error);});
      child.on('close',code=>{children.delete(child);clearTimeout(timeout);if(settled)return;code===0?resolve(stdout):reject(new Error(stderr||'Session operation failed (exit '+code+')'));});
    });
  }
  const provider={onDidChangeTreeData:changed.event,
    async getChildren(){try{return JSON.parse(await run(['sessions','list','--json']));}catch(error){output.appendLine(error.message);return [];}},
    getTreeItem(session){const item=new vscode.TreeItem(session.title);item.id=session.id;item.description=session.cwd;item.tooltip=session.id;item.contextValue='codelaboonSession';item.command={command:'codelaboon.resumeSession',title:'Resume Session',arguments:[session]};return item;}
  };
  context.subscriptions.push(vscode.window.createTreeView('codelaboon.sessions',{treeDataProvider:provider}));
  const refresh=()=>changed.fire();const actions=createActions(vscode,run,refresh,output);
  const handlers={importSession:actions.importSession,exportSession:actions.exportSession,convertSession:actions.convertSession,
    refreshSessions:refresh,resumeSession:async selected=>{const result=await actions.resumeSession(selected);if(!result)return;const terminal=vscode.window.createTerminal({name:'Codelaboon · '+result.engine,shellPath:cli,shellArgs:['sessions','resume',result.session.id,'--engine',result.engine],cwd:result.session.cwd||undefined});terminal.show();}};
  for(const [name,handler] of Object.entries(handlers))context.subscriptions.push(vscode.commands.registerCommand('codelaboon.'+name,async(...args)=>{try{return await handler(...args);}catch(error){output.appendLine(error.message);vscode.window.showErrorMessage(error.message);}}));
}
module.exports={register,createActions,engines};
