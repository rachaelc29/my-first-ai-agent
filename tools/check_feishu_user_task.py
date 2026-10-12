"""Read-only test task probe after ephemeral user authorization."""
import getpass
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from crm_sync.feishu import FeishuTestCRM
from crm_sync.model import Conflict, Uncertain
from crm_sync.oauth import authorize
from tools.check_feishu_task_access import probe
from tools.find_test_record import SafeError


def main():
    config=json.loads((Path.home()/'Library/Application Support/PropertyCRMSync/test-config.json').read_text())
    print('用户授权只读测试：只访问指定虚构客户关联的任务，不修改任务或飞书记录。')
    name=input('指定虚构客户名字（例如 C，与表中完全一致）: ').strip()
    if not name:raise Conflict('fictional customer required')
    secret=getpass.getpass('独立测试应用 App Secret（输入隐藏）: ')
    if not secret:raise Conflict('credential not supplied; no requests made')
    crm=FeishuTestCRM(config,secret)
    access=authorize(config['test_app_id'],secret)
    # Tenant identity continues to access the isolated TEST table; only the
    # specified task GET uses the user token. Restore original token even on error.
    def user_task_call(path,method):
        if method!='GET' or not path.startswith('task/v2/tasks/'):
            raise Conflict('user probe endpoint rejected')
        original=crm.token
        try:
            crm.token=access
            return crm.call(path,method)
        finally:
            crm.token=original
    print(json.dumps(probe(crm,name,user_task_call),ensure_ascii=False))
    print('测试结束；没有保存应用密钥、访问令牌或刷新令牌。')


if __name__=='__main__':
    try:main()
    except (Conflict,Uncertain,SafeError) as exc:
        print('验证暂停：'+str(exc));raise SystemExit(1)
    except KeyboardInterrupt:
        print('\n已取消。');raise SystemExit(1)
    except Exception:
        print('验证暂停；敏感详情未输出。');raise SystemExit(1)
