from copy import deepcopy
from datetime import date, datetime, timezone
import unittest
from tools.update_feishu_test_task import proposed_task, update
from crm_sync.model import Conflict, Uncertain
from crm_sync.oauth import authorization_url, UPDATE_SCOPES


class UpdateTaskTests(unittest.TestCase):
    def record(self):return {'name':'C','plan':'2026-12-22，修改后的虚构跟进内容','task_id':'mock-guid','anchor':None}
    def setup_clients(self):
        record=self.record();fields={'名字':record['name'],'下次follow':record['plan'],'飞书任务ID':record['task_id']}
        class CRM:
            def path(self,suffix):return 'bitable/mock/'+suffix
            def call(self,path,method):
                if method!='GET':raise AssertionError('CRM writes forbidden')
                return {'data':{'record':{'record_id':'recMock','fields':deepcopy(fields)}}}
        desired=proposed_task(record,today=date(2026,10,13))
        task={'guid':'mock-guid','summary':'旧虚构标题','due':{'timestamp':'0','is_all_day':True},'completed_at':'0','updated_at':'old','members':[{'id':'mock-user','role':'assignee'}],'description':'保留描述'}
        calls=[]
        def api(path,method,payload=None):
            calls.append((method,payload))
            if method=='PATCH':
                self.assertEqual(set(payload['task']),{'summary','due'})
                self.assertEqual(payload['update_fields'],['summary','due'])
                task.update(deepcopy(payload['task']))
            return {'data':{'task':deepcopy(task)}}
        return CRM(),api,record,desired,task,calls,fields
    def test_update_same_task_without_crm_or_membership_writes(self):
        crm,api,record,desired,task,calls,fields=self.setup_clients()
        result=update(crm,api,'recMock',record,deepcopy(task),desired)
        self.assertEqual(result['task_update'],'passed')
        self.assertEqual(task['guid'],'mock-guid')
        self.assertEqual(task['members'],[{'id':'mock-user','role':'assignee'}])
        self.assertEqual(task['description'],'保留描述')
        self.assertEqual([c[0] for c in calls],['GET','PATCH','GET'])
    def test_crm_change_after_preview_prevents_patch(self):
        crm,api,record,desired,task,calls,fields=self.setup_clients()
        fields['下次follow']='2026-12-23，另一虚构计划'
        with self.assertRaises(Conflict):update(crm,api,'recMock',record,deepcopy(task),desired)
        self.assertEqual(calls,[])
    def test_task_change_after_preview_prevents_patch(self):
        crm,api,record,desired,task,calls,fields=self.setup_clients()
        snapshot=deepcopy(task);task['summary']='用户又修改了任务'
        with self.assertRaises(Conflict):update(crm,api,'recMock',record,snapshot,desired)
        self.assertEqual([c[0] for c in calls],['GET'])
    def test_completed_task_is_not_patched(self):
        crm,api,record,desired,task,calls,fields=self.setup_clients();task['completed_at']='1234'
        with self.assertRaises(Conflict):update(crm,api,'recMock',record,deepcopy(task),desired)
        self.assertFalse(any(c[0]=='PATCH' for c in calls))
    def test_fuzzy_or_empty_action_not_enabled(self):
        for plan in ['2026年12月初，联系','2026-12-22','下周五，联系']:
            record=self.record();record['plan']=plan
            with self.subTest(plan=plan),self.assertRaises(Conflict):proposed_task(record,today=date(2026,10,13))
    def test_all_day_date_is_timezone_independent(self):
        desired=proposed_task(self.record(),today=date(2026,10,13))
        self.assertEqual(desired['summary'],'【C】修改后的虚构跟进内容')
        timestamp=int(desired['due']['timestamp'])/1000
        self.assertEqual(datetime.fromtimestamp(timestamp,timezone.utc).isoformat(),'2026-12-22T00:00:00+00:00')
    def test_permission_is_read_and_writeonly(self):
        from urllib.parse import urlsplit,parse_qs
        params=parse_qs(urlsplit(authorization_url('cli_mock','state','v'*43,UPDATE_SCOPES)).query)
        self.assertEqual(params['scope'],['task:task:read task:task:writeonly'])
    def test_task_guid_mismatch_prevents_patch(self):
        crm,api,record,desired,task,calls,fields=self.setup_clients();task['guid']='wrong'
        with self.assertRaises(Conflict):update(crm,api,'recMock',record,deepcopy(task),desired)
        self.assertFalse(any(c[0]=='PATCH' for c in calls))
