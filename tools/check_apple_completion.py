"""Mac-only test-list timestamp diagnostic. No Feishu connection or writes."""
import json
from pathlib import Path
import subprocess
import sys


def main():
    if sys.platform != 'darwin':
        print('请在自己的 Mac 上运行。');return 1
    root = Path.home() / 'Library/Application Support/PropertyCRMSync'
    try:
        config = json.loads((root / 'test-config.json').read_text())
        if config.get('test_only_ack') != 'ONLY_FICTIONAL_TEST_DATA':
            print('测试范围未确认，已停止。');return 1
        payload = {'command':'completion_diagnostics', 'list_id':config['apple_test_list_id']}
        binary = root / 'RemindersBridge.app/Contents/MacOS/RemindersBridge'
        response = subprocess.run([str(binary)], input=json.dumps(payload),
                                  text=True, capture_output=True, timeout=150)
        result = json.loads(response.stdout)
        if not result.get('ok'):
            print('诊断暂停：请确认桥接程序已重新编译且提醒事项权限允许。');return 1
        print('只读时间诊断（UTC）；没有修改提醒或请求飞书：')
        print(json.dumps(result['result'],ensure_ascii=False,indent=2))
        return 0
    except Exception:
        print('诊断暂停；敏感详情未输出。');return 1


if __name__ == '__main__':
    raise SystemExit(main())
