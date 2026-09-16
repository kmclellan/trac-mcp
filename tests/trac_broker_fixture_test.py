#!/usr/bin/python2
from __future__ import print_function
import base64, os, sys, uuid
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,ROOT)
import trac_broker as b
from trac.env import Environment
from trac.wiki.model import WikiPage
from trac.attachment import Attachment

def denied(fn, text):
 try: fn()
 except Exception as e:
  assert text in str(e), (text,str(e)); return
 raise AssertionError('expected denial: '+text)

def main():
 path=sys.argv[1] if len(sys.argv)>1 else '/srv/trac/test'; b.ENVS['fixture']=path; e=Environment(path)
 suffix=uuid.uuid4().hex[:10]; page='McpFixture'+suffix
 w=WikiPage(e,page); w.text='alpha searchable'; w.save('Fixture','create','127.0.0.1')
 assert page in b.dispatch({'op':'wiki_list','environment':'fixture','prefix':page})['pages']
 assert b.dispatch({'op':'wiki_search','environment':'fixture','query':'searchable'})['results']
 payload=base64.b64encode('fixture bytes')
 up={'op':'attachment_upload','environment':'fixture','realm':'wiki','resource':page,'filename':'a.txt','expected_revision':1,'content_base64':payload,'idempotency_key':'upload-'+suffix}
 assert not b.dispatch(up)['duplicate']; assert b.dispatch(up)['duplicate']
 got=b.dispatch({'op':'attachment_get','environment':'fixture','realm':'wiki','resource':page,'filename':'a.txt','max_bytes':100})
 assert got['content_base64']==payload
 denied(lambda:b.dispatch({'op':'attachment_get','environment':'fixture','realm':'wiki','resource':page,'filename':'a.txt','max_bytes':2}),'too large')
 denied(lambda:b.dispatch({'op':'wiki_list','environment':'wrong'}),'environment not allowed')
 kind='component'; name='FixtureComponent'+suffix; key='item-'+suffix
 create={'op':'project_item_create','environment':'fixture','kind':kind,'name':name,'description':'one','owner':'Fixture','idempotency_key':key}
 assert not b.dispatch(create)['duplicate']; assert b.dispatch(create)['duplicate']
 cur=b.dispatch({'op':'project_item_get','environment':'fixture','kind':kind,'name':name})
 b.dispatch({'op':'project_item_update','environment':'fixture','kind':kind,'name':name,'expected':cur,'description':'two'})
 denied(lambda:b.dispatch({'op':'project_item_update','environment':'fixture','kind':kind,'name':name,'expected':cur,'description':'three'}),'stale project item')
 print('PASS trac broker fixture expansion')
if __name__=='__main__': main()
