'use strict';
const assert=require('assert');
const {createActions,engines}=require('../codelaboon/integrations/vscode/session-actions');
const manifest=require('../codelaboon/integrations/vscode/package.json');
const picks=[],inputs=[],calls=[];let refreshes=0;
const vscode={workspace:{workspaceFolders:[{uri:{fsPath:'/project with spaces'}}]},Uri:{file:fsPath=>({fsPath})},window:{
 async showQuickPick(items){const result=picks.shift();assert(result===undefined||items.some(item=>typeof item==='string'?item===result:item.id===result.id));return result;},
 async showInputBox(){return inputs.shift();},async showOpenDialog(){return [{fsPath:'/source with spaces/session.jsonl'}];},
 async showSaveDialog(){return {fsPath:'/output with spaces/session.json'};},showInformationMessage(){}
}};
const run=async args=>{calls.push(args);return args[1]==='list'?JSON.stringify([{id:'universal-id',title:'Work',cwd:'/project'}]):'universal-id';};
const actions=createActions(vscode,run,()=>refreshes++,{appendLine(){},show(){}});
(async()=>{
 assert.strictEqual(engines.length,7);
 for(const engine of engines){
  picks.push(engine,'Choose session file');await actions.importSession();
  assert.deepStrictEqual(calls.at(-1),['sessions','import','--engine',engine,'--source','/source with spaces/session.jsonl']);
  picks.push(engine);if(['opencode','kilo'].includes(engine))inputs.push('provider/model');
  await actions.exportSession({id:'universal-id'});
  assert.deepStrictEqual(calls.at(-1),['sessions','export','universal-id','--engine',engine,'--output','/output with spaces/session.json',...(['opencode','kilo'].includes(engine)?['--model','provider/model']:[])]);
 }
 picks.push('codex','Enter native session ID','opencode');inputs.push('source-id','provider/model');await actions.convertSession();
 assert.deepStrictEqual(calls.at(-1),['sessions','convert','--from','codex','--source','source-id','--to','opencode','--output','/output with spaces/session.json','--model','provider/model']);
 assert(!calls.at(-1).includes('import'),'Standalone conversion must not import into library');
 const count=calls.length;picks.push(undefined);await actions.importSession();assert.strictEqual(calls.length,count);
 picks.push({id:'universal-id',label:'Work'},'codex');const resumed=await actions.resumeSession();assert.strictEqual(resumed.session.id,'universal-id');assert.strictEqual(resumed.engine,'codex');
 assert(manifest.contributes.menus['view/title'].some(item=>item.command==='codelaboon.importSession'));
 assert(manifest.contributes.menus['view/title'].some(item=>item.command==='codelaboon.exportSession'));
 assert(refreshes>=15);
 console.log('PASS session buttons: import/export all seven agents, standalone conversion, cancellation and safe argument paths');
})().catch(error=>{console.error(error);process.exitCode=1;});
