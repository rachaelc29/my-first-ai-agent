"""Phase 1: authentication + field schema only. Never fetch customer records."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

VARIABLES = ('FEISHU_APP_ID', 'FEISHU_APP_SECRET', 'FEISHU_APP_TOKEN', 'FEISHU_TABLE_ID')
BASE = 'https://open.feishu.cn/open-apis/'

class SafeFailure(Exception):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SafeFailure('redirect blocked')

def request_json(path, *, payload=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(BASE + path, headers=headers,
        data=json.dumps(payload).encode() if payload is not None else None,
        method='POST' if payload is not None else 'GET')
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise SafeFailure('HTTP status ' + str(exc.code)) from None
    except SafeFailure:
        raise
    except Exception:
        raise SafeFailure('network or response failure; sensitive details suppressed') from None
    if not isinstance(result, dict) or result.get('code') != 0:
        code = result.get('code') if isinstance(result, dict) else None
        raise SafeFailure('API rejected request; numeric code=' + str(code if isinstance(code, int) else 'unknown'))
    return result

def verify(config, call=request_json):
    missing = [name for name in VARIABLES if not config.get(name)]
    if missing:
        raise SafeFailure('missing variable names: ' + ', '.join(missing))
    result = call('auth/v3/tenant_access_token/internal',
        payload={'app_id': config['FEISHU_APP_ID'], 'app_secret': config['FEISHU_APP_SECRET']})
    token = result.get('tenant_access_token')
    if not isinstance(token, str) or not token:
        raise SafeFailure('authentication token missing')
    app = urllib.parse.quote(config['FEISHU_APP_TOKEN'], safe='')
    table = urllib.parse.quote(config['FEISHU_TABLE_ID'], safe='')
    fields, seen, page = [], set(), None
    while True:
        query = {'page_size': 100}
        if page:
            query['page_token'] = page
        result = call('bitable/v1/apps/' + app + '/tables/' + table + '/fields?' + urllib.parse.urlencode(query), token=token)
        data = result.get('data')
        if not isinstance(data, dict) or not isinstance(data.get('items'), list):
            raise SafeFailure('field schema response invalid')
        for item in data['items']:
            if not isinstance(item, dict) or not isinstance(item.get('field_name'), str) or not isinstance(item.get('type'), int):
                raise SafeFailure('field definition invalid')
            fields.append({'name': item['field_name'], 'type': item['type'], 'ui_type': item.get('ui_type')})
        if not data.get('has_more'):
            break
        page = data.get('page_token')
        if not isinstance(page, str) or not page or page in seen:
            raise SafeFailure('pagination incomplete')
        seen.add(page)
    return {'authentication': 'passed', 'schema': 'passed', 'field_count': len(fields), 'fields': fields}

if __name__ == '__main__':
    try:
        print(json.dumps(verify(os.environ), ensure_ascii=False))
    except SafeFailure as exc:
        print(json.dumps({'status': 'failed', 'reason': str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
