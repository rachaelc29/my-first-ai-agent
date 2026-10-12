"""Local test-only task access probe. No writes, no credential persistence."""
import getpass
import json
from pathlib import Path
import sys
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crm_sync.feishu import FeishuTestCRM
from crm_sync.model import Conflict, Uncertain
from tools.find_test_record import pages, SafeError


def text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ''.join(part.get('text','') for part in value if isinstance(part,dict))
    raise SafeError('测试字段不是文本，已停止。')


def probe(crm, name, task_call=None):
    # FeishuTestCRM constructor verifies exact TEST base/table/schema first.
    def call(path, **kwargs):
        return crm.call(path, 'GET')
    records = pages(crm.path('records'), None, call,
                    {'field_names':json.dumps(['名字','飞书任务ID'],ensure_ascii=False)})
    matched = [r for r in records if text(r.get('fields',{}).get('名字','')) == name]
    if len(matched) != 1:
        raise SafeError('没有唯一的虚构客户匹配，已停止。')
    guid = text(matched[0]['fields'].get('飞书任务ID',''))
    if not guid:
        raise SafeError('该虚构记录没有飞书任务ID，已停止。')
    path = 'task/v2/tasks/' + urllib.parse.quote(guid,safe='') + '?user_id_type=open_id'
    task = (task_call or crm.call)(path,'GET').get('data',{}).get('task',{})
    if task.get('guid') != guid:
        raise SafeError('任务身份核验失败，已停止。')
    # Do not print task title/description, owner IDs, table IDs or credentials.
    return {'task_read':'passed','identity_match':'passed','task_write':'not_tested'}


def main():
    root=Path.home()/'Library/Application Support/PropertyCRMSync'
    config=json.loads((root/'test-config.json').read_text())
    print('只读验证独立 CRM-SYNC-TEST 表关联的任务，不更新或完成任何任务。')
    name=input('指定虚构客户名字（例如 B；需与测试表完全一致）: ').strip()
    if not name:
        raise SafeError('未指定虚构客户，已取消。')
    secret=getpass.getpass('独立测试应用 App Secret（输入隐藏）: ')
    if not secret:
        raise SafeError('未输入凭证，没有联网。')
    crm=FeishuTestCRM(config,secret)
    print(json.dumps(probe(crm,name),ensure_ascii=False))


if __name__=='__main__':
    try:
        main()
    except (Conflict,Uncertain,SafeError) as exc:
        print('验证暂停：'+str(exc));raise SystemExit(1)
    except KeyboardInterrupt:
        print('\n已取消。');raise SystemExit(1)
    except Exception:
        print('验证暂停；敏感详情未输出。');raise SystemExit(1)
