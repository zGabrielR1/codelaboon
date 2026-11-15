'use strict';
const vscode=require('vscode');const fs=require('fs');const path=require('path');const assert=require('assert');
exports.run=async()=>{
 const project=process.env.CODELABOON_VSCODE_TEST_PROJECT;
 await vscode.extensions.getExtension('codelaboon.codelaboon').activate();
 await vscode.commands.executeCommand('codelaboon.connectCodex');
 assert(vscode.workspace.getConfiguration('chatgpt').get('cliExecutable').includes('wrapper'));
 await vscode.extensions.getExtension('openai.chatgpt').activate();
 await vscode.commands.executeCommand('chatgpt.openSidebar');
 fs.writeFileSync(path.join(project,'ui-ready'),'ready');
 const deadline=Date.now()+65000;
 while(!fs.existsSync(path.join(project,'reply-visible'))&&Date.now()<deadline)await new Promise(r=>setTimeout(r,250));
 assert(fs.existsSync(path.join(project,'reply-visible')),'Codex editor did not render the backend response');
 fs.writeFileSync(path.join(project,'host-test-passed'),'passed');
};
