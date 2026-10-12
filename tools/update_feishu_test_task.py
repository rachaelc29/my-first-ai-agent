"""One confirmed update of an existing fictional task. No cloud deployment."""
import getpass
import json
from datetime import datetime, date, time, timezone
from pathlib import Path
import sys
import urllib.parse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from crm_sync.feishu import FeishuTestCRM
from crm_sync.model import Conflict, Uncertain
from crm_sync.oauth import authorize, UPDATE_SCOPES
from followup.parser import parse, ZONE
from tools.find_test_record import pages, SafeError
from tools.check_feishu_task_access import text


def select_record(crm,name):
    def call(path,**kwargs):return crm.call(path,'GET')
    records=pages(crm.path('records'),None,call,
                  {'field_names':json.dumps(['名字','飞书任务ID'],ensure_ascii=False)})
    matches=[r for r in records if text(r.get('fields',{}).get('名字',''))==name]
    if len(matches)!=1 or not matches[0].get('record_id'):
        raise Conflict('fictional customer must match exactly one record')
    return matches[0]['record_id']


def read_record(crm,record_id):
    record=crm.call(crm.path('records/'+urllib.parse.quote(record_id,safe='')),'GET')['data']['record']
    if record.get('record_id')!=record_id:raise Conflict('record identity mismatch')
    fields=record['fields']
    return {'name':text(fields.get('名字','')),'plan':text(fields.get('下次follow','')),
            'task_id':text(fields.get('飞书任务ID','')),'anchor':fields.get('跟进计划记录时间')}


def proposed_task(record,*,today):
    anchor=record['anchor']
    if anchor:
        if not isinstance(anchor,(int,float)):raise Conflict('invalid anchor')
        anchor=datetime.fromtimestamp(anchor/1000,ZONE).date()
    else:anchor=None
    result=parse(record['plan'],anchor=anchor,today=today)
    # This first real update validates only explicit YYYY-MM-DD dates.
    if result['status']!='proposed' or result['kind']!='exact' or not result['action_text']:
        raise Conflict('only a future explicit date and nonempty action are enabled for this test')
    if not record['name'] or not record['task_id']:
        raise Conflict('customer name or linked task ID missing')
    due=date.fromisoformat(result['proposed_reminder_date'])
    timestamp=int(datetime.combine(due,time.min,timezone.utc).timestamp()*1000)
    return {'summary':'【'+record['name']+'】'+result['action_text'],
            'due':{'timestamp':str(timestamp),'is_all_day':True}}


def read_task(api,guid):
    task=api('task/v2/tasks/'+urllib.parse.quote(guid,safe='')+'?user_id_type=open_id','GET')['data']['task']
    if task.get('guid')!=guid:raise Conflict('task identity mismatch')
    if str(task.get('completed_at',0) or 0)!='0':raise Conflict('completed task cannot be updated by this test')
    return task


def update(crm,api,record_id,snapshot,task_snapshot,desired):
    if read_record(crm,record_id)!=snapshot:
        raise Conflict('test plan changed after preview; no update')
    guid=snapshot['task_id']
    current=read_task(api,guid)
    watch=('guid','summary','description','due','completed_at','updated_at','members','tasklists')
    if any(current.get(k)!=task_snapshot.get(k) for k in watch):
        raise Conflict('task changed after preview; no update')
    # Only title/date; no creation, deletion, completion, membership or CRM PUT.
    api('task/v2/tasks/'+urllib.parse.quote(guid,safe='')+'?user_id_type=open_id','PATCH',
        {'task':desired,'update_fields':['summary','due']})
    actual=read_task(api,guid)
    due=actual.get('due') or {}
    if actual.get('summary')!=desired['summary'] or str(due.get('timestamp'))!=desired['due']['timestamp'] or due.get('is_all_day') is not True:
        raise Uncertain('task update verification incomplete; inspect before retry')
    if read_record(crm,record_id)!=snapshot:
        raise Uncertain('test plan changed during update; review conflict before further sync')
    return {'task_update':'passed','same_task_id':'passed','crm_write':'not_performed'}


def main():
    root=Path.home()/'Library/Application Support/PropertyCRMSync'
    config=json.loads((root/'test-config.json').read_text())
    print('只更新独立测试表中指定虚构客户的原任务；不写客户表，不创建任务。')
    name=input('虚构客户名字（例如 C，与表中完全一致）: ').strip()
    if not name:raise Conflict('fictional customer required')
    secret=getpass.getpass('独立测试应用 App Secret（输入隐藏）: ')
    if not secret:raise Conflict('credential missing')
    crm=FeishuTestCRM(config,secret)
    record_id=select_record(crm,name)
    snapshot=read_record(crm,record_id)
    if snapshot['name']!=name:raise Conflict('customer changed during selection')
    desired=proposed_task(snapshot,today=datetime.now(ZONE).date())
    access=authorize(config['test_app_id'],secret,scopes=UPDATE_SCOPES)
    def api(path,method,payload=None):
        if not path.startswith('task/v2/tasks/') or method not in ('GET','PATCH'):
            raise Conflict('test endpoint not permitted')
        previous=crm.token
        try:
            crm.token=access
            return crm.call(path,method,payload)
        finally:crm.token=previous
    existing=read_task(api,snapshot['task_id'])
    print('仅在本机预览虚构任务；不要用于真实客户：')
    print('原任务标题：'+str(existing.get('summary','')))
    print('更新后标题：'+desired['summary'])
    print('更新后日期：'+datetime.fromtimestamp(int(desired['due']['timestamp'])/1000,timezone.utc).date().isoformat()+'（全天）')
    print('任务ID保持不变；不修改负责人、关注人、描述或完成状态。')
    if input('确认本次测试更新？输入 YES: ').strip()!='YES':
        print('已取消，没有更新任务。');return
    print(json.dumps(update(crm,api,record_id,snapshot,existing,desired),ensure_ascii=False))
    print('测试结束，未保存应用密钥或用户令牌。')


if __name__=='__main__':
    try:main()
    except (Conflict,Uncertain,SafeError) as exc:
        print('测试暂停：'+str(exc));raise SystemExit(1)
    except KeyboardInterrupt:
        print('\n已取消。');raise SystemExit(1)
    except Exception:
        print('测试暂停；敏感详情未输出。');raise SystemExit(1)
