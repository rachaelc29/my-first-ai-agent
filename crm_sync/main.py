"""Run: python3 -B -m crm_sync.main demo | test-lists | mock-apple | feishu-test."""
import argparse
from dataclasses import asdict
from datetime import date, datetime, timedelta
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from .engine import Engine
from .model import Customer, MemoryCRM, MemoryReminders, Conflict, Uncertain
from .apple import AppleReminders

ROOT=Path.home()/'Library/Application Support/PropertyCRMSync'

def mock_customer():
    from followup.parser import ZONE
    return Customer('fictional-customer-001', (datetime.now(ZONE).date()+timedelta(days=3)).isoformat()+'，询问虚构客户和家人讨论的结果')

def demo():
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        c=mock_customer();crm=MemoryCRM([c]);apple=MemoryReminders()
        engine=Engine(crm,apple,Path(directory)/'state.sqlite')
        print('1 飞书模拟计划 → Apple 模拟任务:',engine.run())
        task=apple.find(c.task_id)
        from followup.parser import ZONE
        task.due=(datetime.now(ZONE).date()+timedelta(days=5)).isoformat()
        task.content='虚构客户：改为询问学校申请进展'
        print('2 Apple 模拟改期/内容 → 飞书下次follow:',engine.run())
        assert c.plan==task.due+'，'+task.content
        task.completed=True
        task.completed_at=datetime.now(ZONE).isoformat()
        print('3 Apple 模拟完成 → 飞书最新follow/状态:',engine.run())
        assert c.latest.endswith('\n'+task.content) and c.status=='已完成' and c.plan==''
        print('4 重跑不重复创建:',engine.run())
        assert len(apple.tasks)==1
        print('Demo passed. No external services accessed.')
        engine.close()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['demo','test-lists','mock-apple','feishu-test'])
    parser.add_argument('--watch',action='store_true')
    parser.add_argument('--review',action='store_true')
    args=parser.parse_args()
    if args.mode=='demo':return demo()
    if sys.platform!='darwin':raise Conflict('Apple connection requires your Mac')
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    import fcntl
    with open(ROOT/'sync.lock','a') as lock_handle:
        try: fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise Conflict('another local sync process is running')
        if args.mode=='test-lists':
            bridge=AppleReminders('',{},ROOT)
            print(json.dumps(bridge.call({'command':'test_lists'}),ensure_ascii=False))
            return
        config_path=ROOT/'test-config.json'
        if not config_path.exists():raise Conflict('test-config.json not yet configured')
        config=json.loads(config_path.read_text())
        if not config.get('apple_test_list_id'):raise Conflict('test list identifier required')
        if config.get('test_only_ack')!='ONLY_FICTIONAL_TEST_DATA':raise Conflict('test acknowledgement required')
        mode_dir=ROOT/args.mode
        mode_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
        if args.mode=='mock-apple':
            snapshot=mode_dir/'mock-crm.json'
            customers=[Customer(**v) for v in json.loads(snapshot.read_text())] if snapshot.exists() else [mock_customer()]
            crm=MemoryCRM(customers)
        else:
            from .feishu import FeishuTestCRM
            # Secret only in terminal memory, never CLI args, file, log, or repository.
            secret=getpass.getpass('独立飞书测试应用 App Secret（输入隐藏）: ')
            crm=FeishuTestCRM(config,secret)
            secret=None
            snapshot=None
        apple=AppleReminders(config['apple_test_list_id'],{},mode_dir)
        engine=Engine(crm,apple,mode_dir/'state.sqlite',approved_fuzzy=config.get('approved_fuzzy_rules',False))
        try:
            if args.review:
                print('只在自己的 Mac 本地显示测试内容，请勿发送截图或报告。')
                for item in engine.review():
                    print(json.dumps(item,ensure_ascii=False,indent=2))
                    choice=input('选择 crm / apple / completion / new；直接回车跳过: ').strip()
                    if choice in ('crm','apple','completion','new'):
                        approval = input('确认使用以上显示内容进行测试写入？输入 YES: ').strip()
                        if approval == 'YES':
                            engine.resolve(item,choice)
                            print('确认已执行；正在保存并核验结果。')
                        else:
                            print('未收到明确的 YES，已取消；没有执行这项写入。')
                    elif choice:
                        print('选项无法识别，已跳过；没有执行这项写入。')
                    else:
                        print('已跳过；没有执行这项写入。')
                if snapshot:
                    temp=snapshot.with_suffix('.tmp');temp.write_text(json.dumps([asdict(c) for c in crm.list_customers()],ensure_ascii=False));temp.chmod(0o600);temp.replace(snapshot)
                    saved = json.loads(snapshot.read_text())
                    if saved != [asdict(c) for c in crm.list_customers()]:
                        raise Uncertain('mock result persistence verification failed')
                    print('本地模拟资料已保存并核验。')
                return
            while True:
                if snapshot and snapshot.exists():
                    rows=json.loads(snapshot.read_text())
                    crm.customers={row['id']:Customer(**row) for row in rows}
                result=engine.run()
                if snapshot:
                    # Only fictional local records. Saved atomically for restart.
                    temp=snapshot.with_suffix('.tmp');temp.write_text(json.dumps([asdict(c) for c in crm.list_customers()],ensure_ascii=False));temp.chmod(0o600);temp.replace(snapshot)
                print(json.dumps({'events':result},ensure_ascii=False),flush=True)
                if not args.watch:break
                time.sleep(120)
        finally:engine.close()

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('已停止同步，任务未删除。')
    except (Conflict,Uncertain) as exc:
        print('安全暂停：'+str(exc));raise SystemExit(1)
    except Exception:
        print('安全暂停：本地配置或运行失败，未输出敏感详情。');raise SystemExit(1)
