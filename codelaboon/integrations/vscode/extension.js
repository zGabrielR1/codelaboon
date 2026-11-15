'use strict';
const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

function bootstrap(context) {
  try { return JSON.parse(fs.readFileSync(path.join(context.extensionPath, 'backend.json'), 'utf8')); }
  catch { return {}; }
}
function options(context) {
  const local = bootstrap(context);
  const settings = vscode.workspace.getConfiguration('codelaboon');
  return { wrapper: settings.get('wrapperPath') || local.wrapper || '', configDir: local.configDir,
    cli: local.cli || settings.get('executablePath') || 'codelaboon', auto: local.connectOnInstall === true };
}
function setting(key) { return vscode.workspace.getConfiguration('claudeCode').inspect(key)?.globalValue; }
async function set(key, value) { await vscode.workspace.getConfiguration('claudeCode').update(key, value, vscode.ConfigurationTarget.Global); }

async function connectImpl(context, quiet = false) {
  const backend = options(context);
  if (!backend.wrapper || !path.isAbsolute(backend.wrapper) || !fs.existsSync(backend.wrapper)) {
    throw new Error('Run codelaboon ide install to register the installed backend wrapper.');
  }
  const managedEnv = { ANTHROPIC_MODEL: 'free', ...(backend.configDir ? { CLAUDE_CONFIG_DIR: backend.configDir } : {}) };
  const current = vscode.workspace.getConfiguration('claudeCode').get('environmentVariables') || [];
  let saved = context.globalState.get('connection');
  if (!saved) {
    saved = { wrapper: setting('claudeProcessWrapper'), login: setting('disableLoginPrompt'),
      env: Object.fromEntries(Object.keys(managedEnv).map(name => [name, current.find(row => row.name === name)?.value])) };
  }
  const env = current.filter(row => !Object.hasOwn(managedEnv, row.name));
  env.push(...Object.entries(managedEnv).map(([name, value]) => ({ name, value })));
  saved.owned = { wrapper: backend.wrapper, env: managedEnv };
  await context.globalState.update('connection', saved);
  await context.globalState.update('autoConnectDisabled', false);
  await set('environmentVariables', env);
  await set('disableLoginPrompt', true);
  await set('claudeProcessWrapper', backend.wrapper);
  if (!quiet) vscode.window.showInformationMessage('Claude Code is connected to Codelaboon. New sessions use the free backend.');
  return { connected: true, wrapper: backend.wrapper };
}
async function disconnectImpl(context) {
  const saved = context.globalState.get('connection');
  if (!saved) return;
  if (setting('claudeProcessWrapper') === saved.owned.wrapper) await set('claudeProcessWrapper', saved.wrapper);
  if (setting('disableLoginPrompt') === true) await set('disableLoginPrompt', saved.login);
  const current = vscode.workspace.getConfiguration('claudeCode').get('environmentVariables') || [];
  const restored = [];
  for (const row of current) {
    if (saved.owned.env[row.name] === row.value) {
      if (saved.env[row.name] !== undefined) restored.push({ name: row.name, value: saved.env[row.name] });
    } else restored.push(row);
  }
  await set('environmentVariables', restored);
  await context.globalState.update('connection', undefined);
  await context.globalState.update('autoConnectDisabled', true);
  vscode.window.showInformationMessage('Codelaboon connection removed. Previous managed settings restored.');
}
let operation = Promise.resolve();
function serialized(fn) { const next = operation.then(fn, fn); operation = next.catch(() => {}); return next; }
function connect(context, quiet = false) { return serialized(() => connectImpl(context, quiet)); }
function disconnect(context) { return serialized(() => disconnectImpl(context)); }
function openTerminal(context, engine = 'opencode') {
  const choices = { opencode: [], omp: ['omp'], kilo: ['kilo'], claude: ['claude'], crush: ['crush'], jcode: ['jcode'], codex: ['codex'] };
  if (!Object.hasOwn(choices, engine)) throw new Error('Unknown Codelaboon engine');
  const editor = vscode.window.activeTextEditor;
  const folder = (editor && vscode.workspace.getWorkspaceFolder(editor.document.uri)) || vscode.workspace.workspaceFolders?.[0];
  const terminal = vscode.window.createTerminal({ name: 'Codelaboon · '+engine, shellPath: options(context).cli,
    shellArgs: choices[engine], cwd: folder?.uri.fsPath });
  terminal.show();
  return terminal;
}
async function connectCodex(context, quiet = false) {
  const wrapper = bootstrap(context).codexWrapper;
  if (!wrapper || !path.isAbsolute(wrapper) || !fs.existsSync(wrapper)) throw new Error('Run codelaboon ide install --engine codex');
  const settings = vscode.workspace.getConfiguration('chatgpt');
  if (!context.globalState.get('codexConnection')) await context.globalState.update('codexConnection', {previous:settings.inspect('cliExecutable')?.globalValue, owned:wrapper});
  await settings.update('cliExecutable',wrapper,vscode.ConfigurationTarget.Global);
  await context.globalState.update('codexDisconnected',false);
  if (!quiet) vscode.window.showInformationMessage('Codex is connected to Codelaboon. Reload the window before starting a new Codex session.', 'Reload Window').then(action => {if (action==='Reload Window') return vscode.commands.executeCommand('workbench.action.reloadWindow');});
}
async function disconnectCodex(context) {
  const saved=context.globalState.get('codexConnection');
  if (!saved) return;
  const settings=vscode.workspace.getConfiguration('chatgpt');
  if (settings.inspect('cliExecutable')?.globalValue===saved.owned) await settings.update('cliExecutable',saved.previous,vscode.ConfigurationTarget.Global);
  await context.globalState.update('codexConnection',undefined);
  await context.globalState.update('codexDisconnected',true);
}
function activate(context) {
  require('./session-actions').register(vscode,context,options(context).cli);
  const output = vscode.window.createOutputChannel('Codelaboon');
  context.subscriptions.push(output);
  context.subscriptions.push(vscode.commands.registerCommand('codelaboon.openTerminal', () => openTerminal(context)));
  context.subscriptions.push(vscode.commands.registerCommand('codelaboon.openEngineTerminal', async () => {
    const engine = await vscode.window.showQuickPick(['opencode','omp','kilo','claude','crush','jcode','codex'], {title:'Open a native Codelaboon engine'});
    if (engine) openTerminal(context,engine);
  }));
  const guarded = fn => async (...args) => { try { return await fn(...args); } catch (error) { output.appendLine(error.message); vscode.window.showErrorMessage(error.message); throw error; } };
  context.subscriptions.push(vscode.commands.registerCommand('codelaboon.connectClaude', guarded(() => connect(context))));
  context.subscriptions.push(vscode.commands.registerCommand('codelaboon.disconnectClaude', guarded(() => disconnect(context))));
  context.subscriptions.push(vscode.commands.registerCommand('codelaboon.openClaude', guarded(async () => {
    await connect(context, true); await vscode.commands.executeCommand('claude-vscode.sidebar.open');
  })));
  context.subscriptions.push(vscode.commands.registerCommand('codelaboon.checkFreeModels', guarded(async () => {
    output.show(true); output.appendLine('Checking live free models and tool calls…');
    const child = spawn(options(context).cli, ['models', 'check', 'free'], { windowsHide: true });
    child.stdout.on('data', data => output.append(data.toString()));
    child.stderr.on('data', data => output.append(data.toString()));
    child.on('error', error => output.appendLine(error.message));
    child.on('close', code => output.appendLine('Checks finished (exit '+code+').'));
    context.subscriptions.push({dispose: () => child.kill()});
  })));
  context.subscriptions.push(vscode.commands.registerCommand('codelaboon.connectCodex', guarded(() => connectCodex(context))));
  context.subscriptions.push(vscode.commands.registerCommand('codelaboon.disconnectCodex', guarded(() => disconnectCodex(context))));
  context.subscriptions.push(vscode.commands.registerCommand('codelaboon.openCodex', guarded(async () => {await connectCodex(context); await vscode.commands.executeCommand('chatgpt.openSidebar');})));
  if (bootstrap(context).connectCodexOnInstall && !context.globalState.get('codexConnection') && !context.globalState.get('codexDisconnected')) connectCodex(context, true).catch(error => output.appendLine(error.message));
  context.subscriptions.push(vscode.window.registerUriHandler({ handleUri: guarded(uri => uri.path === '/codex' ? connectCodex(context) : connect(context)) }));
  if (options(context).auto && !context.globalState.get('connection') && !context.globalState.get('autoConnectDisabled')) connect(context, true).catch(error => output.appendLine(error.message));
  return { connect: () => connect(context, true), disconnect: () => disconnect(context) };
}
module.exports = { activate, connect, disconnect, openTerminal };
