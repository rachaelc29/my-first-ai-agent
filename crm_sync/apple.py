import json
from pathlib import Path
import subprocess
from dataclasses import asdict
from .model import Task, Conflict, Uncertain

class AppleReminders:
    def __init__(self, list_id, bindings, state_dir):
        self.list_id, self.bindings = list_id, bindings
        self.binary = Path.home() / 'Library/Application Support/PropertyCRMSync/RemindersBridge.app/Contents/MacOS/RemindersBridge'
        self.quarantine = Path(state_dir) / 'uncertain-creations.json'
        self.quarantine.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    def call(self, payload):
        try:
            result = subprocess.run([str(self.binary)],input=json.dumps(payload),text=True,capture_output=True,timeout=150)
            body = json.loads(result.stdout)
        except Exception:
            raise Uncertain('local bridge result unavailable') from None
        if not body.get('ok'):
            raise Conflict('local bridge rejected operation')
        return body['result']

    def bind(self, tid, cid):
        self.bindings[tid] = cid

    def find(self, tid):
        if tid not in self.bindings:
            raise Conflict('customer binding unknown')
        value = self.call({'command':'get','list_id':self.list_id,'task_id':tid,'customer_id':self.bindings[tid]})
        return Task(**value) if value else None

    def put(self, task, expected=None):
        self.bindings[task.id] = task.customer_id
        blocked = json.loads(self.quarantine.read_text()) if self.quarantine.exists() else []
        if expected is None and task.id in blocked:
            raise Conflict('uncertain create requires manual reconciliation')
        # Mark before launch. If process/response fails, never blindly retry create.
        if expected is None:
            blocked.append(task.id)
            self.quarantine.write_text(json.dumps(blocked));self.quarantine.chmod(0o600)
        value = self.call({'command':'put','list_id':self.list_id,'task_id':task.id,'customer_id':task.customer_id,
                           'task':asdict(task),'expected':expected})
        if expected is None:
            blocked.remove(task.id);self.quarantine.write_text(json.dumps(blocked))
        return Task(**value)
