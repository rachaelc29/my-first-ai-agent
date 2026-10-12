import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from crm_sync import main
from crm_sync.model import MemoryReminders

class ReviewCLITests(unittest.TestCase):
    def run_case(self, approval):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'test-config.json').write_text(json.dumps({'apple_test_list_id':'mock-list','test_only_ack':'ONLY_FICTIONAL_TEST_DATA'}))
            reminders=MemoryReminders()
            output=io.StringIO()
            with patch.object(main,'ROOT',root), patch.object(main.sys,'platform','darwin'), patch.object(main,'AppleReminders',return_value=reminders),contextlib.redirect_stdout(output):
                with patch.object(main.sys,'argv',['sync','mock-apple']):main.main()
                task=next(iter(reminders.tasks.values()))
                task.completed=True;task.final_verified=False
                with patch.object(main.sys,'argv',['sync','mock-apple','--review']), patch('builtins.input',side_effect=['completion',approval]):main.main()
            saved=json.loads((root/'mock-apple/mock-crm.json').read_text())[0]
            return saved,output.getvalue()
    def test_confirm_persists_completion(self):
        saved,output=self.run_case('YES')
        self.assertEqual(saved['status'],'已完成')
        self.assertEqual(saved['latest'],'询问虚构客户和家人讨论的结果')
        self.assertIn('确认已执行',output)
        self.assertIn('已保存并核验',output)
    def test_surrounding_spaces_do_not_silently_skip(self):
        saved,output=self.run_case(' YES ')
        self.assertEqual(saved['status'],'已完成')
    def test_no_confirmation_is_explicitly_cancelled(self):
        saved,output=self.run_case('')
        self.assertEqual(saved['status'],'进行中')
        self.assertEqual(saved['latest'],'')
        self.assertIn('已取消',output)
