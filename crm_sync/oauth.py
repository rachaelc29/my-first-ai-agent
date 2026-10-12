"""Ephemeral localhost OAuth probe. No token/secret persistence or logs."""
import base64
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from .model import Conflict
from tools.verify_feishu_schema import NoRedirect

REDIRECT_URI = 'http://localhost:8765/callback'
SCOPES = 'task:task:read'
UPDATE_SCOPES = 'task:task:read task:task:writeonly'


def authorization_url(app_id, state, verifier, scopes=SCOPES):
    if scopes not in (SCOPES, UPDATE_SCOPES):
        raise Conflict('probe scopes not permitted')
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode()
    params = {'client_id':app_id,'response_type':'code','redirect_uri':REDIRECT_URI,
              'scope':scopes,'state':state,'code_challenge':challenge,
              'code_challenge_method':'S256','prompt':'consent'}
    return 'https://accounts.feishu.cn/open-apis/authen/v1/authorize?' + urllib.parse.urlencode(params)


def parse_callback(path, expected_state):
    url = urllib.parse.urlsplit(path)
    if url.path != '/callback':
        raise Conflict('callback path rejected')
    params = urllib.parse.parse_qs(url.query,keep_blank_values=True)
    if len(params.get('state',[])) != 1 or not hmac.compare_digest(params['state'][0],expected_state):
        raise Conflict('callback state rejected')
    if 'error' in params:
        raise Conflict('user declined authorization')
    if len(params.get('code',[])) != 1 or not params['code'][0] or len(params['code'][0]) > 8192:
        raise Conflict('authorization code missing or invalid')
    return params['code'][0]


def token_request(payload):
    # Officially documented v2 + PKCE combination for this isolated read probe.
    # A production deployment will require refreshed-token storage and endpoint review.
    req = urllib.request.Request('https://open.feishu.cn/open-apis/authen/v2/oauth/token',
        data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise Conflict('OAuth token HTTP status '+str(exc.code)) from None
    except Exception:
        raise Conflict('OAuth token network or response failure') from None
    if not isinstance(result,dict) or result.get('code') != 0 or not result.get('access_token'):
        code=result.get('code') if isinstance(result,dict) else None
        raise Conflict('OAuth token rejected; numeric code '+str(code if isinstance(code,int) else 'unknown'))
    return result['access_token']


def authorize(app_id, secret, timeout=300, exchange=token_request, *, scopes=SCOPES):
    state=secrets.token_urlsafe(32)
    verifier=secrets.token_urlsafe(64)
    result={}
    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log callback URL, authorization code, or state.
        def do_GET(self):
            if self.headers.get('Host') not in ('localhost:8765','127.0.0.1:8765'):
                self.send_error(400,'Invalid host');return
            try:
                code=parse_callback(self.path,state)
            except Conflict as exc:
                if str(exc)=='user declined authorization':
                    result['error']='authorization declined'
                self.send_error(400,'Authorization not accepted');return
            if result:
                self.send_error(409,'Already received');return
            result['code']=code
            page='<html><head><meta charset="UTF-8"></head><body>授权结果已送达本机。请关闭此页并查看终端；不要分享地址栏内容。</body></html>'.encode()
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(page)))
            self.send_header('Cache-Control','no-store')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'none'")
            self.end_headers();self.wfile.write(page)
    try:
        server=HTTPServer(('127.0.0.1',8765),Callback)
    except OSError:
        raise Conflict('local callback port unavailable; no browser authorization started') from None
    with server:
        server.timeout=1
        if not webbrowser.open(authorization_url(app_id,state,verifier,scopes)):
            raise Conflict('browser could not open; authorization not started')
        print('浏览器已打开飞书官方授权页。请确认是测试应用并完成登录授权；最多等待5分钟。')
        deadline=time.monotonic()+timeout
        while not result and time.monotonic()<deadline:
            server.handle_request()
    if not result.get('code'):
        raise Conflict('authorization declined or timed out; no token saved')
    return exchange({'grant_type':'authorization_code','client_id':app_id,'client_secret':secret,
                     'code':result['code'],'redirect_uri':REDIRECT_URI,'code_verifier':verifier})
