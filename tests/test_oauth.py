import unittest
from urllib.parse import urlsplit, parse_qs
from crm_sync.oauth import authorization_url, parse_callback, SCOPES
from crm_sync.model import Conflict
from tools.check_feishu_task_access import probe


class OAuthTests(unittest.TestCase):
    def test_pkce_rfc_vector_and_no_secret_in_authorization_url(self):
        verifier='dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'
        url=authorization_url('cli_mock','mock-state',verifier)
        parsed=urlsplit(url);params=parse_qs(parsed.query)
        self.assertEqual(parsed.scheme,'https')
        self.assertEqual(parsed.hostname,'accounts.feishu.cn')
        self.assertEqual(params['code_challenge'],['E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM'])
        self.assertEqual(params['code_challenge_method'],['S256'])
        self.assertEqual(params['scope'],['task:task:read'])
        self.assertNotIn(verifier,url)
        self.assertNotIn('client_secret',params)
    def test_valid_callback(self):
        self.assertEqual(parse_callback('/callback?state=mock-state&code=mock-code','mock-state'),'mock-code')
    def test_wrong_state_rejected(self):
        with self.assertRaises(Conflict):parse_callback('/callback?state=wrong&code=mock-code','mock-state')
    def test_missing_state_rejected(self):
        with self.assertRaises(Conflict):parse_callback('/callback?code=mock-code','mock-state')
    def test_duplicate_state_or_code_rejected(self):
        for path in ['/callback?state=s&state=s&code=c','/callback?state=s&code=c&code=d']:
            with self.subTest(path=path),self.assertRaises(Conflict):parse_callback(path,'s')
    def test_other_path_rejected(self):
        with self.assertRaises(Conflict):parse_callback('/other?state=s&code=c','s')
    def test_user_denial_is_not_token_exchange(self):
        with self.assertRaises(Conflict):parse_callback('/callback?state=s&error=access_denied','s')
    def test_missing_or_overlong_code_rejected(self):
        for path in ['/callback?state=s','/callback?state=s&code=','/callback?state=s&code='+'a'*8193]:
            with self.assertRaises(Conflict):parse_callback(path,'s')
    def test_user_probe_uses_separate_task_reader(self):
        calls=[]
        class CRM:
            def path(self,suffix):return 'bitable/v1/apps/mock/tables/mock/'+suffix
            def call(self,path,method):
                calls.append(('tenant',path,method))
                return {'data':{'items':[{'fields':{'名字':'C','飞书任务ID':'mock-guid'}}]}}
        def task_read(path,method):
            calls.append(('user',path,method))
            return {'data':{'task':{'guid':'mock-guid'}}}
        self.assertEqual(probe(CRM(),'C',task_read)['task_read'],'passed')
        self.assertEqual([c[0] for c in calls],['tenant','user'])
        self.assertTrue(all(c[2]=='GET' for c in calls))
