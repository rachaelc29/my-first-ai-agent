"""Only a separately configured base/table named CRM-SYNC-TEST is writable."""
from dataclasses import asdict
import json
import urllib.parse
import urllib.request
import urllib.error
from .model import Customer, Conflict, Uncertain
from tools.verify_feishu_schema import NoRedirect

FIELD_MAP = {'plan':'下次follow','latest':'最新follow','task_id':'跟进任务编号',
             'status':'跟进任务状态','anchor':'跟进计划记录时间'}
EXPECTED_TYPES = {'名字':1,'下次follow':1,'最新follow':1,'跟进任务编号':1,
                  '跟进任务状态':3,'跟进计划记录时间':5}

class FeishuTestCRM:
    def __init__(self, config, secret):
        self.config = config
        if config.get('mode') != 'feishu-test' or config.get('test_only_ack') != 'ONLY_FICTIONAL_TEST_DATA':
            raise Conflict('explicit test acknowledgement required')
        self.app = urllib.parse.quote(config['test_app_token'],safe='')
        self.table = urllib.parse.quote(config['test_table_id'],safe='')
        self.token = None
        self.token = self.call('auth/v3/tenant_access_token/internal','POST',
            {'app_id':config['test_app_id'],'app_secret':secret})['tenant_access_token']
        base = self.call('bitable/v1/apps/'+self.app,'GET')['data']['app']
        if base.get('name') != 'CRM-SYNC-TEST':
            raise Conflict('base name must be CRM-SYNC-TEST')
        tables = self.pages('bitable/v1/apps/'+self.app+'/tables')
        if not any(t.get('table_id')==config['test_table_id'] and t.get('name')=='CRM-SYNC-TEST' for t in tables):
            raise Conflict('test table identity mismatch')
        fields = self.pages(self.path('fields'))
        types = {f['field_name']:f['type'] for f in fields}
        if any(types.get(k)!=v for k,v in EXPECTED_TYPES.items()):
            raise Conflict('test schema mismatch')
        # Record IDs must be explicitly allowed. No unrestricted table writes.
        self.allowed = set(config.get('allowed_test_record_ids',[]))
        if not self.allowed:
            raise Conflict('test record allowlist required')

    def path(self, suffix):
        return 'bitable/v1/apps/'+self.app+'/tables/'+self.table+'/'+suffix

    def call(self,path,method,payload=None):
        headers={'Content-Type':'application/json'}
        if self.token:headers['Authorization']='Bearer '+self.token
        request=urllib.request.Request('https://open.feishu.cn/open-apis/'+path,
            headers=headers,method=method,data=json.dumps(payload).encode() if payload is not None else None)
        try:
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=30) as response:
                result=json.load(response)
        except Exception:
            if method=='PUT':raise Uncertain('test write result unknown') from None
            raise Conflict('test API unavailable') from None
        if result.get('code')!=0:
            raise Conflict('test API rejected operation')
        return result

    def pages(self,path):
        items=[];page=None;seen=set()
        while True:
            query={'page_size':100}
            if page:query['page_token']=page
            data=self.call(path+'?'+urllib.parse.urlencode(query),'GET')['data']
            items.extend(data['items'])
            if not data.get('has_more'):return items
            page=data.get('page_token')
            if not page or page in seen:raise Conflict('invalid pagination')
            seen.add(page)

    def _customer(self,record):
        fields=record['fields']
        def text(name):
            value=fields.get(name,'')
            if isinstance(value,list):return ''.join(part.get('text','') for part in value)
            if not isinstance(value,str):raise Conflict('unexpected test field value')
            return value
        anchor=fields.get('跟进计划记录时间')
        if anchor:
            from datetime import datetime
            from followup.parser import ZONE
            anchor=datetime.fromtimestamp(anchor/1000,ZONE).date().isoformat()
        else:anchor=''
        return Customer(record['record_id'],text('下次follow'),text('最新follow'),
            text('跟进任务编号'),text('跟进任务状态'),anchor)

    def list_customers(self):
        # Fetch only explicitly allowed mock records, never list entire customer table.
        return [self.get(cid) for cid in sorted(self.allowed)]

    def get(self,cid):
        if cid not in self.allowed:raise Conflict('record not allowlisted')
        return self._customer(self.call(self.path('records/'+urllib.parse.quote(cid,safe='')),'GET')['data']['record'])

    def update(self,cid,changes,expected):
        if set(changes)-set(FIELD_MAP):raise Conflict('field outside write whitelist')
        if asdict(self.get(cid))!=expected:raise Conflict('test CRM changed before write')
        fields={FIELD_MAP[k]:v for k,v in changes.items()}
        if 'anchor' in changes:raise Conflict('anchor changes not enabled in this pilot')
        self.call(self.path('records/'+urllib.parse.quote(cid,safe='')),'PUT',{'fields':fields})
        actual=self.get(cid)
        if asdict(actual)!=dict(expected,**changes):raise Uncertain('test write verification failed')
        return actual
