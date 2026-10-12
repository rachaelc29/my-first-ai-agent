"""Local setup for mock Apple testing only. No Feishu credentials needed."""
import json
import sys
from .apple import AppleReminders
from .main import ROOT
from .model import Conflict

def main():
    if sys.platform!='darwin':raise Conflict('run this on your Mac')
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=ROOT/'test-config.json'
    if path.exists():raise Conflict('configuration exists; will not overwrite it')
    bridge=AppleReminders('',{},ROOT)
    lists=bridge.call({'command':'test_lists'})
    if len(lists)!=1 or not lists[0]['writable']:
        raise Conflict('create exactly one writable CRM-SYNC-TEST list first')
    if input('只处理 CRM-SYNC-TEST 虚构测试列表，输入 YES 同意: ')!='YES':
        print('未配置。');return
    path.write_text(json.dumps({'apple_test_list_id':lists[0]['id'],
        'test_only_ack':'ONLY_FICTIONAL_TEST_DATA','approved_fuzzy_rules':False},indent=2))
    path.chmod(0o600)
    print('已配置模拟测试模式；没有创建或修改提醒。')

if __name__=='__main__':
    try:main()
    except Exception:
        print('设置暂停：请检查本机程序是否编译、权限是否允许及是否已有配置。');raise SystemExit(1)
