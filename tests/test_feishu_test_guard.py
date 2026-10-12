import unittest
from unittest.mock import patch
from crm_sync.feishu import FeishuTestCRM
from crm_sync.model import Conflict

class GuardTests(unittest.TestCase):
    def config(self):return {'mode':'feishu-test','test_only_ack':'ONLY_FICTIONAL_TEST_DATA','test_app_token':'fictional-base','test_table_id':'fictional-table','test_app_id':'fictional-app','allowed_test_record_ids':['fictional-record']}
    def call(self,path,method,payload=None):
        if path.startswith('auth/'):return {'tenant_access_token':'fictional-token'}
        if path.endswith('/tables?page_size=100'):return {'data':{'items':[{'table_id':'fictional-table','name':'CRM-SYNC-TEST'}]}}
        if '/fields?' in path:
            from crm_sync.feishu import EXPECTED_TYPES
            return {'data':{'items':[{'field_name':k,'type':v} for k,v in EXPECTED_TYPES.items()]}}
        return {'data':{'app':{'name':'CRM-SYNC-TEST'}}}
    def test_production_base_rejected(self):
        def call(adapter,path,method,payload=None):
            if path.startswith('auth/'):return {'tenant_access_token':'mock'}
            return {'data':{'app':{'name':'正式客户表'}}}
        with patch.object(FeishuTestCRM,'call',call):
            with self.assertRaises(Conflict):FeishuTestCRM(self.config(),'mock')
    def test_missing_ack_rejected_before_network(self):
        config=self.config();config.pop('test_only_ack')
        with patch.object(FeishuTestCRM,'call') as call:
            with self.assertRaises(Conflict):FeishuTestCRM(config,'mock')
            call.assert_not_called()
    def test_record_allowlist_and_field_whitelist(self):
        with patch.object(FeishuTestCRM,'call',lambda obj,*a,**k:self.call(*a,**k)):
            adapter=FeishuTestCRM(self.config(),'mock')
            with self.assertRaises(Conflict):adapter.get('production-record')
            with self.assertRaises(Conflict):adapter.update('fictional-record',{'budget':1},{})
    def test_empty_allowlist_rejected(self):
        config=self.config();config['allowed_test_record_ids']=[]
        with patch.object(FeishuTestCRM,'call',lambda obj,*a,**k:self.call(*a,**k)):
            with self.assertRaises(Conflict):FeishuTestCRM(config,'mock')
