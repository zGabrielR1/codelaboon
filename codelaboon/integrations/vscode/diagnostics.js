'use strict';
const {execFile} = require('child_process');
function collect(cli) {
  return new Promise((resolve,reject)=>execFile(cli,['doctor','--json'],{windowsHide:true,timeout:15000,maxBuffer:1024*1024},(error,stdout)=>{
    if(error)return reject(error);try{resolve(JSON.parse(stdout));}catch(e){reject(e);}
  }));
}
function register(vscode,context,cli) {
  const changes=new vscode.EventEmitter();
  const provider={onDidChangeTreeData:changes.event,getTreeItem:item=>item,async getChildren(){
    try {
      const state=await collect(cli);const controller=state.local_controller;
      const evaluation=controller.evaluation;
      return [
        new vscode.TreeItem('Worker: '+(state.worker.running?'running':'stopped')),
        new vscode.TreeItem('Pending tasks: '+(state.worker.pending_count??0)),
        new vscode.TreeItem('Local controller: '+(controller.model_installed&&controller.runtime_installed?'ready · loads on demand':'optional runtime/model missing')),
        new vscode.TreeItem('Controller evaluation: '+(evaluation.total?evaluation.passed+'/'+evaluation.total:'not run')),
        new vscode.TreeItem('Routing: '+state.routing.preset+' · '+state.routing.observations.length+' observed routes'),
        new vscode.TreeItem('Security checks: '+state.security.builtin_checks.join(', ')),
        new vscode.TreeItem('Pending privilege cases: '+state.pending_privilege_cases.length)
      ];
    } catch(error){return [new vscode.TreeItem('Diagnostics unavailable: '+error.message)];}
  }};
  context.subscriptions.push(changes,vscode.window.registerTreeDataProvider('codelaboon.diagnostics',provider),
    vscode.commands.registerCommand('codelaboon.refreshDiagnostics',()=>changes.fire()),
    vscode.commands.registerCommand('codelaboon.evaluateController',()=>{
      const terminal=vscode.window.createTerminal({name:'Codelaboon controller evaluation',shellPath:cli,shellArgs:['controller-eval']});terminal.show();
    }));
}
module.exports={collect,register};
