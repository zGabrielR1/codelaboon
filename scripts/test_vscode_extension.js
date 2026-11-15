'use strict';
// Test real connector code against the public VS Code configuration API contract.
const assert = require('assert');
const Module = require('module');
const original = Module._load;
const values = { claudeProcessWrapper: '/previous/wrapper', disableLoginPrompt: false,
  environmentVariables: [{name:'UNRELATED_SECRET',value:'untouched'}, {name:'ANTHROPIC_MODEL',value:'previous-model'}] };
const api = {
  ConfigurationTarget: { Global: 1 },
  workspace: {getConfiguration(section) { return { get(key) {return values[key];}, inspect(key) {return {globalValue: values[key]};},
    async update(key,value,target) {assert.strictEqual(target,1); values[key]=value;} }; }},
  window: { showInformationMessage() {}, createTerminal(options) { api.lastTerminal=options;return {show() {}}; } }
};
Module._load = function(name,...args) {return name==='vscode' ? api : original.call(this,name,...args);};
const extension = require('../codelaboon/integrations/vscode/extension.js');
Module._load=original;
const store={};
const context={extensionPath:__dirname, globalState:{get:key=>store[key],update:async(key,value)=>{store[key]=value;}}};
const fs = require('fs');
const oldExists=fs.existsSync;
// The configured path exists; no subprocess is started by setting up the connector.
values.wrapperPath='/backend/wrapper';
fs.existsSync=()=>true;
(async()=>{
  await Promise.all([extension.connect(context,true), extension.connect(context,true)]);
  assert.strictEqual(values.claudeProcessWrapper,'/backend/wrapper');
  assert.strictEqual(values.disableLoginPrompt,true);
  assert(values.environmentVariables.some(row=>row.name==='UNRELATED_SECRET'&&row.value==='untouched'));
  assert(!JSON.stringify(store).includes('untouched'),'A user API secret leaked into the backup');
  values.environmentVariables.push({name:'NEW_PREFERENCE',value:'keep'});
  await extension.disconnect(context);
  assert.strictEqual(values.claudeProcessWrapper,'/previous/wrapper');
  assert.strictEqual(values.disableLoginPrompt,false);
  assert(values.environmentVariables.some(row=>row.name==='ANTHROPIC_MODEL'&&row.value==='previous-model'));
  assert(values.environmentVariables.some(row=>row.name==='NEW_PREFERENCE'&&row.value==='keep'));
  assert.strictEqual(store.autoConnectDisabled,true);
  extension.openTerminal(context);
  assert.deepStrictEqual(api.lastTerminal.shellArgs,[]);
  assert.strictEqual(api.lastTerminal.shellPath,'codelaboon');
  extension.openTerminal(context,'jcode');
  assert.deepStrictEqual(api.lastTerminal.shellArgs,['jcode']);
  assert.throws(()=>extension.openTerminal(context,'jcode;echo unsafe'));
  fs.existsSync=oldExists;
  console.log('PASS VS Code connector preserves unrelated settings/secrets and restores owned values');
})().catch(error=>{console.error(error);process.exitCode=1;});
