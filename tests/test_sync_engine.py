from dataclasses import asdict
from datetime import date
from pathlib import Path
import tempfile
import unittest
from crm_sync.engine import Engine
from crm_sync.model import Customer, MemoryCRM, MemoryReminders, Uncertain

class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.c=Customer('mock-001','2026-12-01，问候虚构客户',latest='旧的虚构跟进内容')
        self.crm=MemoryCRM([self.c]);self.apple=MemoryReminders()
        self.path=Path(self.temp.name)/'state.sqlite'
        self.e=Engine(self.crm,self.apple,self.path,today=date(2026,10,12))
    def tearDown(self):self.e.close();self.temp.cleanup()
    def create(self):
        self.assertEqual(self.e.run()[0]['status'],'synchronized')
        return self.apple.find(self.c.task_id)
    def test_create_and_repeat(self):
        self.create();tid=self.c.task_id
        self.e.run();self.assertEqual(len(self.apple.tasks),1);self.assertEqual(self.c.task_id,tid)
    def test_apple_date_update_preserves_latest(self):
        t=self.create();t.due='2026-12-04';self.e.run()
        self.assertEqual(self.c.plan,'2026-12-04，问候虚构客户');self.assertEqual(self.c.latest,'旧的虚构跟进内容')
    def test_apple_content_update(self):
        t=self.create();t.content='改为询问虚构申请进展';self.e.run()
        self.assertEqual(self.c.plan,'2026-12-01，改为询问虚构申请进展')
    def test_crm_update_task(self):
        t=self.create();self.c.plan='2026-12-09，虚构新行动';self.e.run()
        self.assertEqual(t.id,self.c.task_id);self.assertEqual(self.apple.find(t.id).content,'虚构新行动')
    def test_completion_uses_latest_exact_content(self):
        t=self.create();t.content='仅记录此最终文字';self.e.run()
        t.completed=True;self.e.run()
        self.assertEqual(self.c.latest,'仅记录此最终文字');self.assertEqual(self.c.status,'已完成')
        self.e.run();self.assertEqual(len(self.apple.tasks),1)
    def test_conflicting_plans_no_write(self):
        t=self.create();self.c.plan='2026-12-02，飞书变更';t.content='Apple变更'
        count=len(self.crm.writes);self.assertEqual(self.e.run()[0]['status'],'needs_confirmation')
        self.assertEqual(len(self.crm.writes),count);self.assertEqual(t.content,'Apple变更')
    def test_completion_conflicts_with_new_plan(self):
        t=self.create();t.completed=True;self.c.plan='2026-12-09，新的计划';self.e.run()
        self.assertEqual(self.c.latest,'旧的虚构跟进内容');self.assertNotEqual(self.c.status,'已完成')
    def test_completion_conflicts_with_latest(self):
        t=self.create();t.completed=True;self.c.latest='手动新增的虚构文字';self.e.run()
        self.assertEqual(self.c.latest,'手动新增的虚构文字');self.assertNotEqual(self.c.status,'已完成')
    def test_unverified_completion_never_written(self):
        t=self.create();t.completed=True;t.final_verified=False;self.e.run()
        self.assertEqual(self.c.latest,'旧的虚构跟进内容');self.assertEqual(self.c.status,'进行中')
    def test_overdue_task_kept(self):
        t=self.create();self.e.today=date(2027,1,1);self.e.run()
        self.assertIn(t.id,self.apple.tasks);self.assertFalse(t.completed)
    def test_removed_task_not_recreated(self):
        t=self.create();del self.apple.tasks[t.id]
        self.assertEqual(self.e.run()[0]['status'],'needs_confirmation');self.assertEqual(len(self.apple.tasks),0)
    def test_two_same_names_distinct_ids(self):
        self.crm.customers['mock-002']=Customer('mock-002',self.c.plan)
        self.e.run();self.assertEqual(len(self.apple.tasks),2)
        self.assertNotEqual(self.c.task_id,self.crm.get('mock-002').task_id)
    def test_wrong_customer_binding_stops(self):
        t=self.create();t.customer_id='wrong-customer';t.completed=True;self.e.run()
        self.assertEqual(self.c.latest,'旧的虚构跟进内容')
    def test_crash_after_create_reconciles(self):
        original=self.crm.update
        def uncertain(*args,**kwargs):raise Uncertain('mock timeout')
        self.crm.update=uncertain;self.e.run();self.assertEqual(len(self.apple.tasks),1)
        self.e.close();self.crm.update=original
        self.e=Engine(self.crm,self.apple,self.path,today=date(2026,10,12))
        self.e.run();self.assertEqual(len(self.apple.tasks),1);self.assertTrue(self.c.task_id)
    def test_timeout_after_crm_effect_reconciles(self):
        original=self.crm.update
        def uncertain(*args,**kwargs):original(*args,**kwargs);raise Uncertain('mock timeout')
        self.crm.update=uncertain;self.e.run();self.crm.update=original
        self.e.run();self.assertEqual(len(self.apple.tasks),1);self.assertEqual(self.c.status,'进行中')
    def test_pending_changed_data_pauses(self):
        def uncertain(*args,**kwargs):raise Uncertain('mock timeout')
        self.crm.update=uncertain;self.e.run();self.c.plan='2026-12-02，另外的计划'
        self.assertEqual(self.e.run()[0]['status'],'needs_confirmation');self.assertEqual(len(self.apple.tasks),1)
    def test_clear_content_does_not_erase_latest(self):
        t=self.create();t.content='';t.completed=True;self.e.run()
        self.assertEqual(self.c.latest,'旧的虚构跟进内容')
    def test_fuzzy_requires_rule_approval(self):
        self.c.plan='2026年12月初，虚构问候';self.e.run();self.assertEqual(len(self.apple.tasks),0)
        self.e.approved_fuzzy=True;self.e.run();self.assertEqual(len(self.apple.tasks),1)
    def test_event_and_missing_anchor_wait(self):
        for plan in ['客户回台湾后再联系','下周五，联系']:
            self.c.plan=plan;self.e.run();self.assertEqual(len(self.apple.tasks),0)
    def test_converged_changes_no_extra_write(self):
        t=self.create();self.c.plan='2026-12-02，双方一样';t.due='2026-12-02';t.content='双方一样'
        before=len(self.crm.writes);self.assertEqual(self.e.run()[0]['status'],'converged')
        self.assertEqual(len(self.crm.writes),before)
    def test_personal_task_untouched(self):
        from crm_sync.model import Task
        personal=Task('personal','not-crm','虚构个人待办',None)
        self.apple.tasks['personal']=personal;self.create();self.e.run()
        self.assertEqual(asdict(self.apple.tasks['personal']),asdict(personal))
    def test_field_whitelist(self):
        with self.assertRaises(ValueError):self.crm.update(self.c.id,{'budget':'wrong'},asdict(self.c))

    # Additional human-resolution regressions.
    def test_confirm_completion_snapshot(self):
        t=self.create();t.content='人工确认的最终虚构文字';t.completed=True;t.final_verified=False
        self.e.run();self.assertEqual(self.c.status,'进行中')
        item=self.e.review()[0];self.e.resolve(item,'completion')
        self.assertEqual(self.c.latest,t.content);self.assertEqual(self.c.status,'已完成')
    def test_preview_invalidated(self):
        from crm_sync.model import Conflict
        t=self.create();item=self.e.review()[0];t.content='预览后变了'
        with self.assertRaises(Conflict):self.e.resolve(item,'apple')
    def test_conflict_choose_apple(self):
        t=self.create();self.c.plan='2026-12-04，飞书';t.content='Apple';self.e.run()
        self.e.resolve(self.e.review()[0],'apple')
        self.assertEqual(self.c.plan,'2026-12-01，Apple')
    def test_new_relative_plan_cannot_reuse_anchor(self):
        self.c.anchor='2026-10-12';self.create();self.c.plan='下周五，新的虚构计划'
        self.assertEqual(self.e.run()[0]['status'],'needs_confirmation')

    def test_new_round_keeps_old_completed_task(self):
        t=self.create();t.completed=True;self.e.run()
        self.c.plan='2026-12-15，明确的新一轮跟进';self.e.run()
        self.e.resolve(self.e.review()[0],'new')
        self.assertEqual(len(self.apple.tasks),2)
        self.assertIn(t.id,self.apple.tasks);self.assertTrue(t.completed)
        self.assertNotEqual(self.c.task_id,t.id);self.assertEqual(self.c.status,'进行中')
    def test_new_round_confirmed_keeps_unfinished_old_task(self):
        t=self.create();self.c.plan='2026-12-15，独立的新任务'
        self.e.resolve(self.e.review()[0],'new')
        self.assertIn(t.id,self.apple.tasks);self.assertFalse(t.completed)
        self.assertEqual(len(self.apple.tasks),2)

    def test_changed_content_and_completion_still_needs_confirmation(self):
        t=self.create();t.content='完成时还修改了内容';t.completed=True
        self.assertEqual(self.e.run()[0]['status'],'needs_confirmation')
        self.assertEqual(self.c.latest,'旧的虚构跟进内容')
        self.assertEqual(self.c.status,'进行中')

    def test_unchanged_content_completes_automatically(self):
        t=self.create();t.completed=True
        self.assertEqual(self.e.run()[0]['status'],'synchronized')
        self.assertEqual(self.c.latest,t.content)
        self.assertEqual(self.c.status,'已完成')
