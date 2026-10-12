import io
import ssl
import unittest
import urllib.error
from unittest.mock import patch, Mock
from crm_sync.feishu import FeishuTestCRM
from crm_sync.model import Conflict, Uncertain


class FeishuErrorTests(unittest.TestCase):
    def client(self):
        client=FeishuTestCRM.__new__(FeishuTestCRM)
        client.token='mock-sensitive-token'
        return client
    def failure(self,error,path='task/v2/tasks/mock',method='GET'):
        opener=Mock();opener.open.side_effect=error
        with patch('crm_sync.feishu.urllib.request.build_opener',return_value=opener):
            with self.assertRaises((Conflict,Uncertain)) as caught:
                self.client().call(path,method)
        result=str(caught.exception)
        self.assertNotIn('mock-sensitive-token',result)
        self.assertNotIn('mock-error-private-detail',result)
        return result
    def test_http_status_and_stage_without_body(self):
        error=urllib.error.HTTPError('https://mock.invalid',403,'mock-error-private-detail',{},io.BytesIO(b'mock-error-private-detail'))
        self.assertEqual(self.failure(error),'task API HTTP status 403')
    def test_certificate_diagnosis(self):
        error=urllib.error.URLError(ssl.SSLCertVerificationError('mock-error-private-detail'))
        self.assertIn('SSL certificate verification failed',self.failure(error))
    def test_authentication_stage(self):
        error=urllib.error.URLError(TimeoutError('mock-error-private-detail'))
        self.assertIn('authentication unavailable',self.failure(error,'auth/v3/tenant_access_token/internal','POST'))
    def test_write_failure_still_uncertain(self):
        error=urllib.error.URLError(TimeoutError('mock-error-private-detail'))
        self.assertIn('write result unknown',self.failure(error,method='PATCH'))
    def test_api_code_only(self):
        response=Mock()
        response.read.return_value=b'{"code":99991672,"msg":"mock-error-private-detail"}'
        context=Mock();context.__enter__=Mock(return_value=response);context.__exit__=Mock(return_value=False)
        opener=Mock();opener.open.return_value=context
        with patch('crm_sync.feishu.urllib.request.build_opener',return_value=opener):
            with self.assertRaises(Conflict) as caught:self.client().call('task/v2/tasks/mock','GET')
        self.assertIn('99991672',str(caught.exception))
        self.assertNotIn('mock-error-private-detail',str(caught.exception))
