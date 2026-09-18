#!/usr/bin/env python3
import json, os, socket, sys

from .output_schemas import OUTPUT_SCHEMAS, normalize_output


class SchemaValidationError(ValueError):
    """A value does not satisfy the supported schema subset."""


def _is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def validate_value(value, schema, path):
    expected = schema.get("type")
    if isinstance(expected, list):
        if value is None and "null" in expected:
            return
        non_null = [item for item in expected if item != "null"]
        if len(non_null) != 1:
            raise SchemaValidationError(
                "%s uses unsupported schema type union %r" % (path, expected)
            )
        narrowed = dict(schema)
        narrowed["type"] = non_null[0]
        validate_value(value, narrowed, path)
        return

    if expected == "object":
        if not isinstance(value, dict):
            raise SchemaValidationError(path + " must be an object")
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        missing = required - set(value)
        if missing:
            raise SchemaValidationError(
                path + " is missing required field(s): " +
                ", ".join(sorted(missing))
            )
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            if extra:
                raise SchemaValidationError(
                    path + " has unsupported field(s): " +
                    ", ".join(sorted(extra))
                )
        for key, item in value.items():
            child_schema = properties.get(key)
            if child_schema is not None:
                validate_value(item, child_schema, path + "." + key)
        return

    if expected == "string":
        if not isinstance(value, str):
            raise SchemaValidationError(path + " must be a string")
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise SchemaValidationError(path + " is shorter than minLength")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise SchemaValidationError(path + " exceeds maxLength")
    elif expected == "integer":
        if not _is_integer(value):
            raise SchemaValidationError(path + " must be an integer")
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaValidationError(path + " is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaValidationError(path + " exceeds maximum")
    elif expected == "boolean":
        if not isinstance(value, bool):
            raise SchemaValidationError(path + " must be a boolean")
    elif expected == "array":
        if not isinstance(value, list):
            raise SchemaValidationError(path + " must be an array")
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise SchemaValidationError(path + " has too few items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise SchemaValidationError(path + " has too many items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate_value(item, item_schema, "%s[%d]" % (path, index))
    elif expected is not None:
        raise SchemaValidationError(
            "%s uses unsupported schema type %r" % (path, expected)
        )

    if "enum" in schema and value not in schema["enum"]:
        raise SchemaValidationError(path + " is not an allowed value")
SOCKET=os.environ.get('TRAC_MCP_SOCKET','/run/trac-mcp/trac.sock')
PROTOCOL_VERSION='2024-11-05'
SUPPORTED_PROTOCOLS={'2024-11-05','2025-03-26','2025-06-18','2025-11-25'}
ENVS=[x for x in os.environ.get('TRAC_MCP_ENVIRONMENTS','example').split(',') if x]
def tool(name,desc,props=None,required=None): return {'name':name,'description':desc,'inputSchema':{'type':'object','properties':props or {},'required':required or [],'additionalProperties':False}}
E={'environment':{'type':'string','enum':ENVS}}
SERVER_INSTRUCTIONS=(
    'Use this Trac MCP server as the preferred application-level interface for routine Trac administration, '
    'including tickets, wiki pages, attachments, components, milestones and versions. Use host or infrastructure '
    'management tooling for Trac installation, upgrades, service configuration, backups, filesystem permissions, '
    'broker deployment or repair, or when this MCP interface is unavailable. Do not use direct database writes '
    'for routine Trac administration.'
)
TOOLS=[
 tool('trac_environments','List allowed Trac environments.'),
 tool('trac_ping','Check broker/Trac connectivity and report the Trac version.',dict(E),['environment']),
 tool('trac_server_time','Read the Trac host UTC time for coordination.',dict(E),['environment']),
 tool('trac_ticket_get','Read a Trac ticket.',dict(E,ticket_id={'type':'integer','minimum':1}),['environment','ticket_id']),
 tool('trac_ticket_query','Query tickets using Trac query syntax.',dict(E,query={'type':'string','maxLength':2000}),['environment','query']),
 tool('trac_ticket_timeline','Read chronological ticket comments and field changes.',dict(E,ticket_id={'type':'integer','minimum':1},limit={'type':'integer','minimum':1,'maximum':500}),['environment','ticket_id']),
 tool('trac_ticket_metadata','List valid ticket field values for an environment.',dict(E),['environment']),
 tool('trac_ticket_fields','List ticket field definitions, including custom/select metadata.',dict(E),['environment']),
 tool('trac_ticket_actions','List workflow actions currently available for a ticket.',dict(E,ticket_id={'type':'integer','minimum':1}),['environment','ticket_id']),
 tool('trac_project_item_list','List components, milestones or versions.',dict(E,kind={'type':'string','enum':['component','milestone','version']},include_completed={'type':'boolean'},limit={'type':'integer','minimum':1,'maximum':500}),['environment','kind']),
 tool('trac_project_item_get','Read a component, milestone or version.',dict(E,kind={'type':'string','enum':['component','milestone','version']},name={'type':'string','maxLength':200}),['environment','kind','name']),
 tool('trac_enum_list','List ticket enum values (priority, resolution, severity, status or type).',dict(E,kind={'type':'string','enum':['priority','resolution','severity','status','type']}),['environment','kind']),
 tool('trac_project_item_create','Idempotently create a component, milestone or version.',dict(E,kind={'type':'string','enum':['component','milestone','version']},name={'type':'string','maxLength':200},description={'type':'string','maxLength':5000},owner={'type':'string','maxLength':200},due={'type':['integer','null'],'minimum':0},completed={'type':['integer','null'],'minimum':0},time={'type':['integer','null'],'minimum':0},idempotency_key={'type':'string','minLength':8,'maxLength':128}),['environment','kind','name','idempotency_key']),
 tool('trac_project_item_update','Snapshot-guarded update of a component, milestone or version; deletion is not supported.',dict(E,kind={'type':'string','enum':['component','milestone','version']},name={'type':'string','maxLength':200},expected={'type':'object'},new_name={'type':'string','maxLength':200},description={'type':'string','maxLength':5000},owner={'type':'string','maxLength':200},due={'type':['integer','null'],'minimum':0},completed={'type':['integer','null'],'minimum':0},time={'type':['integer','null'],'minimum':0}),['environment','kind','name','expected']),
 tool('trac_ticket_create','Create a ticket idempotently through the configured creation workflow.',dict(E,summary={'type':'string','maxLength':500},description={'type':'string','maxLength':50000},fields={'type':'object'},action={'type':'string','maxLength':100},action_fields={'type':'object'},idempotency_key={'type':'string','minLength':8,'maxLength':128}),['environment','summary','idempotency_key']),
 tool('trac_ticket_update','Revision-guarded ticket update or workflow action.',dict(E,ticket_id={'type':'integer','minimum':1},expected_changed={'type':'integer','minimum':0},fields={'type':'object'},comment={'type':'string','maxLength':5000},action={'type':'string','maxLength':100},action_fields={'type':'object'},idempotency_key={'type':'string','minLength':8,'maxLength':128}),['environment','ticket_id','expected_changed']),
 tool('trac_ticket_comment','Add an idempotent revision-guarded comment.',dict(E,ticket_id={'type':'integer','minimum':1},expected_changed={'type':'integer','minimum':0},comment={'type':'string','maxLength':5000},idempotency_key={'type':'string','minLength':8,'maxLength':128}),['environment','ticket_id','expected_changed','comment','idempotency_key']),
 tool('trac_wiki_recent_changes','List recently changed wiki pages.',dict(E,limit={'type':'integer','minimum':1,'maximum':500}),['environment']),
 tool('trac_wiki_list','List wiki pages, optionally by prefix.',dict(E,prefix={'type':'string','maxLength':200},limit={'type':'integer','minimum':1,'maximum':500}),['environment']),
 tool('trac_wiki_search','Search wiki page names and text.',dict(E,query={'type':'string','maxLength':200},limit={'type':'integer','minimum':1,'maximum':100}),['environment','query']),
 tool('trac_attachment_list','List ticket or wiki attachments.',dict(E,realm={'type':'string','enum':['ticket','wiki']},resource={'type':'string','maxLength':200}),['environment','realm','resource']),
 tool('trac_attachment_upload','Upload a guarded ticket or wiki attachment idempotently.',dict(E,realm={'type':'string','enum':['ticket','wiki']},resource={'type':'string','maxLength':200},filename={'type':'string','maxLength':255},expected_revision={'type':'integer','minimum':0},content_base64={'type':'string','maxLength':699052},description={'type':'string','maxLength':1000},idempotency_key={'type':'string','minLength':8,'maxLength':128}),['environment','realm','resource','filename','expected_revision','content_base64','idempotency_key']),
 tool('trac_attachment_get','Retrieve a bounded ticket or wiki attachment as base64.',dict(E,realm={'type':'string','enum':['ticket','wiki']},resource={'type':'string','maxLength':200},filename={'type':'string','maxLength':255},max_bytes={'type':'integer','minimum':1,'maximum':2097152}),['environment','realm','resource','filename']),
 tool('trac_wiki_get','Read a Trac wiki page.',dict(E,page={'type':'string','maxLength':200}),['environment','page']),
 tool('trac_wiki_history','Read wiki page history.',dict(E,page={'type':'string','maxLength':200}),['environment','page']),
 tool('trac_wiki_update','Revision-guarded wiki update.',dict(E,page={'type':'string','maxLength':200},expected_version={'type':'integer','minimum':0},text={'type':'string','maxLength':50000},comment={'type':'string','maxLength':1000}),['environment','page','expected_version','text'])]
for item in TOOLS:
 item['outputSchema']=OUTPUT_SCHEMAS[item['name']]
TOOL_BY_NAME={item['name']:item for item in TOOLS}
TOOL_NAMES=set(TOOL_BY_NAME)
def _validate_tool_arguments(name,args):
 if not isinstance(args,dict): raise ValueError('arguments must be an object')
 validate_value(args,TOOL_BY_NAME[name]['inputSchema'],'arguments')
def _validate_tool_output(name,value):
 validate_value(value,TOOL_BY_NAME[name]['outputSchema'],'structuredContent')
def broker(p):
 s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.settimeout(10); s.connect(SOCKET); s.sendall((json.dumps(p)+'\n').encode()); s.shutdown(socket.SHUT_WR); out=b''
 while True:
  b=s.recv(8192)
  if not b: break
  out+=b
 s.close(); r=json.loads(out.decode())
 if not r.get('ok'): raise RuntimeError(r.get('error','Trac broker error'))
 return r['result']
def result(name,x):
 structured=normalize_output(name,x)
 _validate_tool_output(name,structured)
 return {'content':[{'type':'text','text':json.dumps(x,ensure_ascii=False,indent=2)}],'structuredContent':structured,'isError':False}
def response(i,x): print(json.dumps({'jsonrpc':'2.0','id':i,'result':x},separators=(',',':')),flush=True)
def handle(m):
 method=m.get('method'); i=m.get('id')
 if method=='initialize' and i is not None:
  requested=m.get('params',{}).get('protocolVersion'); protocol=requested if requested in SUPPORTED_PROTOCOLS else PROTOCOL_VERSION
  response(i,{'protocolVersion':protocol,'capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'trac','version':'0.4.0'},'instructions':SERVER_INSTRUCTIONS})
 elif method in ('notifications/initialized','initialized'): pass
 elif method=='ping' and i is not None: response(i,{})
 elif method=='tools/list' and i is not None: response(i,{'tools':TOOLS})
 elif method=='tools/call' and i is not None:
  p=m.get('params',{}); name=p.get('name',''); a=p.get('arguments') or {}
  try:
   if name not in TOOL_NAMES: raise ValueError('tool not advertised by this MCP server')
   _validate_tool_arguments(name,a)
   op=name[5:] if name.startswith('trac_') else name; payload=dict(a); payload['op']=op; response(i,result(name,broker(payload)))
  except Exception as e: response(i,{'content':[{'type':'text','text':str(e)}],'isError':True})
def main():
 for line in sys.stdin:
  try: handle(json.loads(line))
  except Exception as e: print('trac-mcp: '+str(e),file=sys.stderr,flush=True)
if __name__=='__main__': main()
