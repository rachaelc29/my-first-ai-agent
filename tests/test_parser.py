import unittest
from datetime import date, datetime, timezone
from followup.parser import parse, Rules, reminder_ready

class ParserTests(unittest.TestCase):
    def p(self, text, anchor=date(2026,10,12), today=date(2026,10,12), rules=None):
        return parse(text, anchor=anchor, today=today, rules=rules)

    def test_explicit_dates(self):
        for text, expected in [('2026-12-01，问候', '2026-12-01'), ('2026/12/1，问候', '2026-12-01'), ('2026年12月1日，问候', '2026-12-01'), ('今年12月1号，问候', '2026-12-01')]:
            with self.subTest(text=text):
                r=self.p(text); self.assertEqual(r['proposed_reminder_date'],expected); self.assertFalse(r['can_remind'])

    def test_user_examples(self):
        cases=[('12月初，问候客户，了解孩子学校申请进展','year_ambiguous',None),('下周五，询问客户和家人讨论房产的结果','relative','2026-10-23'),('11月中旬，客户回台湾后再联系','event',None),('明年2月，了解是否有新的购房计划','fuzzy','2027-02-01')]
        for text,kind,expected in cases:
            with self.subTest(text=text):
                r=self.p(text);self.assertEqual(r['kind'],kind);self.assertEqual(r['proposed_reminder_date'],expected);self.assertEqual(r['original_text'],text)

    def test_fuzzy_windows(self):
        for phrase,start,end in [('初',1,10),('中旬',11,20),('底',21,28),('末',21,28)]:
            with self.subTest(phrase=phrase):
                r=self.p('2027年2月'+phrase+'，联系');self.assertEqual(r['window_start'],f'2027-02-{start:02}');self.assertEqual(r['window_end'],f'2027-02-{end:02}')
        self.assertEqual(self.p('2028年2月，联系')['window_end'],'2028-02-29')

    def test_year_not_invented(self):
        for text in ['12月初，联系','2月1日，联系','01/02，联系','周五，联系','下个月，联系']:
            with self.subTest(text=text):self.assertIsNone(self.p(text)['proposed_reminder_date'])

    def test_missing_anchor(self):
        for text in ['明年2月，联系','下周五，联系','明天，联系']:
            with self.subTest(text=text):self.assertIsNone(self.p(text,anchor=None)['proposed_reminder_date'])

    def test_relative_calendar(self):
        for text,anchor,expected in [('下周五，联系',date(2026,12,31),'2027-01-08'),('明天，联系',date(2026,12,31),'2027-01-01'),('3天后，联系',date(2026,10,12),'2026-10-15'),('本周五，联系',date(2026,10,12),'2026-10-16'),('下周天，联系',date(2026,10,12),'2026-10-25')]:
            with self.subTest(text=text):self.assertEqual(self.p(text,anchor=anchor)['proposed_reminder_date'],expected)

    def test_invalid_dates(self):
        for text in ['2026-02-29，联系','2026年13月初，联系','2026年2月30日，联系','9999天后，联系']:
            with self.subTest(text=text):self.assertIsNone(self.p(text)['proposed_reminder_date'])

    def test_events_and_conflicts(self):
        for text in ['客户回来后再联系','2026年12月初，等申请完成后再联系','下周五，或者2026年12月1日再联系','2026年12月初，明年再问']:
            with self.subTest(text=text):self.assertIsNone(self.p(text)['proposed_reminder_date'])

    def test_policy(self):
        r=self.p('2026年12月初，联系',rules=Rules(reminder_at='end'));self.assertEqual(r['proposed_reminder_date'],'2026-12-10')
        r=self.p('2026年12月初，联系',rules=Rules(periods={'初':(3,7)}));self.assertEqual(r['window_start'],'2026-12-03')
        r=self.p('2026-10-17，联系',rules=Rules(weekdays_only=True));self.assertEqual(r['status'],'needs_confirmation')
        with self.assertRaises(ValueError):self.p('今天',rules=Rules(reminder_at='unknown'))

    def test_overdue_and_reparse(self):
        r=self.p('下周五，联系',today=date(2026,11,1));self.assertEqual(r['status'],'overdue_review');self.assertEqual(r['window_start'],'2026-10-23')
        r=self.p('2025-12-01，联系');self.assertEqual(r['status'],'overdue_review')

    def test_timezone(self):
        # UTC Sunday already Monday in Melbourne (daylight saving).
        r=self.p('下周五，联系',anchor=datetime(2026,10,11,14,tzinfo=timezone.utc));self.assertEqual(r['window_start'],'2026-10-23')
        with self.assertRaises(ValueError):self.p('明天',anchor=datetime(2026,10,12))

    def test_no_automatic_reminders(self):
        text='2026-10-12，联系';r=self.p(text)
        self.assertFalse(reminder_ready(r,today=date(2026,10,12),confirmed=False,current_text=text))
        self.assertTrue(reminder_ready(r,today=date(2026,10,12),confirmed=True,current_text=text))
        self.assertFalse(reminder_ready(r,today=date(2026,10,12),confirmed=True,current_text='已改计划'))
        self.assertFalse(reminder_ready(r,today=date(2026,10,13),confirmed=True,current_text=text))
        self.assertFalse(reminder_ready(self.p('客户回来后再联系'),today=date(2026,10,12),confirmed=True,current_text='客户回来后再联系',event_satisfied=True))

    def test_empty_and_action_preserved(self):
        self.assertIsNone(self.p('')['proposed_reminder_date'])
        self.assertEqual(self.p('下周五，询问客户，了解家人意见')['action_text'],'询问客户，了解家人意见')

if __name__ == '__main__':unittest.main()
