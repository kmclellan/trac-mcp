#!/usr/bin/python2
from __future__ import print_function
import base64, imp, os, socket, sys, uuid
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BROKER_PATH=os.path.join(ROOT,'legacy','trac_broker_py2.py')
with open(BROKER_PATH,'r') as broker_source:
 b=imp.load_module('trac_broker',broker_source,BROKER_PATH,
                   ('.py','r',imp.PY_SOURCE))
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
 original_admin_uids=set(b.ADMIN_UIDS)
 left,right=socket.socketpair()
 try:
  assert b.peer_uid(right)==os.getuid()
  b.ADMIN_UIDS=set()
  b.authorize_request(right,{'op':'ticket_get'})
  denied(lambda:b.authorize_request(right,{'op':'ticket_delete'}),
         'local admin operations are disabled')
  b.ADMIN_UIDS=set((os.getuid()+1,))
  denied(lambda:b.authorize_request(right,{'op':'ticket_delete'}),
         'local admin operation denied')
  b.ADMIN_UIDS=set((os.getuid(),))
  b.authorize_request(right,{'op':'ticket_delete'})
  b.ADMIN_UIDS=original_admin_uids
  left.sendall(b'{"chunk":'); left.sendall(b'"ok"}'); left.shutdown(socket.SHUT_WR)
  assert b.recv_request(right)==b'{"chunk":"ok"}'
 finally:
  b.ADMIN_UIDS=original_admin_uids
  left.close(); right.close()
 old_max=b.MAX; b.MAX=8
 left,right=socket.socketpair()
 try:
  left.sendall(b'123456789'); left.shutdown(socket.SHUT_WR)
  denied(lambda:b.recv_request(right),'request too large')
 finally:
  b.MAX=old_max; left.close(); right.close()

 suffix=uuid.uuid4().hex[:10]; page='McpFixture'+suffix
 w=WikiPage(e,page); w.text='alpha searchable'; w.save('Fixture','create')
 assert page in b.dispatch({'op':'wiki_list','environment':'fixture','prefix':page})['pages']
 assert b.dispatch({'op':'wiki_search','environment':'fixture','query':'searchable'})['results']
 assert b.dispatch({'op':'wiki_history','environment':'fixture','page':page})['history']
 payload=base64.b64encode(b'fixture bytes').decode('ascii')
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

 # Benign/read-only expansion.
 assert b.dispatch({'op':'ping','environment':'fixture'})['trac_version']
 assert b.dispatch({'op':'server_time','environment':'fixture'})['unix_timestamp'] > 0
 assert b.dispatch({'op':'ticket_fields','environment':'fixture'})['fields']
 assert any(x['name']==name for x in b.dispatch({'op':'project_item_list','environment':'fixture','kind':'component'})['items'])
 assert b.dispatch({'op':'enum_list','environment':'fixture','kind':'priority'})['items']
 assert b.dispatch({'op':'enum_list','environment':'fixture','kind':'status'})['items']
 assert any(x['page']==page for x in b.dispatch({'op':'wiki_recent_changes','environment':'fixture','limit':50})['changes'])

 # SentinelX-only enum administration.
 enum_name='fixture-priority-'+suffix
 enum_create={'op':'enum_create','environment':'fixture','kind':'priority','name':enum_name,
              'description':'fixture enum','idempotency_key':'enum-create-'+suffix}
 enum_result=b.dispatch(enum_create)
 assert not enum_result['duplicate']
 assert b.dispatch(enum_create)['duplicate']
 enum_current=[x for x in b.dispatch({'op':'enum_list','environment':'fixture','kind':'priority'})['items'] if x['name']==enum_name][0]
 enum_delete={'op':'enum_delete','environment':'fixture','kind':'priority','name':enum_name,
              'expected':enum_current,'confirm':'DELETE','idempotency_key':'enum-delete-'+suffix}
 assert not b.dispatch(enum_delete)['duplicate']
 assert b.dispatch(enum_delete)['duplicate']

 # SentinelX-only batch ticket operations and workflow discovery.
 batch_create={'op':'ticket_batch_create','environment':'fixture','idempotency_key':'batch-create-'+suffix,
               'items':[{'summary':'Fixture batch A '+suffix,'description':'A'},
                        {'summary':'Fixture batch B '+suffix,'description':'B'},
                        {'summary':'Fixture batch assigned '+suffix,'description':'C',
                         'action':'create_and_assign',
                         'action_fields':{'action_create_and_assign_reassign_owner':'FixtureOwner'}}]}
 created=b.dispatch(batch_create)
 assert created['succeeded']==3 and not created['failed']
 assert all(x['duplicate'] for x in b.dispatch(batch_create)['created'])
 first=created['created'][0]['ticket']; second=created['created'][1]['ticket']
 assigned=created['created'][2]['ticket']
 assert assigned['status']=='assigned' and assigned['owner']=='FixtureOwner'
 assert first['status']=='new' and first['reporter']=='MCP'
 assert second['status']=='new' and second['reporter']=='MCP'
 actions=b.dispatch({'op':'ticket_actions','environment':'fixture','ticket_id':first['id']})['actions']
 assert actions and all('name' in x and 'input_fields' in x for x in actions)
 action_names=set(x['name'] for x in actions)
 assert set(('resolve','reassign','accept')).issubset(action_names)
 denied(lambda:b.dispatch({'op':'ticket_update','environment':'fixture',
                           'ticket_id':first['id'],'expected_changed':first['changed'],
                           'fields':{'status':'closed'},
                           'comment':'direct status bypass'}),
        'status/resolution require workflow action')

 second_actions=b.dispatch({'op':'ticket_actions','environment':'fixture','ticket_id':second['id']})['actions']
 assert any(x['name']=='accept' for x in second_actions)
 action_update={'op':'ticket_update','environment':'fixture','ticket_id':second['id'],
                'expected_changed':second['changed'],'action':'accept',
                'fields':{},'comment':'accept through workflow',
                'idempotency_key':'action-update-'+suffix}
 action_result=b.dispatch(action_update)
 assert action_result['ticket']['status']=='accepted'
 assert action_result['action']=='accept'
 assert b.dispatch(action_update)['duplicate']
 second=action_result['ticket']

 resolved_create=b.dispatch({'op':'ticket_create','environment':'fixture',
                             'summary':'Fixture resolve '+suffix,
                             'idempotency_key':'resolve-create-'+suffix})
 resolved=resolved_create['ticket']
 resolve_action=[x for x in b.dispatch({'op':'ticket_actions','environment':'fixture',
                                       'ticket_id':resolved['id']})['actions']
                 if x['name']=='resolve'][0]
 resolution_fields=[x for x in resolve_action['input_fields'] if 'resolution' in x]
 assert resolution_fields
 resolve_update={'op':'ticket_update','environment':'fixture','ticket_id':resolved['id'],
                 'expected_changed':resolved['changed'],'action':'resolve',
                 'action_fields':{resolution_fields[0]:'fixed'},'fields':{},
                 'comment':'resolve through workflow',
                 'idempotency_key':'resolve-update-'+suffix}
 resolved_result=b.dispatch(resolve_update)
 assert resolved_result['ticket']['status']=='closed'
 assert resolved_result['ticket']['resolution']=='fixed'
 assert resolved_result['action']=='resolve'
 assert b.dispatch(resolve_update)['duplicate']
 resolved=resolved_result['ticket']

 direct_delete={'op':'ticket_delete','environment':'fixture',
                'ticket_id':resolved['id'],'expected_changed':resolved['changed'],
                'confirm':'DELETE','idempotency_key':'direct-delete-'+suffix}
 assert not b.dispatch(direct_delete)['duplicate']
 assert b.dispatch(direct_delete)['duplicate']

 batch_update={'op':'ticket_batch_update','environment':'fixture','idempotency_key':'batch-update-'+suffix,
               'items':[{'ticket_id':first['id'],'expected_changed':first['changed'],
                         'fields':{'summary':'Fixture batch A updated '+suffix},
                         'comment':'fixture update'}]}
 updated=b.dispatch(batch_update)
 assert updated['succeeded']==1 and not updated['failed']
 assert b.dispatch(batch_update)['updated'][0]['duplicate']
 first_updated=updated['updated'][0]['ticket']

 # SentinelX-only guarded attachment deletion.
 attachment_delete={'op':'attachment_delete','environment':'fixture','realm':'wiki',
                    'resource':page,'filename':'a.txt','expected_revision':1,
                    'confirm':'DELETE','idempotency_key':'attachment-delete-'+suffix}
 assert not b.dispatch(attachment_delete)['duplicate']
 assert b.dispatch(attachment_delete)['duplicate']

 # SentinelX-only project item and wiki deletion.
 milestone_name='FixtureMilestone'+suffix
 due_us=1893456000000000
 milestone_create={'op':'project_item_create','environment':'fixture','kind':'milestone',
                   'name':milestone_name,'description':'dated fixture',
                   'due':due_us,'idempotency_key':'milestone-create-'+suffix}
 milestone=b.dispatch(milestone_create)
 assert milestone['due']==due_us
 listed=b.dispatch({'op':'project_item_list','environment':'fixture','kind':'milestone'})['items']
 assert any(x['name']==milestone_name and x['due']==due_us for x in listed)
 milestone_current=b.dispatch({'op':'project_item_get','environment':'fixture','kind':'milestone','name':milestone_name})
 due_us_2=1893542400000000
 milestone_updated=b.dispatch({'op':'project_item_update','environment':'fixture','kind':'milestone',
                               'name':milestone_name,'expected':milestone_current,
                               'due':due_us_2,'description':'dated fixture updated'})
 assert milestone_updated['due']==due_us_2
 denied(lambda:b.dispatch({'op':'project_item_update','environment':'fixture','kind':'milestone',
                           'name':milestone_name,'expected':milestone_current,
                           'due':due_us}),'stale project item')
 milestone_cleared=b.dispatch({'op':'project_item_update','environment':'fixture','kind':'milestone',
                              'name':milestone_name,'expected':milestone_updated,'due':None})
 assert milestone_cleared['due'] is None

 current_item=b.dispatch({'op':'project_item_get','environment':'fixture','kind':kind,'name':name})
 project_delete={'op':'project_item_delete','environment':'fixture','kind':kind,'name':name,
                 'expected':current_item,'confirm':'DELETE','idempotency_key':'item-delete-'+suffix}
 assert not b.dispatch(project_delete)['duplicate']
 assert b.dispatch(project_delete)['duplicate']
 wiki_delete={'op':'wiki_delete','environment':'fixture','page':page,'expected_version':1,
              'confirm':'DELETE','idempotency_key':'wiki-delete-'+suffix}
 assert not b.dispatch(wiki_delete)['duplicate']
 assert b.dispatch(wiki_delete)['duplicate']

 # SentinelX-only batch deletion and replay.
 batch_delete={'op':'ticket_batch_delete','environment':'fixture','confirm':'DELETE',
               'idempotency_key':'batch-delete-'+suffix,
               'items':[{'ticket_id':first_updated['id'],'expected_changed':first_updated['changed']},
                        {'ticket_id':second['id'],'expected_changed':second['changed']},
                        {'ticket_id':assigned['id'],'expected_changed':assigned['changed']}]}
 deleted=b.dispatch(batch_delete)
 assert deleted['succeeded']==3 and not deleted['failed']
 assert all(x['duplicate'] for x in b.dispatch(batch_delete)['deleted'])

 print('PASS trac broker fixture expansion')
if __name__=='__main__': main()
