"""Standalone, read-only wiki node resolver. Never save credentials."""
import getpass
import json
import urllib.error
import urllib.parse
import urllib.request


class SafeError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SafeError('已阻止重定向；没有向其他地址发送凭证。')


def request(path, *, payload=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(
        'https://open.feishu.cn/open-apis/' + path,
        headers=headers,
        data=json.dumps(payload).encode() if payload is not None else None,
        method='POST' if payload is not None else 'GET',
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise SafeError('HTTP 状态：' + str(exc.code)) from None
    except SafeError:
        raise
    except Exception:
        raise SafeError('网络或响应异常；敏感详情未输出。') from None
    if not isinstance(result, dict) or result.get('code') != 0:
        code = result.get('code') if isinstance(result, dict) else None
        raise SafeError('飞书拒绝请求；错误码：' + str(code if isinstance(code, int) else '未知'))
    return result


def node_token(value):
    value = value.strip()
    if value.startswith('https://'):
        url = urllib.parse.urlsplit(value)
        if not url.hostname or not url.hostname.endswith('.feishu.cn'):
            raise SafeError('请输入中国版飞书的测试知识库链接。')
        parts = url.path.strip('/').split('/')
        if len(parts) != 2 or parts[0] != 'wiki':
            raise SafeError('需要 /wiki/ 格式的链接。')
        value = parts[1]
    if not value or not value.isascii() or not value.isalnum():
        raise SafeError('知识库节点标识格式不正确。')
    return value


def resolve(app_id, secret, node, call=request):
    auth = call('auth/v3/tenant_access_token/internal', payload={'app_id': app_id, 'app_secret': secret})
    access = auth.get('tenant_access_token')
    if not isinstance(access, str) or not access:
        raise SafeError('认证响应缺少访问令牌。')
    query = urllib.parse.urlencode({'token': node, 'obj_type': 'wiki'})
    result = call('wiki/v2/spaces/get_node?' + query, token=access)
    details = result.get('data', {}).get('node', {})
    if details.get('obj_type') != 'bitable':
        raise SafeError('节点不是多维表格；请检查测试链接。')
    obj_token = details.get('obj_token')
    if not isinstance(obj_token, str) or not obj_token:
        raise SafeError('响应缺少实际多维表格标识。')
    return obj_token


def main():
    print('只查询独立测试知识库节点，不读取客户记录，不修改数据。')
    app_id = input('独立测试应用 App ID（不是 Secret）: ').strip()
    if not app_id.startswith('cli_'):
        raise SafeError('请填写测试应用 App ID。')
    node = node_token(input('独立测试文件的 /wiki/ 链接: '))
    secret = getpass.getpass('独立测试应用 App Secret（输入隐藏）: ')
    if not secret:
        raise SafeError('没有输入凭证；未请求飞书。')
    result = resolve(app_id, secret, node)
    print('查询成功。实际 app_token（文件标识，不是密钥）：')
    print(result)
    print('请仅用于本机测试配置，不需要发送到聊天。')


if __name__ == '__main__':
    try:
        main()
    except SafeError as exc:
        print('查询暂停：' + str(exc))
        raise SystemExit(1)
    except KeyboardInterrupt:
        print('\n已取消。')
        raise SystemExit(1)
    except Exception:
        print('查询暂停；敏感详情未输出。')
        raise SystemExit(1)
