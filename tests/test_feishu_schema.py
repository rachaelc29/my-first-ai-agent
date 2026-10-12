import unittest
from tools.verify_feishu_schema import verify, SafeFailure

CONFIG={'FEISHU_APP_ID':'mock-id','FEISHU_APP_SECRET':'mock-secret','FEISHU_APP_TOKEN':'mock-base','FEISHU_TABLE_ID':'mock-table'}

class SchemaTests(unittest.TestCase):
    def test_pagination_and_no_records_or_write(self):
        paths=[]
        def call(path,**kwargs):
            paths.append(path)
            if len(paths)==1:
                self.assertEqual(path,'auth/v3/tenant_access_token/internal')
                return {'tenant_access_token':'mock-token'}
            self.assertNotIn('payload',kwargs)
            self.assertIn('/fields?',path)
            self.assertNotIn('/records',path)
            return {'data':{'items':[{'field_name':'模拟字段','type':1,'ui_type':'Text','property':{'ignored':'mock-detail'}}], 'has_more':len(paths)==2, 'page_token':'next'}}
        r=verify(CONFIG,call)
        self.assertEqual(r['field_count'],2)
        self.assertEqual(len(paths),3)
        self.assertNotIn('mock-secret',str(r))
        self.assertNotIn('property',str(r))

    def test_missing_credentials_do_not_call_network(self):
        def call(*args,**kwargs):self.fail('network must not run')
        with self.assertRaises(SafeFailure):verify({},call)

    def test_missing_token_stops(self):
        with self.assertRaises(SafeFailure):verify(CONFIG,lambda *a,**k:{})

    def test_repeated_page_stops(self):
        def call(path,**kwargs):
            if path.startswith('auth/'):return {'tenant_access_token':'mock'}
            return {'data':{'items':[], 'has_more':True, 'page_token':'same'}}
        with self.assertRaises(SafeFailure):verify(CONFIG,call)

    def test_missing_page_stops(self):
        def call(path,**kwargs):
            if path.startswith('auth/'):return {'tenant_access_token':'mock'}
            return {'data':{'items':[], 'has_more':True}}
        with self.assertRaises(SafeFailure):verify(CONFIG,call)

    def test_invalid_schema_stops(self):
        def call(path,**kwargs):
            if path.startswith('auth/'):return {'tenant_access_token':'mock'}
            return {'data':{'items':[{'field_name':'模拟字段'}]}}
        with self.assertRaises(SafeFailure):verify(CONFIG,call)
