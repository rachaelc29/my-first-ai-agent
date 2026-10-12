from dataclasses import dataclass, asdict
import hashlib
import json

@dataclass
class Customer:
    id: str
    plan: str
    latest: str = ''
    task_id: str = ''
    status: str = ''
    anchor: str = ''

@dataclass
class Task:
    id: str
    customer_id: str
    content: str
    due: str | None
    completed: bool = False
    # Set false if completion-time content cannot be established.
    final_verified: bool = True
    completed_at: str | None = None


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def plan_text(task):
    return (task.due + '，' if task.due else '') + task.content

def task_value(task):
    return [task.content, task.due, task.completed, task.final_verified, task.completed_at]

class Conflict(Exception):
    pass

class Uncertain(Exception):
    """Side effect may have happened. Requires reconcile, not blind retry."""

class MemoryCRM:
    def __init__(self, customers):
        self.customers = {c.id: c for c in customers}
        self.writes = []
    def list_customers(self):
        return list(self.customers.values())
    def get(self, cid):
        return self.customers[cid]
    def update(self, cid, changes, expected):
        c = self.get(cid)
        if asdict(c) != expected:
            raise Conflict('crm changed before write')
        allowed = {'plan', 'latest', 'task_id', 'status', 'anchor'}
        if set(changes) - allowed:
            raise ValueError('field not permitted')
        for key, value in changes.items():
            setattr(c, key, value)
        self.writes.append((cid, dict(changes)))
        return c

class MemoryReminders:
    def __init__(self):
        self.tasks = {}
        self.writes = []
    def find(self, tid):
        return self.tasks.get(tid)
    def put(self, task, expected=None):
        existing = self.find(task.id)
        if expected is None and existing:
            raise Conflict('task already exists')
        if expected is not None and (not existing or asdict(existing) != expected):
            raise Conflict('task changed before write')
        self.tasks[task.id] = Task(**asdict(task))
        self.writes.append(task.id)
        return self.tasks[task.id]
