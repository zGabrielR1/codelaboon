'use strict';
const assert=require('assert');const Module=require('module');const original=Module._load;
const snapshot={worker:{running:true,pending_count:2},local_controller:{model_installed:true,runtime_installed:true,evaluation:{passed:11,total:13}},routing:{preset:'balanced',observations:[]},security:{builtin_checks:['headers','tls','exposure']},pending_privilege_cases:[]};
Module._load=function(name,...args){return name==='child_process'?{execFile:(cli,args,opts,callback)=>{assert.strictEqual(cli,'fixture-cli');assert.deepStrictEqual(args,['doctor','--json']);callback(null,JSON.stringify(snapshot));}}:original.call(this,name,...args);};
const diagnostics=require('../codelaboon/integrations/vscode/diagnostics');Module._load=original;
let tree;const commands={};const api={EventEmitter:class{constructor(){this.event=()=>{};}fire(){}},TreeItem:class{constructor(label){this.label=label;}},window:{registerTreeDataProvider(id,provider){assert.strictEqual(id,'codelaboon.diagnostics');tree=provider;return{};}},commands:{registerCommand(name,fn){commands[name]=fn;return{};}}};
diagnostics.register(api,{subscriptions:[]},'fixture-cli');
(async()=>{const items=await tree.getChildren();assert(items.some(row=>row.label==='Pending tasks: 2'));assert(items.some(row=>row.label.includes('11/13')));assert(commands['codelaboon.refreshDiagnostics']);console.log('PASS diagnostics view consumes offline JSON and reports actual controller coverage');})().catch(error=>{console.error(error);process.exitCode=1;});
