"""Real browser checks of disposable task operations and a mocked provider key."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import Mock,patch
if os.environ.get('CODELABOON_QA_INSTALLED')!='1':sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codelaboon import work
from codelaboon.web import create_server
from playwright.sync_api import sync_playwright,expect


def run():
    with tempfile.TemporaryDirectory(prefix='codelaboon-task-operations-') as temporary,patch.dict(os.environ,CODELABOON_CONFIG_DIR=temporary,CODELABOON_MODEL_CHECKS='0',CODELABOON_METRICS='0'):
        root=Path(temporary);work.initialize(root/'work.json')
        task=work.add(root,'Inspect only the disposable regression fixture',[[sys.executable,'-c','pass']],scope='Temporary fixture only',swarm={'controller':'worker','engine':'jcode','workers':1,'timeout':30,'interval':60,'cycles':0,'model':'free'})
        runtime=root/'work-runtime';attempt=runtime/'failed-fixture';attempt.mkdir(parents=True)
        (attempt/'result.json').write_text(json.dumps({'task':task,'stage':'build','harness':'swarm-'+task,'status':'failed','started':time.time()-5,'finished':time.time(),'exit_code':1}))
        (attempt/'output.log').write_text('Disposable failed attempt\nAuthorization: Bearer sk-fixture-secret')
        (runtime/'state.json').write_text(json.dumps({'last_attempts':{task:str(attempt)},'done':[],'cooldowns':{'swarm-'+task:time.time()+90}}))
        (runtime/'service-info.json').write_text(json.dumps({'features':['task-engine-selection','operator-interventions','task-execution-settings','task-retry']}))
        provider=Mock(keyless=False);provider.validate_api_key.return_value=False;provider.list_models.return_value=['live-account-model']
        cli=Mock(providers={'howtofix':provider});cli._current_provider_config.return_value={'models':[]}
        with patch('codelaboon.work.running',return_value=True),patch('codelaboon.engine_tasks.catalog',return_value=[]),patch('codelaboon.work.start') as start,patch('config.providers.save_provider_config',return_value=True) as save:
            server=create_server(0,cli);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with sync_playwright() as pw:
                    options={'executable_path':os.environ['CODELABOON_QA_CHROMIUM']} if os.environ.get('CODELABOON_QA_CHROMIUM') else {}
                    browser=pw.chromium.launch(**options)
                    try:
                        page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                        base='http://127.0.0.1:'+str(server.server_port);page.goto(base+'/tasks?task='+task)
                        expect(page.locator('#task-retry')).to_be_enabled()
                        page.locator('#task-message').fill('Check only the regression fixture');page.reload();expect(page.locator('#task-message')).to_have_value('Check only the regression fixture')
                        page.locator('#task-message').press('Control+Enter');expect(page.locator('#task-message')).to_have_value('');expect(page.locator('#conversation-feed')).to_contain_text('Check only the regression fixture')
                        page.locator('#task-message').press('ArrowUp');expect(page.locator('#task-message')).to_have_value('Check only the regression fixture');page.locator('#task-message').fill('')
                        page.locator('#open-attempts').click();expect(page.locator('#attempt-list')).to_contain_text('failed');page.locator('#attempt-list button').nth(1).click()
                        expect(page.locator('#log-meta')).to_contain_text('failed-fixture');expect(page.locator('#task-log')).to_contain_text('[redacted]')
                        page.locator('#task-retry').click();expect(page.locator('#task-retry')).to_have_text('Retry queued')
                        from codelaboon.work_queue import controls
                        assert (controls(runtime,task)/'RETRY.json').is_file();start.assert_not_called()
                        page.locator('#worker-action').click();expect(page.locator('#worker-action')).to_have_text('Resume worker')
                        page.once('dialog',lambda dialog:dialog.accept());page.locator('#worker-action').click();expect(page.locator('#worker-action')).to_have_text('Pause scheduling');start.assert_not_called()
                        if os.environ.get('CODELABOON_QA_SCREENSHOT'):page.screenshot(path=os.environ['CODELABOON_QA_SCREENSHOT'],full_page=True)
                        page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
                        page.goto(base+'/');page.locator('.actions summary').click();page.locator('#provider-settings').click();page.locator('#provider-key').fill('fixture-not-real-key');page.locator('#save-provider').click()
                        expect(page.locator('#provider-dialog')).not_to_be_visible();assert save.call_args.args[1]['api_key']=='fixture-not-real-key';assert page.locator('#provider-key').input_value()==''
                        assert 'fixture-not-real-key' not in page.evaluate('JSON.stringify(localStorage)+JSON.stringify(sessionStorage)')
                        assert not errors,errors
                        print('PASS browser: draft reload, keyboard guidance/recall, historical redacted logs, checkpoint retry, mobile layout and private key form; no real tasks or inference')
                    finally:browser.close()
            finally:server.shutdown();server.server_close();thread.join(timeout=3)

if __name__=='__main__':run()
