"""Read-only lookup of one fictional record in an explicitly named test base."""
import getpass
import urllib.parse
import json
try:
    from tools.resolve_feishu_wiki import request, SafeError
except ModuleNotFoundError:
    from resolve_feishu_wiki import request, SafeError


def pages(path, token, call, extra=None):
    result, seen, page = [], set(), None
    while True:
        params = dict(extra or {}, page_size=100)
        if page:
            params['page_token'] = page
        response = call(path + '?' + urllib.parse.urlencode(params), token=token)
        data = response.get('data', {})
        if not isinstance(data.get('items'), list):
            raise SafeError('返回结构不完整，已停止。')
        result.extend(data['items'])
        if not data.get('has_more'):
            return result
        page = data.get('page_token')
        if not isinstance(page, str) or not page or page in seen:
            raise SafeError('分页不完整，已停止。')
        seen.add(page)


def find(app_id, secret, app_token, table_id, name, call=request):
    auth = call('auth/v3/tenant_access_token/internal', payload={'app_id':app_id,'app_secret':secret})
    token = auth.get('tenant_access_token')
    if not token:
        raise SafeError('认证没有返回访问令牌。')
    root = 'bitable/v1/apps/' + urllib.parse.quote(app_token, safe='')
    base = call(root, token=token).get('data', {}).get('app', {})
    if base.get('name') != 'CRM-SYNC-TEST':
        raise SafeError('文件名称不是 CRM-SYNC-TEST；没有读取记录。')
    tables = pages(root + '/tables', token, call)
    if not any(t.get('table_id') == table_id and t.get('name') == 'CRM-SYNC-TEST' for t in tables):
        raise SafeError('数据表身份不符合测试范围；没有读取记录。')
    # Only the name field is requested. No budgets, contact details or follow-up history.
    records = pages(root + '/tables/' + urllib.parse.quote(table_id, safe='') + '/records',
                    token, call, {'field_names':json.dumps(['名字'],ensure_ascii=False)})
    matches = []
    for record in records:
        value = record.get('fields', {}).get('名字', '')
        if isinstance(value, list):
            value = ''.join(v.get('text','') for v in value if isinstance(v,dict))
        if value == name:
            matches.append(record.get('record_id'))
    if len(matches) != 1 or not isinstance(matches[0],str) or not matches[0].startswith('rec'):
        raise SafeError('未找到唯一的虚构客户匹配；没有选取记录。')
    return matches[0]


def main():
    print('只读查询独立测试表；不会修改任何数据，也不会读取正式环境变量。')
    if input('确认 CRM-SYNC-TEST 文件中只有虚构数据？输入 YES: ').strip() != 'YES':
        print('已取消。'); return
    app_id = input('独立测试应用 App ID: ').strip()
    app_token = input('实际测试 app_token（不是 wiki 节点）: ').strip()
    table_id = input('测试 table_id: ').strip()
    name = input('虚构客户名字（直接回车使用 测试客户 A（虚构））: ').strip() or '测试客户 A（虚构）'
    if not app_id.startswith('cli_') or not app_token.isalnum() or not table_id.startswith('tbl'):
        raise SafeError('测试标识格式不正确。')
    secret = getpass.getpass('独立测试应用 App Secret（输入隐藏）: ')
    if not secret:
        raise SafeError('未输入凭证，没有联网。')
    record = find(app_id,secret,app_token,table_id,name)
    print('唯一虚构客户的真实 record_id：')
    print(record)
    print('请仅用于本机配置，不需要发送到聊天。没有写入任何记录。')


if __name__ == '__main__':
    try:
        main()
    except SafeError as exc:
        print('查询暂停：' + str(exc));raise SystemExit(1)
    except KeyboardInterrupt:
        print('\n已取消。');raise SystemExit(1)
    except Exception:
        print('查询暂停；敏感详情未输出。');raise SystemExit(1)
