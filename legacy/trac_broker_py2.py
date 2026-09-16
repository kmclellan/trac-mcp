#!/usr/bin/python2
# -*- coding: utf-8 -*-
from __future__ import print_function
import base64, calendar, grp, json, os, re, socket, StringIO
from trac.env import Environment
from trac.ticket.model import Ticket
from trac.ticket.query import Query
from trac.ticket.model import Component, Milestone, Priority, Type, Version
from trac.wiki.model import WikiPage
from trac.wiki.api import WikiSystem
from trac.attachment import Attachment
SOCKET=os.environ.get('TRAC_MCP_SOCKET','/run/trac-mcp/trac.sock')
ENVS=dict(x.split('=',1) for x in os.environ.get('TRAC_MCP_ENVIRONMENTS','example=/srv/trac/example').split(',') if '=' in x)
MAX=1048576

def env(name):
 if name not in ENVS: raise ValueError('environment not allowed')
 return Environment(ENVS[name])
def txt(v,n):
 if not isinstance(v,(str,unicode)): raise ValueError('text required')
 v=v.decode('utf-8') if isinstance(v,str) else v
 if len(v)>n: raise ValueError('text too long')
 return v
def changed_time(t): return getattr(t,'time_changed',t['changetime'])
def td(t):
 dt=changed_time(t); d={'id':t.id,'changed':calendar.timegm(dt.utctimetuple())*1000000+dt.microsecond}
 for k in ('summary','description','status','type','priority','milestone','component','owner','reporter','keywords','resolution'): d[k]=t[k]
 return d
def idem(e,key): return e.db_query('SELECT value FROM system WHERE name=%s',(key,))
def dispatch(d):
 op=d.get('op')
 if op=='environments': return {'environments':sorted(ENVS)}
 e=env(d.get('environment'))
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
  out={'kind':kind,'name':x.name,'description':x.description}
  if kind=='component': out['owner']=x.owner
  return out
 if op=='project_item_create':
  kind=txt(d['kind'],20); name=txt(d['name'],200); cls={'component':Component,'milestone':Milestone,'version':Version}.get(kind)
  if not cls: raise ValueError('project item kind not allowed')
  key='mcp-project-item:%s:%s'%(d['environment'],txt(d['idempotency_key'],128)); old=idem(e,key)
  if old: return {'kind':kind,'name':old[0][0],'duplicate':True}
  x=cls(e); x.name=name; x.description=txt(d.get('description',''),5000)
  if kind=='component': x.owner=txt(d.get('owner',''),200)
  x.insert(); e.db_transaction('INSERT INTO system (name,value) VALUES (%s,%s)',(key,x.name))
  return {'kind':kind,'name':x.name,'description':x.description,'duplicate':False}
 if op=='project_item_update':
  kind=txt(d['kind'],20); name=txt(d['name'],200); cls={'component':Component,'milestone':Milestone,'version':Version}.get(kind)
  if not cls: raise ValueError('project item kind not allowed')
  x=cls(e,name)
  if not x.exists: raise ValueError('project item not found')
  expected=d.get('expected') or {}
  current={'kind':kind,'name':x.name,'description':x.description}
  if kind=='component': current['owner']=x.owner
  if expected!=current: raise ValueError('stale project item')
  if 'new_name' in d: x.name=txt(d['new_name'],200)
  if 'description' in d: x.description=txt(d['description'],5000)
  if kind=='component' and 'owner' in d: x.owner=txt(d['owner'],200)
  x.update(os.environ.get('TRAC_MCP_AUTHOR','MCP')) if kind=='milestone' else x.update()
  return {'kind':kind,'name':x.name,'description':x.description}
 if op=='ticket_create':
  key='mcp-create:%s:%s'%(d['environment'],txt(d['idempotency_key'],128)); old=idem(e,key)
  if old: return {'ticket':td(Ticket(e,int(old[0][0]))),'duplicate':True}
  t=Ticket(e); t['summary']=txt(d['summary'],500); t['description']=txt(d.get('description',''),50000)
  allowed=('type','priority','milestone','component','owner','keywords','cc','version')
  for k,v in d.get('fields',{}).items():
   if k not in allowed: raise ValueError('field not allowed')
   t[k]=txt(v,1000)
  tid=t.insert(); e.db_transaction('INSERT INTO system (name,value) VALUES (%s,%s)',(key,str(tid)))
  return {'ticket':td(Ticket(e,tid)),'duplicate':False}
 if op=='ticket_update':
  t=Ticket(e,int(d['ticket_id'])); dt=changed_time(t); changed=calendar.timegm(dt.utctimetuple())*1000000+dt.microsecond
  if changed!=int(d['expected_changed']): raise ValueError('stale ticket revision')
  allowed=('summary','description','status','type','priority','milestone','component','owner','keywords','cc','version','resolution')
  fields=d.get('fields',{})
  if not fields: raise ValueError('fields required')
  for k,v in fields.items():
   if k not in allowed: raise ValueError('field not allowed')
   t[k]=txt(v,50000 if k=='description' else 1000)
  t.save_changes(os.environ.get('TRAC_MCP_AUTHOR','MCP'),txt(d.get('comment','Updated through MCP'),5000)); return {'ticket':td(Ticket(e,t.id))}
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
  if not isinstance(raw,(str,unicode)): raise ValueError('base64 content required')
  try: data=base64.b64decode(raw)
  except Exception: raise ValueError('invalid base64 content')
  if len(data)>524288: raise ValueError('attachment too large')
  a=Attachment(e,realm,resource); a.author=os.environ.get('TRAC_MCP_AUTHOR','MCP'); a.description=txt(d.get('description','Uploaded through MCP'),1000)
  a.insert(filename,StringIO.StringIO(data),len(data)); e.db_transaction('INSERT INTO system (name,value) VALUES (%s,%s)',(key,a.filename))
  return {'realm':realm,'resource':resource,'filename':a.filename,'size':a.size,'duplicate':False}
 if op=='attachment_get':
  realm=txt(d['realm'],20); resource=txt(d['resource'],200); filename=txt(d['filename'],255)
  if realm not in ('ticket','wiki'): raise ValueError('attachment realm not allowed')
  a=Attachment(e,realm,resource,filename); max_bytes=min(max(int(d.get('max_bytes',1048576)),1),2097152)
  if a.size>max_bytes: raise ValueError('attachment too large')
  f=a.open(); data=f.read(max_bytes+1); f.close()
  if len(data)>max_bytes: raise ValueError('attachment too large')
  return {'realm':realm,'resource':resource,'filename':a.filename,'size':a.size,'author':a.author,'description':a.description,'content_base64':base64.b64encode(data).decode('ascii')}
 if op=='wiki_get':
  w=WikiPage(e,txt(d['page'],200))
  if not w.exists: raise ValueError('wiki page not found')
  return {'page':w.name,'version':w.version,'text':w.text,'author':w.author,'comment':w.comment}
 if op=='wiki_history':
  w=WikiPage(e,txt(d['page'],200)); out=[]
  for version,t,author,comment,ipnr in w.get_history():
   out.append({'version':version,'time':calendar.timegm(t.utctimetuple())*1000000+t.microsecond,'author':author,'comment':comment})
   if len(out)>=100: break
  return {'history':out}
 if op=='wiki_update':
  w=WikiPage(e,txt(d['page'],200)); current=w.version if w.exists else 0
  if current!=int(d['expected_version']): raise ValueError('stale wiki revision')
  w.text=txt(d['text'],50000); w.save(os.environ.get('TRAC_MCP_AUTHOR','MCP'),txt(d.get('comment','Updated through MCP'),1000))
  w=WikiPage(e,w.name); return {'page':w.name,'version':w.version,'text':w.text,'author':w.author,'comment':w.comment}
 raise ValueError('unknown operation')
def main():
 try: os.unlink(SOCKET)
 except OSError: pass
 s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.bind(SOCKET); os.chown(SOCKET,-1,grp.getgrnam('mcp-gateway').gr_gid); os.chmod(SOCKET,0660); s.listen(16)
 while True:
  c,_=s.accept()
  try:
   raw=c.recv(MAX+1)
   if len(raw)>MAX: raise ValueError('request too large')
   r={'ok':True,'result':dispatch(json.loads(raw))}
  except Exception as x: r={'ok':False,'error':unicode(x)}
  try: c.sendall((json.dumps(r,ensure_ascii=False)+'\n').encode('utf-8'))
  finally: c.close()
if __name__=='__main__': main()
