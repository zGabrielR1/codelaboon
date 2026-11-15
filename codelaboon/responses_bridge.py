"""Responses protocol for native Codex clients over free chat providers."""
import json
import secrets
import time


def to_chat(body):
    messages=[]
    if body.get('instructions'): messages.append({'role':'system','content':body['instructions']})
    inputs=body.get('input',[])
    if isinstance(inputs,str): inputs=[{'role':'user','content':inputs}]
    for item in inputs:
        kind=item.get('type','message')
        if kind=='message':
            content=item.get('content','')
            if isinstance(content,list):
                content=[{'type':'text','text':part.get('text','')} if part['type'] in ('input_text','output_text') else
                         {'type':'image_url','image_url':{'url':part['image_url']}} for part in content
                         if part['type'] in ('input_text','output_text','input_image')]
            messages.append({'role':item.get('role','user'),'content':content})
        elif kind in ('function_call','custom_tool_call'):
            arguments=item.get('arguments') if kind=='function_call' else json.dumps({'input':item.get('input','')})
            messages.append({'role':'assistant','content':None,'tool_calls':[{'id':item['call_id'],'type':'function',
                             'function':{'name':item['name'],'arguments':arguments or '{}'}}]})
        elif kind in ('function_call_output','custom_tool_call_output'):
            output=item.get('output','')
            messages.append({'role':'tool','tool_call_id':item['call_id'],'content':output if isinstance(output,str) else json.dumps(output)})
    tools=[]
    for tool in body.get('tools',[]):
        if tool['type'] in ('function','custom'):
            parameters=tool.get('parameters',{'type':'object','properties':{'input':{'type':'string'}},'required':['input']})
            tools.append({'type':'function','function':{'name':tool['name'],'description':tool.get('description',''), 'parameters':parameters}})
    result={'model':body['model'],'messages':messages,'stream':False,'max_tokens':body.get('max_output_tokens',4096)}
    if tools: result['tools']=tools
    return result


class ResponsesResponse:
    codelaboon_google_oauth=False
    def __init__(self,response,body):
        self.response=response;self.body=body;self.status_code=response.status_code
        self.headers={'Content-Type':'text/event-stream' if body.get('stream') and self.status_code<400 else 'application/json'}
    def close(self): self.response.close()
    def json(self):
        data=self.response.json()
        if self.status_code>=400:return data
        message=data['choices'][0]['message'];output=[]
        if message.get('content'):
            output.append({'id':'msg_'+secrets.token_hex(8),'type':'message','role':'assistant','status':'completed',
                           'content':[{'type':'output_text','text':message['content'],'annotations':[]}]})
        custom={tool['name'] for tool in self.body.get('tools',[]) if tool['type']=='custom'}
        for call in message.get('tool_calls',[]):
            function=call['function'];item={'id':'fc_'+secrets.token_hex(8),'call_id':call['id'],'status':'completed','name':function['name']}
            if function['name'] in custom:
                item.update(type='custom_tool_call',input=json.loads(function['arguments']).get('input',''))
            else:item.update(type='function_call',arguments=function['arguments'])
            output.append(item)
        return {'id':'resp_'+secrets.token_hex(8),'object':'response','created_at':int(time.time()),'status':'completed',
                'model':self.body['model'],'output':output,'usage':{'input_tokens':data.get('usage',{}).get('prompt_tokens',0),
                'output_tokens':data.get('usage',{}).get('completion_tokens',0),'total_tokens':data.get('usage',{}).get('total_tokens',0)}}
    def iter_content(self,chunk_size=None):
        document=self.json()
        if not self.body.get('stream') or self.status_code>=400:
            yield json.dumps(document).encode();return
        sequence=0
        def event(kind,**data):
            nonlocal sequence
            sequence+=1
            return ('event: '+kind+'\ndata: '+json.dumps({'type':kind,'sequence_number':sequence,**data})+'\n\n').encode()
        yield event('response.created',response={**document,'status':'in_progress','output':[]})
        for index,item in enumerate(document['output']):
            yield event('response.output_item.added',output_index=index,item={**item,'status':'in_progress'})
            if item['type']=='message':
                part=item['content'][0]
                yield event('response.content_part.added',output_index=index,item_id=item['id'],content_index=0,part={**part,'text':''})
                yield event('response.output_text.delta',output_index=index,item_id=item['id'],content_index=0,delta=part['text'])
                yield event('response.output_text.done',output_index=index,item_id=item['id'],content_index=0,text=part['text'])
                yield event('response.content_part.done',output_index=index,item_id=item['id'],content_index=0,part=part)
            yield event('response.output_item.done',output_index=index,item=item)
        yield event('response.completed',response=document)
