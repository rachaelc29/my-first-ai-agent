import unittest
from tools.find_test_record import find, SafeError


class FindRecordTests(unittest.TestCase):
    def call(self, path, **kwargs):
        if path.startswith('auth/'):
            return {'tenant_access_token':'mock-access'}
        if '/records?' in path:
            self.assertIn('field_names=',path)
            self.assertNotIn('payload',kwargs)
            return {'data':{'items':[{'record_id':'recMock','fields':{'名字':[{'text':'虚构测试'}]}}]}}
        if '/tables?' in path:
            return {'data':{'items':[{'table_id':'tblMock','name':'CRM-SYNC-TEST'}]}}
        return {'data':{'app':{'name':'CRM-SYNC-TEST'}}}

    def test_unique_match(self):
        self.assertEqual(find('mock','mock','mock','tblMock','虚构测试',self.call),'recMock')

    def test_other_file_stops_before_records(self):
        calls=[]
        def call(path,**kwargs):
            calls.append(path)
            if path.startswith('auth/'):
                return {'tenant_access_token':'mock-access'}
            return {'data':{'app':{'name':'非测试文件'}}}
        with self.assertRaises(SafeError):find('mock','mock','mock','tblMock','虚构测试',call)
        self.assertFalse(any('/records' in p for p in calls))

    def test_wrong_table_stops_before_records(self):
        with self.assertRaises(SafeError):find('mock','mock','mock','tblWrong','虚构测试',self.call)

    def test_absent_name_not_guessed(self):
        with self.assertRaises(SafeError):find('mock','mock','mock','tblMock','其他虚构名字',self.call)

    def test_duplicate_match_stops(self):
        def call(path,**kwargs):
            result=self.call(path,**kwargs)
            if '/records?' in path:
                result['data']['items'] *= 2
            return result
        with self.assertRaises(SafeError):find('mock','mock','mock','tblMock','虚构测试',call)
