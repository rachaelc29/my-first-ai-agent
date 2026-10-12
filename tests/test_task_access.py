import unittest
from tools.check_feishu_task_access import probe, SafeError


class FakeCRM:
    def __init__(self, duplicate=False, mismatch=False):
        self.calls=[];self.duplicate=duplicate;self.mismatch=mismatch
    def path(self, resource):return 'bitable/v1/apps/mock/tables/tblMock/'+resource
    def call(self,path,method):
        self.calls.append((path,method))
        if '/records?' in path:
            row={'fields':{'名字':'B','飞书任务ID':'mock-guid'}}
            return {'data':{'items':[row,row] if self.duplicate else [row]}}
        return {'data':{'task':{'guid':'wrong-guid' if self.mismatch else 'mock-guid','summary':'ignored mock content'}}}


class TaskAccessTests(unittest.TestCase):
    def test_read_only_probe(self):
        crm=FakeCRM();result=probe(crm,'B')
        self.assertEqual(result['task_read'],'passed')
        self.assertEqual(result['task_write'],'not_tested')
        self.assertTrue(all(method=='GET' for _,method in crm.calls))
        self.assertNotIn('mock-guid',str(result))
        self.assertIn('field_names=',crm.calls[0][0])
    def test_duplicate_name_stops_before_task(self):
        crm=FakeCRM(duplicate=True)
        with self.assertRaises(SafeError):probe(crm,'B')
        self.assertEqual(len(crm.calls),1)
    def test_task_identity_mismatch_stops(self):
        with self.assertRaises(SafeError):probe(FakeCRM(mismatch=True),'B')
    def test_missing_name_stops(self):
        crm=FakeCRM()
        with self.assertRaises(SafeError):probe(crm,'C')
        self.assertEqual(len(crm.calls),1)
