"""Real browser regression: click, deep-link, follow live output and intervene.

Install test-only playwright and its Chromium browser before running this script.
All task files are temporary; no engine, worker or provider is executed.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codelaboon import work
from codelaboon.web import create_server
from playwright.sync_api import sync_playwright,expect


def run():
    evidence=Path('.runtime/task-chat-qa');evidence.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='task-chat-browser-') as temporary,patch.dict(os.environ,CODELABOON_CONFIG_DIR=temporary,CODELABOON_MODEL_CHECKS='0',CODELABOON_METRICS='0'):
        root=Path(temporary);work.initialize(root/'work.json')
        identity=work.add(root,'Review the local fixture regression',[['python','-c','print("fixture")']],scope='Temporary local fixture files only',swarm={'controller':'worker','engine':'jcode','workers':1,'timeout':30,'interval':60,'cycles':0,'model':'fixture'})
        runtime=root/'work-runtime';attempt=runtime/'fixture-attempt';attempt.mkdir(parents=True)
        (attempt/'result.json').write_text(json.dumps({'task':identity,'stage':'build','harness':'fixture','status':'running','started':time.time()}))
        output=attempt/'output.log';output.write_text('Fixture cycle started\n')
        reply=attempt/'reply.partial.txt';reply.write_text('I am reviewing the fixture regression and coordinating the workers.')
        (runtime/'service-info.json').write_text(json.dumps({'features':['task-engine-selection','operator-interventions','task-execution-settings','task-conversations']}))
        with patch('codelaboon.work.running',return_value=True),patch('codelaboon.engine_tasks.catalog',return_value=[]),patch('codelaboon.work.start') as start:
            server=create_server(0,Mock(providers={}))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with sync_playwright() as playwright:
                    browser=playwright.chromium.launch()
                    try:
                        page=browser.new_page(viewport={'width':1440,'height':900})
                        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                        base=f'http://127.0.0.1:{server.server_port}'
                        page.goto(base+'/tasks')
                        expect(page.locator('.task-row')).to_be_visible()
                        page.locator('#new-task').click()
                        expect(page.locator('#task-dialog')).to_be_visible()
                        expect(page.locator('#task-cycles')).to_have_value('1')
                        expect(page.locator('#task-profile')).to_have_value('coding')
                        expect(page.locator('#task-checks')).to_have_value('')
                        page.locator('#close-task').click()
                        row=page.locator('.task-row');expect(row).to_be_visible()
                        expect(page.locator('#message-form')).to_have_count(0)
                        row.click();expect(page).to_have_url(base+'/tasks?task='+identity)
                        expect(page.locator('#task-message')).to_be_in_viewport()
                        expect(page.locator('[data-kind=reply]')).to_contain_text('coordinating the workers')
                        output.write_text('Fixture cycle started\nNew live fixture output\n')
                        reply.write_text('The workers found the failing fixture path. I am checking their proposed fix.')
                        expect(page.locator('[data-kind=reply]')).to_contain_text('checking their proposed fix',timeout=10000)
                        page.locator('#task-message').fill('Prioritize the fixture regression')
                        page.locator('#send-message').click()
                        expect(page.locator('#conversation-feed')).to_contain_text('Awaiting the orchestrator')
                        page.reload();expect(page.locator('#conversation-feed')).to_contain_text('Prioritize the fixture regression')
                        page.locator('#open-task-settings').click()
                        page.locator('#settings-worker').fill('nvidia/fixture-worker')
                        page.locator('#settings-mode').select_option('local')
                        page.locator('#settings-planner').fill('local/fixture-planner')
                        page.locator('#settings-system').fill('Keep fixture reports concise')
                        page.locator('#settings-save').click()
                        expect(page.locator('#task-settings-dialog')).not_to_be_visible()
                        page.locator('#open-task-settings').click()
                        expect(page.locator('#settings-worker')).to_have_value('nvidia/fixture-worker')
                        expect(page.locator('#settings-mode')).to_have_value('local')
                        page.locator('#close-settings').click()
                        page.locator('#open-task-changes').click()
                        expect(page.locator('#changes-content')).to_contain_text('Current working tree')
                        page.locator('#close-changes').click()
                        page.locator('#back-tasks').click();expect(page).to_have_url(base+'/tasks')
                        page.go_back();expect(page.locator('#message-form')).to_be_visible()
                        for width in (1440,768,390):
                            page.set_viewport_size({'width':width,'height':900})
                            expect(page.locator('#send-message')).to_be_in_viewport()
                            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                            page.screenshot(path=str(evidence/f'chat-{width}.png'))
                            page.locator('#open-task-settings').click()
                            expect(page.locator('#settings-worker')).to_be_visible()
                            page.screenshot(path=str(evidence/f'settings-{width}.png'),full_page=True)
                            page.locator('#close-settings').click()
                        page.locator('#back-tasks').click()
                        expect(row).to_be_visible();row.click()
                        expect(page.locator('#send-message')).to_be_in_viewport()
                        (attempt/'reply.txt').write_text('The workers fixed the fixture regression; independent checks passed.')
                        reply.unlink()
                        (attempt/'result.json').write_text(json.dumps({'task':identity,'stage':'build','engine':'opencode','status':'succeeded','verification':'passed','started':time.time()-10,'finished':time.time()}))
                        (runtime/'state.json').write_text(json.dumps({'done':[identity],'cycles':{identity:1}}))
                        expect(page.locator('[data-kind=reply]')).to_contain_text('independent checks passed',timeout=10000)
                        page.locator('#task-message').fill('Now explain the fix and continue with the next fixture')
                        page.locator('#send-message').click()
                        expect(page.locator('#conversation-feed')).to_contain_text('Now explain the fix')
                        page.screenshot(path=str(evidence/'completed-followup.png'))
                        page.locator('#open-task-chat').click()
                        expect(page).to_have_url(base+'/?task='+identity)
                        expect(page.locator('#sessions [data-task]')).to_have_count(1)
                        expect(page.locator('#messages')).to_contain_text('independent checks passed')
                        expect(page.locator('#messages .role').last).to_have_text('You')
                        page.locator('#prompt').fill('Explain the result in this same conversation')
                        page.locator('#send').click()
                        expect(page.locator('#messages')).to_contain_text('Explain the result in this same conversation')
                        for width in (1440,768,390):
                            page.set_viewport_size({'width':width,'height':900})
                            expect(page.locator('#send')).to_be_in_viewport()
                            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                            page.screenshot(path=str(evidence/f'unified-chat-{width}.png'))
                        page.reload();expect(page.locator('#messages')).to_contain_text('Explain the result in this same conversation')
                        page.set_viewport_size({'width':1440,'height':900})
                        page.locator('#new').click()
                        expect(page.locator('#title')).to_have_text('New conversation')
                        expect(page.locator('#provider')).to_be_visible()
                        page.locator('#sessions [data-task]').click(force=True)
                        expect(page.locator('#messages')).to_contain_text('Explain the result in this same conversation')
                        page.goto(base+'/tasks?task=missing-task')
                        expect(page.get_by_role('heading',name='Task unavailable')).to_be_visible()
                        assert not errors,errors
                        assert len(list((runtime/'task-controls').glob('*/messages/*.json')))==3
                        start.assert_not_called()
                    finally:browser.close()
            finally:server.shutdown();server.server_close();thread.join(3)
    print('PASS task chat/settings/changes: navigation, live output, durable guidance, independent model settings and prompts, desktop/tablet/mobile, no model execution')


if __name__=='__main__':run()
