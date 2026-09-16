#!/usr/bin/env python3
import json, os, socket, sys
SOCKET=os.environ.get('TRAC_MCP_SOCKET','/run/trac-mcp/trac.sock')
PROTOCOL_VERSION='2024-11-05'
SUPPORTED_PROTOCOLS={'2024-11-05','2025-03-26','2025-06-18','2025-11-25'}
ENVS=[x for x in os.environ.get('TRAC_MCP_ENVIRONMENTS','example').split(',') if x]
def tool(name,desc,props=None,required=None): return {'name':name,'description':desc,'inputSchema':{'type':'object','properties':props or {},'required':required or [],'additionalProperties':False}}
E={'environment':{'type':'string','enum':ENVS}}
TOOLS=[
 tool('trac_environments','List allowed Trac environments.'),
 tool('trac_ticket_get','Read a Trac ticket.',dict(E,ticket_id={'type':'integer','minimum':1}),['environment','ticket_id']),
 tool('trac_ticket_query','Query tickets using Trac query syntax.',dict(E,query={'type':'string','maxLength':2000}),['environment','query']),
 tool('trac_ticket_timeline','Read chronological ticket comments and field changes.',dict(E,ticket_id={'type':'integer','minimum':1},limit={'type':'integer','minimum':1,'maximum':500}),['environment','ticket_id']),
 tool('trac_ticket_metadata','List valid ticket field values for an environment.',dict(E),['environment']),
 tool('trac_project_item_get','Read a component, milestone or version.',dict(E,kind={'type':'string','enum':['component','milestone','version']},name={'type':'string','maxLength':200}),['environment','kind','name']),
 tool('trac_project_item_create','Idempotently create a component, milestone or version.',dict(E,kind={'type':'string','enum':['component','milestone','version']},name={'type':'string','maxLength':200},description={'type':'string','maxLength':5000},owner={'type':'string','maxLength':200},idempotency_key={'type':'string','minLength':8,'maxLength':128}),['environment','kind','name','idempotency_key']),
 tool('trac_project_item_update','Snapshot-guarded update of a component, milestone or version; deletion is not supported.',dict(E,kind={'type':'string','enum':['component','milestone','version']},name={'type':'string','maxLength':200},expected={'type':'object'},new_name={'type':'string','maxLength':200},description={'type':'string','maxLength':5000},owner={'type':'string','maxLength':200}),['environment','kind','name','expected']),
 tool('trac_ticket_create','Create a ticket idempotently.',dict(E,summary={'type':'string','maxLength':500},description={'type':'string','maxLength':50000},fields={'type':'object'},idempotency_key={'type':'string','minLength':8,'maxLength':128}),['environment','summary','idempotency_key']),
 tool('trac_ticket_update','Revision-guarded ticket update.',dict(E,ticket_id={'type':'integer'},expected_changed={'type':'integer'},fields={'type':'object'},comment={'type':'string','maxLength':5000}),['environment','ticket_id','expected_changed','fields']),
 tool('trac_ticket_comment','Add an idempotent revision-guarded comment.',dict(E,ticket_id={'type':'integer'},expected_changed={'type':'integer'},comment={'type':'string','maxLength':5000},idempotency_key={'type':'string','minLength':8,'maxLength':128}),['environment','ticket_id','expected_changed','comment','idempotency_key']),
 tool('trac_wiki_list','List wiki pages, optionally by prefix.',dict(E,prefix={'type':'string','maxLength':200},limit={'type':'integer','minimum':1,'maximum':500}),['environment']),
 tool('trac_wiki_search','Search wiki page names and text.',dict(E,query={'type':'string','maxLength':200},limit={'type':'integer','minimum':1,'maximum':100}),['environment','query']),
 tool('trac_attachment_list','List ticket or wiki attachments.',dict(E,realm={'type':'string','enum':['ticket','wiki']},resource={'type':'string','maxLength':200}),['environment','realm','resource']),
 tool('trac_attachment_upload','Upload a guarded ticket or wiki attachment idempotently.',dict(E,realm={'type':'string','enum':['ticket','wiki']},resource={'type':'string','maxLength':200},filename={'type':'string','maxLength':255},expected_revision={'type':'integer','minimum':0},content_base64={'type':'string','maxLength':699052},description={'type':'string','maxLength':1000},idempotency_key={'type':'string','minLength':8,'maxLength':128}),['environment','realm','resource','filename','expected_revision','content_base64','idempotency_key']),
 tool('trac_attachment_get','Retrieve a bounded ticket or wiki attachment as base64.',dict(E,realm={'type':'string','enum':['ticket','wiki']},resource={'type':'string','maxLength':200},filename={'type':'string','maxLength':255},max_bytes={'type':'integer','minimum':1,'maximum':2097152}),['environment','realm','resource','filename']),
 tool('trac_wiki_get','Read a Trac wiki page.',dict(E,page={'type':'string','maxLength':200}),['environment','page']),
 tool('trac_wiki_history','Read wiki page history.',dict(E,page={'type':'string','maxLength':200}),['environment','page']),
 tool('trac_wiki_update','Revision-guarded wiki update.',dict(E,page={'type':'string','maxLength':200},expected_version={'type':'integer','minimum':0},text={'type':'string','maxLength':50000},comment={'type':'string','maxLength':1000}),['environment','page','expected_version','text'])]
def broker(p):
 s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.settimeout(10); s.connect(SOCKET); s.sendall((json.dumps(p)+'\n').encode()); s.shutdown(socket.SHUT_WR); out=b''
 while True:
  b=s.recv(8192)
  if not b: break
  out+=b
 s.close(); r=json.loads(out.decode())
 if not r.get('ok'): raise RuntimeError(r.get('error','Trac broker error'))
 return r['result']
def result(x): return {'content':[{'type':'text','text':json.dumps(x,ensure_ascii=False,indent=2)}],'isError':False}
def response(i,x): print(json.dumps({'jsonrpc':'2.0','id':i,'result':x},separators=(',',':')),flush=True)
def handle(m):
 method=m.get('method'); i=m.get('id')
 if method=='initialize' and i is not None:
  requested=m.get('params',{}).get('protocolVersion'); protocol=requested if requested in SUPPORTED_PROTOCOLS else PROTOCOL_VERSION
  response(i,{'protocolVersion':protocol,'capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'trac','version':'0.4.0'}})
 elif method in ('notifications/initialized','initialized'): pass
 elif method=='ping' and i is not None: response(i,{})
 elif method=='tools/list' and i is not None: response(i,{'tools':TOOLS})
 elif method=='tools/call' and i is not None:
  p=m.get('params',{}); name=p.get('name',''); a=p.get('arguments') or {}
  try:
   op=name[5:] if name.startswith('trac_') else name; payload={'op':op}; payload.update(a); response(i,result(broker(payload)))
  except Exception as e: response(i,{'content':[{'type':'text','text':str(e)}],'isError':True})
def main():
 for line in sys.stdin:
  try: handle(json.loads(line))
  except Exception as e: print('trac-mcp: '+str(e),file=sys.stderr,flush=True)
if __name__=='__main__': main()
