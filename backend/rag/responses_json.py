"""#233：Responses原生工具/图像适配，保留现有调用结果和工具编号契约。"""
from __future__ import annotations

import json
from urllib.parse import urlparse


def protocol_for(config):
    selected = getattr(config, 'api_protocol', 'auto')
    if selected in {'responses', 'chat_completions'}: return selected
    # 官方GPT工具要求Responses；已配置第三方兼容网关保持其既有协议，不凭模型名擅自迁移。
    return 'responses' if urlparse(getattr(config, 'base_url', '')).hostname == 'api.openai.com' else 'chat_completions'


def call(client, config, system, prompt, *, images, definitions, history, response_format,
         on_partial, on_usage, on_started, argument_context=None):
    from .structured_output import validate_tool_action, StructuredOutputError, decode_tool_arguments
    content = [{'type':'input_text','text':prompt}]
    content += [{'type':'input_image','image_url':url,'detail':'high'} for url in images or []]
    inputs = [{'role':'user','content':content}]
    for message in history or []:
        if message.get('role') == 'assistant' and message.get('tool_calls'):
            inputs.extend({'type':'function_call','call_id':t['id'], 'name':t['function']['name'],
                'arguments':t['function']['arguments']} for t in message['tool_calls'])
        elif message.get('role') == 'tool':
            inputs.append({'type':'function_call_output','call_id':message['tool_call_id'], 'output':message['content']})
        elif message.get('content'):
            inputs.append({'role':message['role'],'content':message['content']})
    fmt = response_format or {'type':'json_object'}
    if fmt.get('type') == 'json_schema':
        fmt = {'type':'json_schema', **fmt['json_schema']}
    options = {'model':config.model,'instructions':system,'input':inputs,'text':{'format':fmt}, 'stream':True}
    if definitions:
        options.update(tools=[{'type':'function',**d['function']} for d in definitions],parallel_tool_calls=False)
        if any(d['function']['name'].startswith('report_') for d in definitions):
            options['tool_choice']='required'
    stream = client.responses.create(**options)
    output=[];actions={};completed=False
    try:
        for event in stream:
            if event.type == 'response.output_text.delta':
                on_started();output.append(event.delta)
                if on_partial: on_partial(''.join(output))
            elif event.type == 'response.function_call_arguments.delta':
                on_started()
            elif event.type == 'response.output_item.done' and event.item.type == 'function_call':
                on_started();item=event.item
                actions[item.call_id] = {'name':item.name,'arguments':item.arguments}
            elif event.type == 'response.completed':
                completed=event.response.status=='completed'
                usage=getattr(event.response,'usage',None)
                if usage: on_usage(usage.model_dump())
            elif event.type in {'response.failed','response.incomplete','error'}:
                raise StructuredOutputError('Responses未完整完成，原结果保留，不采用截断观察')
    finally:
        close=getattr(stream,'close',None)
        if callable(close):close()
    if not completed: raise StructuredOutputError('Responses缺少完成回执')
    if actions:
        if len(actions)!=1:raise StructuredOutputError('只接受一个完整登记工具调用')
        call_id,action=next(iter(actions.items()));raw=action['arguments']
        action['arguments'],encoding=decode_tool_arguments(raw)
        action, bindings = validate_tool_action(action,definitions,argument_context=argument_context)
        return {'action':action, **({'_panel_bindings':bindings} if bindings else {}),
            **({'_argument_encoding':encoding} if encoding else {}),'_tool_call':{'id':call_id,'type':'function',
            'function':{'name':action['name'],'arguments':raw}}}
    from .llm import _extract_json
    result=_extract_json(''.join(output))
    if definitions and '_tool_call' in result:raise StructuredOutputError('模型文本不能伪造工具编号')
    if definitions and 'action' in result:validate_tool_action(result['action'],definitions)
    return result
