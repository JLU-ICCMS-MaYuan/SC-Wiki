"""DeepSeek官方严格工具的传输表示；不修改本地科学Schema及接受条件。"""
from copy import deepcopy
from urllib.parse import urlsplit
import json

from .structured_output import StructuredOutputError

MODE = "deepseek-strict-beta-def-v5"
MARKER = "_strict_transport"
ID_FIELDS = {'file_id','block_id','quote_id','source_id','table_id','region_id'}
ID_LISTS = {'source_ids','read_source_ids','contribution_source_ids','quote_ids','read_pages'}


def official(config):
    return urlsplit(getattr(config, "base_url", "")).hostname == "api.deepseek.com"


def schema_tool(schema):
    return {"type": "function", "function": {"name": "report_structured_output",
        "description": "Return the complete requested JSON using exactly this strict schema.",
        "strict": True, "parameters": schema}}


def wire_schema(schema):
    # 官方接口使用$def；anyOf分支中的纯引用须展开到有明确类型的等价Schema。
    def rename(value):
        if isinstance(value, list): return [rename(v) for v in value]
        if not isinstance(value, dict): return deepcopy(value)
        return {("$def" if k == "$defs" else k):
                v.replace("#/$defs/", "#/$def/") if k == "$ref" else rename(v)
                for k, v in value.items()}
    renamed = rename(schema)
    definitions = renamed.get("$def", {})
    def resolve(branch, chain):
        reference = None
        while isinstance(branch, dict) and set(branch) == {"$ref"}:
            reference = branch["$ref"]
            if not reference.startswith("#/$def/") or reference in chain:
                raise StructuredOutputError("严格传输的联合引用未能有限展开，未删除约束或降级")
            name = reference[len("#/$def/"):].replace("~1", "/").replace("~0", "~")
            if name not in definitions:
                raise StructuredOutputError("严格传输引用缺少定义")
            chain = (*chain, reference)
            branch = definitions[name]
        return branch, chain, reference
    def adapt(value, resolving=()):
        if isinstance(value, list): return [adapt(v, resolving) for v in value]
        if not isinstance(value, dict): return value
        if set(value) == {"$ref"}:
            target, chain, reference = resolve(value, resolving)
            # 引用别名和无type的联合定义在接口中不能形成有效嵌套约束。
            # 类型明确的共享定义继续引用，避免重复展开整份来源枚举。
            # 原始标识枚举须在字段本身约束；接口的基本类型引用不约束枚举。
            return {"$ref": reference} if target.get('type') == 'object' else adapt(target, chain)
        result = {k: adapt(v, resolving) for k, v in value.items() if k != "anyOf"}
        if "anyOf" in value:
            branches = []
            for branch in value["anyOf"]:
                branch, chain, _ = resolve(branch, resolving)
                expanded = adapt(branch, chain)
                branches.extend(expanded["anyOf"] if set(expanded) == {"anyOf"} else [expanded])
            result["anyOf"] = branches
        return result
    result=adapt(renamed)
    # 联合引用展开后删除已不再被引用的定义；保留全部实际约束，避免重复传输。
    needed=set()
    def references(node):
        if isinstance(node,dict):
            ref=node.get('$ref','')
            if ref.startswith('#/$def/'):
                name=ref[len('#/$def/'):].replace('~1','/').replace('~0','~')
                if name not in needed:
                    needed.add(name);references(result.get('$def',{}).get(name,{}))
            for key,value in node.items():
                if key!='$def':references(value)
        elif isinstance(node,list):
            for value in node:references(value)
    references(result)
    if '$def'in result:
        result['$def']={k:v for k,v in result['$def'].items()if k in needed}
        if not result['$def']:result.pop('$def')
    return result


def wire_tools(definitions):
    result = deepcopy(definitions)
    for item in result:
        item["function"]["parameters"] = wire_schema(item["function"]["parameters"])
    return result


def responses_schema(schema):
    """Responses保留标准$defs名称，共用已验证的等价联合/引用展开。"""
    projected=wire_schema(schema)
    def canonical(node):
        if isinstance(node,list):return [canonical(item)for item in node]
        if not isinstance(node,dict):return node
        return {('$defs' if key=='$def'else key):
            value.replace('#/$def/','#/$defs/')if key=='$ref'else canonical(value)
            for key,value in node.items()}
    return canonical(projected)


def request_tools(request):
    return request_view(request)['tool_definitions']


def restore_source_ids(value, reverse, field=None):
    if isinstance(value, dict):
        return {k:restore_source_ids(v,reverse,k)for k,v in value.items()}
    if isinstance(value, list):
        return [reverse.get(v,v)if field in ID_LISTS and isinstance(v,str)
                else restore_source_ids(v,reverse)for v in value]
    return reverse.get(value,value)if field in ID_FIELDS and isinstance(value,str)else value


def request_view(request):
    tools = request.get("tool_definitions")
    if not tools and request.get("response_schema") is not None:
        tools = [schema_tool(request["response_schema"])]
    tools=deepcopy(tools or [])
    result={k:request.get(k)for k in ('system_prompt','user_prompt')}
    reverse={}
    if (len(tools)==1 and tools[0]['function']['name']=='report_structured_output'
            and not request.get('tool_history')):
        schema=tools[0]['function']['parameters']
        definitions=schema.get('$defs',{})
        identifiers=set()
        def collect(node):
            if isinstance(node,dict):
                identifiers.update(v for v in node.get('enum',[])if isinstance(v,str))
                for child in node.values():collect(child)
            elif isinstance(node,list):
                for child in node:collect(child)
        for name,node in definitions.items():
            if name=='CurrentSourceFile' or name.startswith('CurrentSourceBlock'):collect(node)
        try:
            prompt=request['user_prompt'];start=prompt.index('{')
            payload=json.loads(prompt[start:])
        except (KeyError,ValueError,TypeError):
            payload=None
        present=set()
        def present_ids(node,field=None):
            if isinstance(node,dict):
                for k,v in node.items():present_ids(v,k)
            elif isinstance(node,list):
                for v in node:present_ids(v,field)
            elif isinstance(node,str) and (field in ID_FIELDS or field in ID_LISTS):present.add(node)
        present_ids(payload)
        if identifiers and isinstance(payload,dict) and identifiers <= present:
            forward={v:f'sref_{i}'for i,v in enumerate(sorted(identifiers))}
            reverse={v:k for k,v in forward.items()}
            packed=restore_source_ids(payload,forward)
            if restore_source_ids(packed,reverse)!=payload:
                raise StructuredOutputError('来源身份短编码不能无损恢复')
            def enums(node):
                if isinstance(node,dict):
                    return {k:[forward.get(v,v)for v in val]if k=='enum'else enums(val)
                            for k,val in node.items()}
                if isinstance(node,list):return [enums(v)for v in node]
                return node
            for name,node in list(definitions.items()):
                if name=='CurrentSourceFile' or name.startswith('CurrentSourceBlock'):
                    definitions[name]=enums(node)
            result['user_prompt']=prompt[:start]+json.dumps(packed,ensure_ascii=False,separators=(',',':'))
            result['system_prompt']=(request.get('system_prompt')or'')+'\nSource identity fields use lossless sref_N IDs. Output these registered IDs; the host restores original file/block identities. Never treat hashes inside source text as new reference IDs.'
    if len(tools)==1 and tools[0]['function']['name']=='report_structured_output':
        schema=tools[0]['function']['parameters']
        page_schema=schema.get('properties',{}).get('read_pages',{})
        item=page_schema.get('items',{})
        branches=item.get('anyOf',[item])
        pairs=[]
        for branch in branches:
            props=branch.get('properties',{})
            files=props.get('file_id',{}).get('enum',[])
            pages=props.get('page',{}).get('enum',[])
            if not files or not pages:
                pairs=[];break
            pairs.extend((fid,page)for fid in files for page in pages)
        if pairs:
            page_choices={f'pref_{i}':{'file_id':fid,'page':page}
                          for i,(fid,page)in enumerate(sorted(set(pairs)))}
            page_schema['items']={'type':'string','enum':list(page_choices)}
            reverse.update(page_choices)
            result['user_prompt']+=("\n\nUPLOADED_PAGE_CHOICES="+json.dumps(page_choices,ensure_ascii=False,separators=(',',':')))
            result['system_prompt']+=("\nFor this transport only, read_pages is an array of pref_N strings from UPLOADED_PAGE_CHOICES. "
                "Each choice is one indivisible uploaded file/page identity. The host restores the canonical objects. "
                "Do not mix one file's ID with another file's page. Empty read_pages remains [].")
    return {**result,'tool_definitions':wire_tools(tools),'source_ids':reverse}
