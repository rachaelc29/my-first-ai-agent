"""Configure ONLY a separate fictional Feishu test table. No secrets stored."""
import json
import sys
from .main import ROOT

def main():
    if sys.platform!='darwin':raise ValueError('Mac required')
    path=ROOT/'test-config.json'
    config=json.loads(path.read_text())
    print('先完成 Apple 虚构任务测试；这里只配置独立测试表，不配置正式客户表。')
    if input('测试文件和数据表均命名 CRM-SYNC-TEST，且只有虚构数据？输入 YES: ')!='YES':return
    values={}
    for key,label in [('test_app_id','独立测试应用 App ID'),('test_app_token','独立测试文件 app_token'),('test_table_id','独立测试数据表 table_id')]:
        value=input(label+'（不是 Secret）: ').strip()
        if not value or '/' in value or '?' in value:raise ValueError('invalid identifier')
        values[key]=value
    ids=input('允许同步的虚构客户 record_id（多个用英文逗号分隔）: ').strip().split(',')
    ids=[i.strip() for i in ids if i.strip()]
    if not ids or any(not i.startswith('rec') for i in ids):raise ValueError('invalid record identifiers')
    values.update(mode='feishu-test',allowed_test_record_ids=ids)
    config.update(values)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(config,ensure_ascii=False,indent=2));temp.chmod(0o600);temp.replace(path)
    print('测试配置已保存；没有请求飞书，也没有保存 App Secret。运行时仍会校验测试表名称和字段。')

if __name__=='__main__':
    try:main()
    except Exception:
        print('配置暂停；未输出配置内容。');raise SystemExit(1)
