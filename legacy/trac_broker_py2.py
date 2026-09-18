#!/usr/bin/python2
# -*- coding: utf-8 -*-
from __future__ import print_function
import base64, calendar, datetime, grp, json, os, re, socket, struct, sys, time
try:
 import StringIO
 byte_stream=StringIO.StringIO
except ImportError:
 import io
 byte_stream=io.BytesIO
try:
 text_type=unicode
 binary_type=str
except NameError:
 text_type=str
 binary_type=bytes
from trac import __version__ as trac_version
from trac.env import Environment
from trac.ticket.api import TicketSystem
from trac.ticket.model import Ticket
from trac.ticket.query import Query
from trac.ticket.model import (Component, Milestone, Priority, Resolution,
                               Severity, Status, Type, Version)
from trac.test import MockRequest
from trac.util.datefmt import from_utimestamp
from trac.util.html import plaintext
from trac.wiki.model import WikiPage
from trac.wiki.api import WikiSystem
from trac.attachment import Attachment
SOCKET=os.environ.get('TRAC_MCP_SOCKET','/run/trac-mcp/trac.sock')
SOCKET_GROUP=os.environ.get('TRAC_MCP_SOCKET_GROUP','').strip()
ENVS=dict(x.split('=',1) for x in os.environ.get('TRAC_MCP_ENVIRONMENTS','example=/srv/trac/example').split(',') if '=' in x)
MAX=1048576
LOCAL_ADMIN_OPS=set((
 'ticket_delete','ticket_batch_create','ticket_batch_update','ticket_batch_delete',
 'project_item_delete','enum_create','enum_delete','attachment_delete','wiki_delete'
))
ADMIN_UIDS=set(int(x.strip()) for x in os.environ.get('TRAC_MCP_ADMIN_UIDS','').split(',')
               if x.strip())
PEERCRED_OPT=getattr(socket,'SO_PEERCRED',17 if sys.platform.startswith('linux') else None)

def peer_uid(connection):
 if PEERCRED_OPT is not None:
  raw=connection.getsockopt(socket.SOL_SOCKET,PEERCRED_OPT,struct.calcsize('3i'))
  pid,uid,gid=struct.unpack('3i',raw)
  return uid
 if hasattr(connection,'getpeereid'):
  uid,gid=connection.getpeereid(); return uid
 raise ValueError('peer credential checks unavailable on this platform')

def authorize_request(connection,request):
 op=request.get('op')
 if op not in LOCAL_ADMIN_OPS: return
 if not ADMIN_UIDS: raise ValueError('local admin operations are disabled')
 uid=peer_uid(connection)
 if uid not in ADMIN_UIDS: raise ValueError('local admin operation denied for peer uid %s'%uid)

def recv_request(connection):
 chunks=[]; total=0
 while True:
  part=connection.recv(65536)
  if not part: break
  total+=len(part)
  if total>MAX: raise ValueError('request too large')
  chunks.append(part)
 return b''.join(chunks)

def env(name):
 if name not in ENVS: raise ValueError('environment not allowed')
 return Environment(ENVS[name])
def txt(v,n):
 if not isinstance(v,(text_type,binary_type)): raise ValueError('text required')
 v=v.decode('utf-8') if isinstance(v,binary_type) and not isinstance(v,text_type) else v
 if len(v)>n: raise ValueError('text too long')
 return v
def changed_time(t): return getattr(t,'time_changed',t['changetime'])
def td(t):
 dt=changed_time(t); d={'id':t.id,'changed':calendar.timegm(dt.utctimetuple())*1000000+dt.microsecond}
 for k in ('summary','description','status','type','priority','milestone','component','owner','reporter','keywords','resolution'): d[k]=t[k]
 return d
def idem(e,key): return e.db_query('SELECT value FROM system WHERE name=%s',(key,))
def as_us(value):
 if not value: return None
 return calendar.timegm(value.utctimetuple())*1000000+value.microsecond
def simple(value):
 if value is None or isinstance(value,(bool,int,float)): return value
 if isinstance(value,binary_type) and not isinstance(value,text_type):
  return value.decode('utf-8')
 if isinstance(value,text_type): return value
 if isinstance(value,(list,tuple)): return [simple(x) for x in value]
 if isinstance(value,dict): return dict((text_type(k),simple(v)) for k,v in value.items())
 return text_type(value)
def project_class(kind):
 return {'component':Component,'milestone':Milestone,'version':Version}.get(kind)
def project_data(kind,x):
 out={'kind':kind,'name':x.name,'description':x.description}
 if kind=='component': out['owner']=x.owner
 elif kind=='milestone':
  out['due']=as_us(x.due); out['completed']=as_us(x.completed)
 elif kind=='version': out['time']=as_us(x.time)
 return out
def enum_class(kind):
 return {'priority':Priority,'resolution':Resolution,'severity':Severity,
         'status':Status,'type':Type}.get(kind)
def enum_data(kind,x):
 return {'kind':kind,'name':x.name,'value':getattr(x,'value',None),
         'description':getattr(x,'description','')}
def target_revision(e,realm,resource):
 if realm=='ticket':
  t=Ticket(e,int(resource)); return td(t)['changed']
 if realm=='wiki':
  w=WikiPage(e,resource)
  if not w.exists: raise ValueError('attachment target not found')
  return w.version
 raise ValueError('attachment realm not allowed')
def require_delete(d):
 if d.get('confirm')!='DELETE': raise ValueError('confirm must be DELETE')
def workflow_request(e,args=None,method='GET'):
 author=os.environ.get('TRAC_MCP_AUTHOR','MCP')
 req=MockRequest(e,args=args or {},method=method)
 req.callbacks['authname']=lambda req: author
 return req,author
def dispatch(d):
 op=d.get('op')
 if op=='environments': return {'environments':sorted(ENVS)}
 e=env(d.get('environment'))
 if op=='ping':
  return {'environment':d['environment'],'project_name':simple(e.project_name),
          'trac_version':trac_version}
 if op=='server_time':
  now=time.time()
  return {'unix_timestamp':int(now),
          'iso_utc':datetime.datetime.utcfromtimestamp(now).replace(microsecond=0).isoformat()+'Z'}
 if op=='ticket_fields':
  fields=[]
  for field in TicketSystem(e).get_ticket_fields():
   fields.append(simple(dict((k,v) for k,v in field.items()
                             if k in ('name','type','label','custom','optional',
                                      'options','value','format','max_size'))))
  return {'fields':fields}
 if op=='ticket_actions':
  ticket=Ticket(e,int(d['ticket_id']))
  req,auth=workflow_request(e)
  system=TicketSystem(e); actions=[]
  for action in system.get_available_actions(req,ticket):
   item={'name':action,'label':action,'hint':'','input_fields':[]}
   for controller in system.action_controllers:
    available=[a for weight,a in (controller.get_ticket_actions(req,ticket) or [])]
    if action not in available: continue
    try:
     label,control,hint=controller.render_ticket_action_control(req,ticket,action)
     item['label']=plaintext(text_type(label))
     item['hint']=plaintext(text_type(hint))
     html=text_type(control)
     item['input_fields']=sorted(set(re.findall(r'name=["\\\']([^"\\\']+)',html)))
    except Exception:
     pass
    break
   actions.append(item)
  return {'ticket_id':ticket.id,'authname':auth,'actions':actions}
 if op=='project_item_list':
  kind=txt(d['kind'],20); cls=project_class(kind)
  if not cls: raise ValueError('project item kind not allowed')
  items=[project_data(kind,x) for x in cls.select(e)]
  if kind=='milestone' and not bool(d.get('include_completed',True)):
   items=[x for x in items if x.get('completed') is None]
  limit=min(max(int(d.get('limit',200)),1),500)
  return {'kind':kind,'items':items[:limit],'total':len(items)}
 if op=='enum_list':
  kind=txt(d['kind'],20); cls=enum_class(kind)
  if not cls: raise ValueError('enum kind not allowed')
  items=[enum_data(kind,x) for x in cls.select(e)]
  return {'kind':kind,'items':items}
 if op=='ticket_get': return td(Ticket(e,int(d['ticket_id'])))
 if op=='ticket_query':
  q=txt(d['query'],2000); q=q if 'max=' in q else q+'&max=50'
  return {'tickets':[td(Ticket(e,int(x['id']))) for x in Query.from_string(e,q).execute()[:100]]}
 if op=='ticket_timeline':
  t=Ticket(e,int(d['ticket_id'])); limit=min(max(int(d.get('limit',100)),1),500); out=[]
  for tm,author,field,old,new,permanent in t.get_changelog():
   out.append({'time':calendar.timegm(tm.utctimetuple())*1000000+tm.microsecond,'author':author,'field':field,'old':old,'new':new,'permanent':bool(permanent)})
  return {'ticket_id':t.id,'timeline':out[-limit:]}
 if op=='ticket_metadata':
  def names(cls): return [x.name for x in cls.select(e)]
  owners=[]
  try: owners=sorted(set([x[0] for x in e.db_query("SELECT DISTINCT owner FROM ticket WHERE owner<>'' ORDER BY owner")]))
  except Exception: pass
  return {'types':names(Type),'priorities':names(Priority),'components':names(Component),'milestones':names(Milestone),'versions':names(Version),'resolutions':['fixed','invalid','wontfix','duplicate','worksforme'],'owners':owners[:200]}
 if op=='project_item_get':
  kind=txt(d['kind'],20); name=txt(d['name'],200)
  cls={'component':Component,'milestone':Milestone,'version':Version}.get(kind)
  if not cls: raise ValueError('project item kind not allowed')
  x=cls(e,name)
  if not x.exists: raise ValueError('project item not found')
  return project_data(kind,x)
 if op=='project_item_create':
  kind=txt(d['kind'],20); name=txt(d['name'],200); cls={'component':Component,'milestone':Milestone,'version':Version}.get(kind)
  if not cls: raise ValueError('project item kind not allowed')
  key='mcp-project-item:%s:%s'%(d['environment'],txt(d['idempotency_key'],128)); old=idem(e,key)
  if old:
   existing=cls(e,old[0][0]); out=project_data(kind,existing); out['duplicate']=True; return out
  x=cls(e); x.name=name; x.description=txt(d.get('description',''),5000)
  if kind=='component': x.owner=txt(d.get('owner',''),200)
  elif kind=='milestone':
   if d.get('due') is not None: x.due=from_utimestamp(int(d['due']))
   if d.get('completed') is not None: x.completed=from_utimestamp(int(d['completed']))
  elif kind=='version' and d.get('time') is not None:
   x.time=from_utimestamp(int(d['time']))
  x.insert(); e.db_transaction('INSERT INTO system (name,value) VALUES (%s,%s)',(key,x.name))
  out=project_data(kind,x); out['duplicate']=False; return out
 if op=='project_item_update':
  kind=txt(d['kind'],20); name=txt(d['name'],200); cls={'component':Component,'milestone':Milestone,'version':Version}.get(kind)
  if not cls: raise ValueError('project item kind not allowed')
  x=cls(e,name)
  if not x.exists: raise ValueError('project item not found')
  expected=d.get('expected') or {}
  current=project_data(kind,x)
  if expected!=current: raise ValueError('stale project item')
  if 'new_name' in d: x.name=txt(d['new_name'],200)
  if 'description' in d: x.description=txt(d['description'],5000)
  if kind=='component' and 'owner' in d: x.owner=txt(d['owner'],200)
  elif kind=='milestone':
   if 'due' in d: x.due=from_utimestamp(int(d['due'])) if d['due'] is not None else None
   if 'completed' in d: x.completed=from_utimestamp(int(d['completed'])) if d['completed'] is not None else None
  elif kind=='version' and 'time' in d:
   x.time=from_utimestamp(int(d['time'])) if d['time'] is not None else None
  x.update(os.environ.get('TRAC_MCP_AUTHOR','MCP')) if kind=='milestone' else x.update()
  return project_data(kind,x)
 if op=='project_item_delete':
  require_delete(d)
  kind=txt(d['kind'],20); name=txt(d['name'],200); cls=project_class(kind)
  if not cls: raise ValueError('project item kind not allowed')
  key='mcp-project-item-delete:%s:%s'%(d['environment'],txt(d['idempotency_key'],128)); old=idem(e,key)
  if old: return {'kind':kind,'name':name,'deleted':True,'duplicate':True}
  x=cls(e,name)
  if not x.exists: raise ValueError('project item not found')
  current=project_data(kind,x)
  if (d.get('expected') or {})!=current: raise ValueError('stale project item')
  x.delete()
  e.db_transaction('INSERT INTO system (name,value) VALUES (%s,%s)',(key,name))
  return {'kind':kind,'name':name,'deleted':True,'duplicate':False}
 if op=='enum_create':
  kind=txt(d['kind'],20); name=txt(d['name'],200); cls=enum_class(kind)
  if not cls or kind=='status': raise ValueError('enum kind not mutable')
  key='mcp-enum-create:%s:%s'%(d['environment'],txt(d['idempotency_key'],128)); old=idem(e,key)
  if old:
   x=cls(e,old[0][0]); out=enum_data(kind,x); out['duplicate']=True; return out
  x=cls(e); x.name=name; x.description=txt(d.get('description',''),1000)
  if d.get('value') is not None: x.value=txt(d['value'],50)
  x.insert(); e.db_transaction('INSERT INTO system (name,value) VALUES (%s,%s)',(key,x.name))
  out=enum_data(kind,x); out['duplicate']=False; return out
 if op=='enum_delete':
  require_delete(d)
  kind=txt(d['kind'],20); name=txt(d['name'],200); cls=enum_class(kind)
  if not cls or kind=='status': raise ValueError('enum kind not mutable')
  key='mcp-enum-delete:%s:%s'%(d['environment'],txt(d['idempotency_key'],128)); old=idem(e,key)
  if old: return {'kind':kind,'name':name,'deleted':True,'duplicate':True}
  x=cls(e,name); current=enum_data(kind,x)
  if (d.get('expected') or {})!=current: raise ValueError('stale enum item')
  x.delete(); e.db_transaction('INSERT INTO system (name,value) VALUES (%s,%s)',(key,name))
  return {'kind':kind,'name':name,'deleted':True,'duplicate':False}
 if op=='ticket_create':
  key='mcp-create:%s:%s'%(d['environment'],txt(d['idempotency_key'],128)); old=idem(e,key)
  if old: return {'ticket':td(Ticket(e,int(old[0][0]))),'duplicate':True}
  author=os.environ.get('TRAC_MCP_AUTHOR','MCP')
  t=Ticket(e); t['summary']=txt(d['summary'],500); t['description']=txt(d.get('description',''),50000)
  t['reporter']=author
  allowed=('type','priority','milestone','component','owner','keywords','cc','version')
  for k,v in d.get('fields',{}).items():
   if k not in allowed: raise ValueError('field not allowed')
   t[k]=txt(v,1000)
  requested_action=d.get('action')
  args={}
  if requested_action is not None:
   requested_action=txt(requested_action,100); args['action']=requested_action
  for k,v in (d.get('action_fields') or {}).items():
   if not re.match(r'^action_[A-Za-z0-9_]+$',text_type(k)): raise ValueError('invalid action field')
   args[text_type(k)]=txt(v,1000)
  req,author=workflow_request(e,args,method='POST')
  system=TicketSystem(e); actions=system.get_available_actions(req,t)
  action=requested_action or ('create' if 'create' in actions else (actions[0] if actions else None))
  if not action or action not in actions: raise ValueError('ticket creation workflow action not available')
  controllers=[]; action_changes={}
  for controller in system.action_controllers:
   available=[a for weight,a in (controller.get_ticket_actions(req,t) or [])]
   if action not in available: continue
   controllers.append(controller)
   changes=controller.get_ticket_changes(req,t,action) or {}
   for k,v in changes.items(): action_changes[k]=v
  for k,v in action_changes.items(): t[k]=v
  tid=t.insert()
  for controller in controllers: controller.apply_action_side_effects(req,t,action)
  e.db_transaction('INSERT INTO system (name,value) VALUES (%s,%s)',(key,str(tid)))
  return {'ticket':td(Ticket(e,tid)),'duplicate':False,'action':action,
          'action_changes':simple(action_changes)}
 if op=='ticket_update':
  key=None
  if d.get('idempotency_key'):
   key='mcp-update:%s:%s'%(d['environment'],txt(d['idempotency_key'],128)); old=idem(e,key)
   if old: return {'ticket':td(Ticket(e,int(d['ticket_id']))),'duplicate':True}
  t=Ticket(e,int(d['ticket_id'])); dt=changed_time(t); changed=calendar.timegm(dt.utctimetuple())*1000000+dt.microsecond
  if changed!=int(d['expected_changed']): raise ValueError('stale ticket revision')
  direct_allowed=('summary','description','type','priority','milestone','component','owner','keywords','cc','version')
  workflow_allowed=direct_allowed+('status','resolution')
  fields=dict(d.get('fields',{}) or {})
  for k in fields:
   if k not in direct_allowed: raise ValueError('field not allowed; status/resolution require workflow action')
  action=d.get('action'); controllers=[]; action_changes={}
  if action is not None:
   action=txt(action,100)
   args={'action':action}
   for k,v in (d.get('action_fields') or {}).items():
    if not re.match(r'^action_[A-Za-z0-9_]+$',text_type(k)): raise ValueError('invalid action field')
    args[text_type(k)]=txt(v,1000)
   req,author=workflow_request(e,args,method='POST')
   system=TicketSystem(e)
   if action not in system.get_available_actions(req,t): raise ValueError('ticket action not available')
   for controller in system.action_controllers:
    available=[a for weight,a in (controller.get_ticket_actions(req,t) or [])]
    if action not in available: continue
    controllers.append(controller)
    changes=controller.get_ticket_changes(req,t,action) or {}
    for k,v in changes.items(): action_changes[k]=v
   fields.update(action_changes)
  if not fields and not d.get('comment'): raise ValueError('fields, action or comment required')
  for k,v in fields.items():
   if k not in workflow_allowed: raise ValueError('workflow changed unsupported field')
   t[k]=txt(v,50000 if k=='description' else 1000)
  t.save_changes(os.environ.get('TRAC_MCP_AUTHOR','MCP'),txt(d.get('comment','Updated through MCP'),5000))
  for controller in controllers:
   controller.apply_action_side_effects(req,t,action)
  if key: e.db_transaction('INSERT INTO system (name,value) VALUES (%s,%s)',(key,str(t.id)))
  return {'ticket':td(Ticket(e,t.id)),'duplicate':False,'action':action,'action_changes':simple(action_changes)}
 if op=='ticket_comment':
  key='mcp-comment:%s:%s'%(d['environment'],txt(d['idempotency_key'],128))
  old=idem(e,key)
  if old: return {'ticket':td(Ticket(e,int(d['ticket_id']))),'duplicate':True}
  t=Ticket(e,int(d['ticket_id']))
  dt=changed_time(t); changed=calendar.timegm(dt.utctimetuple())*1000000+dt.microsecond
  if changed!=int(d['expected_changed']): raise ValueError('stale ticket revision')
  t.save_changes(os.environ.get('TRAC_MCP_AUTHOR','MCP'),txt(d['comment'],5000))
  e.db_transaction('INSERT INTO system (name,value) VALUES (%s,%s)',(key,str(t.id)))
  return {'ticket':td(Ticket(e,t.id)),'duplicate':False}
 if op=='ticket_delete':
  require_delete(d)
  key='mcp-ticket-delete:%s:%s'%(d['environment'],txt(d['idempotency_key'],128)); old=idem(e,key)
  if old: return {'ticket_id':int(d['ticket_id']),'deleted':True,'duplicate':True}
  t=Ticket(e,int(d['ticket_id'])); current=td(t)
  if current['changed']!=int(d['expected_changed']): raise ValueError('stale ticket revision')
  tid=t.id; t.delete()
  e.db_transaction('INSERT INTO system (name,value) VALUES (%s,%s)',(key,str(tid)))
  return {'ticket_id':tid,'deleted':True,'duplicate':False}
 if op=='ticket_batch_create':
  items=d.get('items')
  if not isinstance(items,list) or not items or len(items)>50: raise ValueError('items must contain 1-50 tickets')
  base=txt(d['idempotency_key'],96); created=[]; failed=[]
  for i,item in enumerate(items):
   try:
    if not isinstance(item,dict): raise ValueError('ticket item must be object')
    req={'op':'ticket_create','environment':d['environment'],
         'summary':item.get('summary'),'description':item.get('description',''),
         'fields':item.get('fields',{}),'action':item.get('action'),
         'action_fields':item.get('action_fields',{}),
         'idempotency_key':'%s-%d'%(base,i)}
    result=dispatch(req); created.append({'index':i,'ticket':result['ticket'],'duplicate':result.get('duplicate',False)})
   except Exception as x:
    failed.append({'index':i,'error':text_type(x)})
  return {'created':created,'failed':failed,'total':len(items),
          'succeeded':len(created),'failed_count':len(failed)}
 if op=='ticket_batch_update':
  items=d.get('items')
  if not isinstance(items,list) or not items or len(items)>50: raise ValueError('items must contain 1-50 tickets')
  base=txt(d['idempotency_key'],96); updated=[]; failed=[]
  for i,item in enumerate(items):
   try:
    if not isinstance(item,dict): raise ValueError('ticket item must be object')
    req={'op':'ticket_update','environment':d['environment'],
         'ticket_id':item.get('ticket_id'),'expected_changed':item.get('expected_changed'),
         'fields':item.get('fields',{}),'comment':item.get('comment','Updated through batch operation'),
         'action':item.get('action'),'action_fields':item.get('action_fields',{}),
         'idempotency_key':'%s-%d'%(base,i)}
    result=dispatch(req); updated.append({'index':i,'ticket':result['ticket'],'duplicate':result.get('duplicate',False)})
   except Exception as x:
    failed.append({'index':i,'ticket_id':item.get('ticket_id') if isinstance(item,dict) else None,'error':text_type(x)})
  return {'updated':updated,'failed':failed,'total':len(items),
          'succeeded':len(updated),'failed_count':len(failed)}
 if op=='ticket_batch_delete':
  require_delete(d)
  items=d.get('items')
  if not isinstance(items,list) or not items or len(items)>50: raise ValueError('items must contain 1-50 tickets')
  base=txt(d['idempotency_key'],96); deleted=[]; failed=[]
  for i,item in enumerate(items):
   try:
    if not isinstance(item,dict): raise ValueError('ticket item must be object')
    req={'op':'ticket_delete','environment':d['environment'],
         'ticket_id':item.get('ticket_id'),'expected_changed':item.get('expected_changed'),
         'confirm':'DELETE','idempotency_key':'%s-%d'%(base,i)}
    result=dispatch(req); deleted.append({'index':i,'ticket_id':result['ticket_id'],'duplicate':result.get('duplicate',False)})
   except Exception as x:
    failed.append({'index':i,'ticket_id':item.get('ticket_id') if isinstance(item,dict) else None,'error':text_type(x)})
  return {'deleted':deleted,'failed':failed,'total':len(items),
          'succeeded':len(deleted),'failed_count':len(failed)}
 if op=='wiki_recent_changes':
  limit=min(max(int(d.get('limit',50)),1),500)
  rows=e.db_query("""SELECT w.name,w.version,w.time,w.author,w.comment
                     FROM wiki w
                     JOIN (SELECT name,MAX(version) AS version
                           FROM wiki GROUP BY name) latest
                       ON latest.name=w.name AND latest.version=w.version
                     ORDER BY w.time DESC""")
  out=[]
  for name,version,tm,author,comment in rows[:limit]:
   out.append({'page':name,'version':version,'time':tm,
               'author':author or '','comment':comment or ''})
  return {'changes':out,'limit':limit}
 if op=='wiki_list':
  prefix=txt(d.get('prefix',''),200); limit=min(max(int(d.get('limit',100)),1),500)
  pages=sorted([x for x in WikiSystem(e).get_pages() if x.startswith(prefix)])[:limit]
  return {'pages':pages}
 if op=='wiki_search':
  query=txt(d['query'],200).lower(); limit=min(max(int(d.get('limit',25)),1),100); out=[]
  for name in sorted(WikiSystem(e).get_pages()):
   w=WikiPage(e,name); original=name+'\n'+w.text; pos=original.lower().find(query)
   if pos<0: continue
   a=max(0,pos-120); b=min(len(original),pos+len(query)+240)
   out.append({'page':name,'version':w.version,'excerpt':original[a:b]})
   if len(out)>=limit: break
  return {'results':out}
 if op=='attachment_list':
  realm=txt(d['realm'],20); resource=txt(d['resource'],200)
  if realm not in ('ticket','wiki'): raise ValueError('attachment realm not allowed')
  out=[]
  for a in Attachment.select(e,realm,resource): out.append({'realm':a.parent_realm,'resource':a.parent_id,'filename':a.filename,'size':a.size,'author':a.author,'description':a.description})
  return {'attachments':out[:200]}
 if op=='attachment_upload':
  realm=txt(d['realm'],20); resource=txt(d['resource'],200); filename=txt(d['filename'],255)
  if realm not in ('ticket','wiki'): raise ValueError('attachment realm not allowed')
  if filename in ('.','..') or '/' in filename or '\\' in filename or '\x00' in filename: raise ValueError('invalid attachment filename')
  key='mcp-attachment:%s:%s'%(d['environment'],txt(d['idempotency_key'],128)); old=idem(e,key)
  if old: return {'realm':realm,'resource':resource,'filename':old[0][0],'duplicate':True}
  expected=int(d['expected_revision'])
  if realm=='ticket':
   t=Ticket(e,int(resource)); dt=changed_time(t); current=calendar.timegm(dt.utctimetuple())*1000000+dt.microsecond
  else:
   w=WikiPage(e,resource)
   if not w.exists: raise ValueError('attachment target not found')
   current=w.version
  if current!=expected: raise ValueError('stale attachment target revision')
  for existing in Attachment.select(e,realm,resource):
   if existing.filename==filename: raise ValueError('attachment already exists')
  raw=d.get('content_base64','')
  if not isinstance(raw,(text_type,binary_type)): raise ValueError('base64 content required')
  try: data=base64.b64decode(raw)
  except Exception: raise ValueError('invalid base64 content')
  if len(data)>524288: raise ValueError('attachment too large')
  a=Attachment(e,realm,resource); a.author=os.environ.get('TRAC_MCP_AUTHOR','MCP'); a.description=txt(d.get('description','Uploaded through MCP'),1000)
  a.insert(filename,byte_stream(data),len(data)); e.db_transaction('INSERT INTO system (name,value) VALUES (%s,%s)',(key,a.filename))
  return {'realm':realm,'resource':resource,'filename':a.filename,'size':a.size,'duplicate':False}
 if op=='attachment_get':
  realm=txt(d['realm'],20); resource=txt(d['resource'],200); filename=txt(d['filename'],255)
  if realm not in ('ticket','wiki'): raise ValueError('attachment realm not allowed')
  a=Attachment(e,realm,resource,filename); max_bytes=min(max(int(d.get('max_bytes',1048576)),1),2097152)
  if a.size>max_bytes: raise ValueError('attachment too large')
  f=a.open(); data=f.read(max_bytes+1); f.close()
  if len(data)>max_bytes: raise ValueError('attachment too large')
  return {'realm':realm,'resource':resource,'filename':a.filename,'size':a.size,'author':a.author,'description':a.description,'content_base64':base64.b64encode(data).decode('ascii')}
 if op=='attachment_delete':
  require_delete(d)
  realm=txt(d['realm'],20); resource=txt(d['resource'],200); filename=txt(d['filename'],255)
  if realm not in ('ticket','wiki'): raise ValueError('attachment realm not allowed')
  key='mcp-attachment-delete:%s:%s'%(d['environment'],txt(d['idempotency_key'],128)); old=idem(e,key)
  if old: return {'realm':realm,'resource':resource,'filename':filename,'deleted':True,'duplicate':True}
  current=target_revision(e,realm,resource)
  if current!=int(d['expected_revision']): raise ValueError('stale attachment target revision')
  a=Attachment(e,realm,resource,filename); a.delete()
  e.db_transaction('INSERT INTO system (name,value) VALUES (%s,%s)',(key,filename))
  return {'realm':realm,'resource':resource,'filename':filename,'deleted':True,'duplicate':False}
 if op=='wiki_get':
  w=WikiPage(e,txt(d['page'],200))
  if not w.exists: raise ValueError('wiki page not found')
  return {'page':w.name,'version':w.version,'text':w.text,'author':w.author,'comment':w.comment}
 if op=='wiki_history':
  w=WikiPage(e,txt(d['page'],200)); out=[]
  for row in w.get_history():
   if len(row)==5:
    version,t,author,comment,ipnr=row
   elif len(row)==4:
    version,t,author,comment=row
   else:
    raise ValueError('unsupported wiki history row')
   out.append({'version':version,'time':calendar.timegm(t.utctimetuple())*1000000+t.microsecond,'author':author,'comment':comment})
   if len(out)>=100: break
  return {'history':out}
 if op=='wiki_update':
  w=WikiPage(e,txt(d['page'],200)); current=w.version if w.exists else 0
  if current!=int(d['expected_version']): raise ValueError('stale wiki revision')
  w.text=txt(d['text'],50000); w.save(os.environ.get('TRAC_MCP_AUTHOR','MCP'),txt(d.get('comment','Updated through MCP'),1000))
  w=WikiPage(e,w.name); return {'page':w.name,'version':w.version,'text':w.text,'author':w.author,'comment':w.comment}
 if op=='wiki_delete':
  require_delete(d)
  page=txt(d['page'],200)
  key='mcp-wiki-delete:%s:%s'%(d['environment'],txt(d['idempotency_key'],128)); old=idem(e,key)
  if old: return {'page':page,'deleted':True,'duplicate':True}
  w=WikiPage(e,page)
  if not w.exists: raise ValueError('wiki page not found')
  if w.version!=int(d['expected_version']): raise ValueError('stale wiki revision')
  w.delete(); e.db_transaction('INSERT INTO system (name,value) VALUES (%s,%s)',(key,page))
  return {'page':page,'deleted':True,'duplicate':False}
 raise ValueError('unknown operation')
def main():
 try: os.unlink(SOCKET)
 except OSError: pass
 s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.bind(SOCKET)
 if SOCKET_GROUP:
  try: gid=int(SOCKET_GROUP)
  except ValueError: gid=grp.getgrnam(SOCKET_GROUP).gr_gid
  os.chown(SOCKET,-1,gid)
 os.chmod(SOCKET,0o660); s.listen(16)
 while True:
  c,_=s.accept(); c.settimeout(10)
  try:
   raw=recv_request(c)
   request=json.loads(raw); authorize_request(c,request)
   r={'ok':True,'result':dispatch(request)}
  except Exception as x: r={'ok':False,'error':text_type(x)}
  try: c.sendall((json.dumps(r,ensure_ascii=False)+'\n').encode('utf-8'))
  finally: c.close()
if __name__=='__main__': main()
