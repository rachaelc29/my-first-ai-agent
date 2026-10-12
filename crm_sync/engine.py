"""Persistent baselines + pending operations. No AI or production credentials."""
from dataclasses import asdict
from datetime import date, datetime
import json
import os
from pathlib import Path
import sqlite3
import uuid
from followup.parser import parse, ZONE
from .model import Task, Conflict, Uncertain, task_value, plan_text

class Engine:
    def __init__(self, crm, reminders, state_file, *, today=None, approved_fuzzy=False):
        self.crm, self.reminders = crm, reminders
        self.today = today or datetime.now(ZONE).date()
        self.approved_fuzzy = approved_fuzzy
        path = Path(state_file)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.exists() and path.is_symlink():
            raise ValueError('state must not be a symlink')
        self.db = sqlite3.connect(path)
        os.chmod(path, 0o600)
        self.db.execute('CREATE TABLE IF NOT EXISTS state (cid TEXT PRIMARY KEY, data TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS pending (cid TEXT PRIMARY KEY, data TEXT NOT NULL)')
        self.db.commit()
        self.events = []

    def close(self):
        self.db.close()

    def _load(self, table, cid):
        row = self.db.execute('SELECT data FROM '+table+' WHERE cid=?', (cid,)).fetchone()
        return json.loads(row[0]) if row else None

    def _save(self, table, cid, value):
        self.db.execute('INSERT OR REPLACE INTO '+table+' VALUES (?,?)', (cid, json.dumps(value,ensure_ascii=False)))
        self.db.commit()

    def _event(self, cid, status):
        # No customer content or identifier goes to stdout.
        self.events.append({'status': status})

    def _parts(self, c):
        anchor = date.fromisoformat(c.anchor) if c.anchor else None
        result = parse(c.plan, anchor=anchor, today=self.today)
        if result['status'] != 'proposed':
            raise Conflict('date needs confirmation')
        if result['kind'] == 'fuzzy' and not self.approved_fuzzy:
            raise Conflict('fuzzy rule not approved')
        if not result['action_text']:
            raise Conflict('action content missing')
        return result['action_text'], result['proposed_reminder_date']

    def _baseline(self, c, task):
        self._save('state', c.id, {'crm': asdict(c), 'task': asdict(task)})

    def _completion_changes(self, task):
        if not task.completed_at:
            raise Conflict('actual completion time missing')
        try:
            when = datetime.fromisoformat(task.completed_at.replace('Z', '+00:00'))
            if when.tzinfo is None:
                raise ValueError('timezone missing')
        except (ValueError, TypeError):
            raise Conflict('actual completion time invalid') from None
        stamp = when.astimezone(ZONE).strftime('%Y-%m-%d %H:%M:%S %z')
        return {'status':'已完成','latest':stamp+'（墨尔本时间）\n'+task.content,'plan':''}

    def _operation(self, c, desired_task, changes, current_task):
        op = {'crm_before': asdict(c), 'changes': changes,
              'task_before': asdict(current_task) if current_task else None,
              'task_after': asdict(desired_task)}
        self._save('pending', c.id, op)  # retained BEFORE any remote side effects
        self._reconcile(c.id, op)

    def _reconcile(self, cid, op):
        before, desired = op['crm_before'], op['task_after']
        if hasattr(self.reminders, 'bind'):
            self.reminders.bind(desired['id'], cid)
        task = self.reminders.find(desired['id'])
        c = self.crm.get(cid)
        crm_after = dict(before, **op['changes'])
        if asdict(c) not in (before, crm_after):
            raise Conflict('crm diverged during pending operation')
        if task is not None and asdict(task) == desired:
            pass  # effect already happened
        elif (asdict(task) if task else None) == op['task_before']:
            task = self.reminders.put(Task(**desired), expected=op['task_before'])
        else:
            raise Conflict('task diverged during pending operation')
        if asdict(c) == before and op['changes']:
            self.crm.update(cid, op['changes'], before)
        c = self.crm.get(cid)
        task = self.reminders.find(desired['id'])
        if asdict(c) != crm_after or not task or asdict(task) != desired:
            raise Uncertain('write verification incomplete')
        self._baseline(c, task)
        self.db.execute('DELETE FROM pending WHERE cid=?',(cid,))
        self.db.commit()
        self._event(cid, 'synchronized')

    def review(self):
        rows = self.db.execute('SELECT cid,data FROM state').fetchall()
        results = []
        for cid, data in rows:
            old = json.loads(data)
            c = self.crm.get(cid)
            if hasattr(self.reminders, 'bind'):
                self.reminders.bind(old['task']['id'], cid)
            task = self.reminders.find(old['task']['id'])
            results.append({'customer_id': cid, 'baseline': old, 'crm': asdict(c),
                            'task': asdict(task) if task else None,
                            'has_pending': bool(self._load('pending', cid))})
        return results

    def resolve(self, snapshot, choice):
        cid = snapshot['customer_id']
        if snapshot['has_pending'] or self._load('pending', cid):
            raise Conflict('pending uncertain operation must be reconciled first')
        c = self.crm.get(cid)
        task = self.reminders.find(snapshot['task']['id']) if snapshot['task'] else None
        if asdict(c) != snapshot['crm'] or not task or asdict(task) != snapshot['task']:
            raise Conflict('changed since preview')
        if task.customer_id != cid or task.id != c.task_id:
            raise Conflict('binding invalid')
        if choice == 'new':
            content, due = self._parts(c)
            new_task = Task(str(uuid.uuid4()), cid, content, due)
            self._operation(c, new_task, {'task_id':new_task.id,'status':'进行中'}, None)
        elif choice == 'completion':
            if not task.completed or not task.content:
                raise Conflict('not an eligible completion')
            # Explicit human confirmation of the displayed current content, not a
            # claim to have recovered unavailable completion-time history.
            self._operation(c, task, self._completion_changes(task), task)
        elif choice == 'apple' and not task.completed:
            self._operation(c, task, {'plan': plan_text(task)}, task)
        elif choice == 'crm' and not task.completed:
            content, due = self._parts(c)
            self._operation(c, Task(task.id,cid,content,due), {}, task)
        else:
            raise Conflict('unsupported resolution')

    def run(self):
        self.events = []
        for c in self.crm.list_customers():
            try:
                pending = self._load('pending', c.id)
                if pending:
                    # Actual adapters quarantine an uncertain create; no blind retry.
                    self._reconcile(c.id, pending)
                    continue
                baseline = self._load('state', c.id)
                if not baseline:
                    if c.task_id or c.status == '已完成':
                        raise Conflict('unknown existing task or completed plan; do not recreate')
                    content, due = self._parts(c)
                    tid = str(uuid.uuid4())
                    task = Task(tid,c.id,content,due)
                    self._operation(c,task,{'task_id':tid,'status':'进行中'},None)
                    continue
                old_c, old_t = baseline['crm'], baseline['task']
                if c.task_id != old_t['id']:
                    raise Conflict('binding changed')
                if hasattr(self.reminders, 'bind'):
                    self.reminders.bind(c.task_id, c.id)
                task = self.reminders.find(c.task_id)
                if not task or task.customer_id != c.id:
                    raise Conflict('bound task missing or wrong customer')
                crm_changed = c.plan != old_c['plan'] or c.anchor != old_c['anchor']
                apple_changed = task_value(task) != task_value(Task(**old_t))
                if c.status != old_c['status']:
                    raise Conflict('task state changed; explicit reactivation required')
                if task.completed and not old_t['completed']:
                    if crm_changed or c.latest != old_c['latest']:
                        raise Conflict('completion conflicts with crm changes')
                    if not task.final_verified or not task.content:
                        raise Conflict('completion snapshot not established')
                    if task.content != old_t['content'] or task.due != old_t['due']:
                        raise Conflict('content changed with completion; confirm final snapshot')
                    changes = self._completion_changes(task)
                    self._operation(c,task,changes,task)
                elif old_t['completed']:
                    # One-time upgrade of a previously synchronized completion.
                    # Only when both CRM fields and final action remain untouched.
                    if (not old_t.get('completed_at') and task.completed_at
                        and not crm_changed and c.latest == old_c['latest'] == old_t['content']
                        and task.content == old_t['content'] and task.due == old_t['due']
                        and task.completed):
                        self._operation(c, task, self._completion_changes(task), task)
                        continue
                    if crm_changed or apple_changed:
                        raise Conflict('completed plan changed; new plan or reopen needs confirmation')
                    self._event(c.id,'unchanged_completed')
                elif crm_changed and apple_changed:
                    content,due = self._parts(c)
                    if [content,due] != [task.content,task.due]:
                        raise Conflict('both sides changed')
                    self._baseline(c,task)
                    self._event(c.id,'converged')
                elif crm_changed:
                    content,due=self._parts(c)
                    parsed = parse(c.plan, anchor=date.fromisoformat(c.anchor) if c.anchor else None, today=self.today)
                    if parsed['kind'] == 'relative' and c.anchor == old_c['anchor']:
                        raise Conflict('new relative plan lacks a new anchor')
                    desired=Task(task.id,c.id,content,due)
                    self._operation(c,desired,{},task)
                elif apple_changed:
                    if not task.content:
                        raise Conflict('empty task content')
                    self._operation(c,task,{'plan':plan_text(task)},task)
                else:
                    # Unrelated changes such as latest follow-up are new baselines,
                    # never written back by ordinary plan synchronization.
                    self._baseline(c,task)
                    self._event(c.id,'unchanged')
            except Conflict:
                self._event(c.id,'needs_confirmation')
            except Uncertain:
                self._event(c.id,'result_unknown')
        return self.events
