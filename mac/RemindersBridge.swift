import Foundation
import EventKit

// Local test bridge. Only a list named CRM-SYNC-TEST is eligible for writes.
struct BridgeFailure: Error { let message: String }
let store = EKEventStore()
func fail(_ message: String) throws -> Never { throw BridgeFailure(message: message) }
func authorize() throws {
    var done = false
    var granted = false
    if #available(macOS 14.0, *) {
        store.requestFullAccessToReminders { ok, _ in granted = ok; done = true }
    } else {
        store.requestAccess(to: .reminder) { ok, _ in granted = ok; done = true }
    }
    let deadline = Date().addingTimeInterval(120)
    while !done && Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.05)) }
    if !granted { try fail("reminders_permission_required") }
}
func required(_ input: [String: Any], _ name: String) throws -> String {
    guard let value = input[name] as? String, !value.isEmpty else { try fail("missing_input") }
    return value
}
func calendar(_ input: [String: Any]) throws -> EKCalendar {
    let id = try required(input, "list_id")
    guard let c = store.calendars(for: .reminder).first(where: { $0.calendarIdentifier == id }),
          c.title == "CRM-SYNC-TEST", c.allowsContentModifications else { try fail("test_list_not_available") }
    return c
}
func reminders(_ calendar: EKCalendar) throws -> [EKReminder] {
    var done = false
    var items: [EKReminder] = []
    store.fetchReminders(matching: store.predicateForReminders(in: [calendar])) { results in
        items = results ?? []; done = true
    }
    let deadline = Date().addingTimeInterval(30)
    while !done && Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.05)) }
    if !done { try fail("read_timeout") }
    return items
}
func dateText(_ r: EKReminder) -> Any {
    guard let d = r.dueDateComponents, let year = d.year, let month = d.month, let day = d.day else { return NSNull() }
    return String(format: "%04d-%02d-%02d", year, month, day)
}
func marker(_ id: String, _ customer: String) -> String {
    return "\n\n[CRM_SYNC_TASK:\(id);CUSTOMER:\(customer)]"
}
func serialize(_ r: EKReminder, taskID: String, customerID: String) throws -> [String: Any] {
    let suffix = marker(taskID, customerID)
    guard let body = r.notes, body.hasSuffix(suffix) else { try fail("binding_invalid") }
    let extra = String(body.dropLast(suffix.count))
    let content = r.title + (extra.isEmpty ? "" : "\n" + extra)
    var verified = true
    if r.isCompleted {
        // EventKit's normal completion write can stamp modification a few ms
        // after completion. Allow at most 10ms of bookkeeping drift. Python
        // additionally requires unchanged content/date before automatic writeback.
        if let completed = r.completionDate, let modified = r.lastModifiedDate {
            verified = modified.timeIntervalSince(completed) <= 0.010
        } else { verified = false }
    }
    let format = ISO8601DateFormatter()
    format.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    let completedAt: Any
    if let date = r.completionDate { completedAt = format.string(from: date) }
    else { completedAt = NSNull() }
    return ["id":taskID,"customer_id":customerID,"content":content,"due":dateText(r),
            "completed":r.isCompleted,"final_verified":verified,"completed_at":completedAt]
}
func bound(_ items: [EKReminder], id: String) throws -> EKReminder? {
    let needle = "[CRM_SYNC_TASK:\(id);CUSTOMER:"
    let found = items.filter { ($0.notes ?? "").contains(needle) }
    if found.count > 1 { try fail("duplicate_binding") }
    return found.first
}
func run(_ input: [String: Any]) throws -> Any {
    try authorize()
    let command = try required(input,"command")
    if command == "test_lists" {
        // Do not enumerate personal list names.
        return store.calendars(for: .reminder).filter { $0.title == "CRM-SYNC-TEST" }.map {
            ["id":$0.calendarIdentifier,"writable":$0.allowsContentModifications]
        }
    }
    let list = try calendar(input)
    let items = try reminders(list)
    if command == "completion_diagnostics" {
        // Only metadata of managed tasks inside the fixed TEST list.
        // No title, notes, client identifier, or personal list is returned.
        let format = ISO8601DateFormatter()
        format.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return items.filter { ($0.notes ?? "").contains("[CRM_SYNC_TASK:") }.map { r -> [String: Any] in
            var result: [String: Any] = ["completed": r.isCompleted]
            result["completion_time"] = r.completionDate.map { format.string(from: $0) } ?? "missing"
            result["last_modified_time"] = r.lastModifiedDate.map { format.string(from: $0) } ?? "missing"
            if let completed = r.completionDate, let modified = r.lastModifiedDate {
                result["modified_minus_completed_seconds"] = modified.timeIntervalSince(completed)
            }
            return result
        }
    }
    let taskID = try required(input,"task_id")
    let customer = try required(input,"customer_id")
    let existing = try bound(items,id:taskID)
    if command == "get" {
        if let r = existing { return try serialize(r,taskID:taskID,customerID:customer) }
        return NSNull()
    }
    if command != "put" { try fail("unknown_command") }
    guard let task = input["task"] as? [String: Any], let content = task["content"] as? String,
          !content.isEmpty, !content.contains("[CRM_SYNC_TASK:"),
          task["id"] as? String == taskID, task["customer_id"] as? String == customer else { try fail("task_invalid") }
    if let r = existing {
        guard let expected = input["expected"] as? [String:Any] else { try fail("creation_conflict") }
        let current = try serialize(r,taskID:taskID,customerID:customer)
        guard NSDictionary(dictionary:current).isEqual(to:expected) else { try fail("task_changed") }
    } else if !(input["expected"] is NSNull) { try fail("task_missing") }
    let r = existing ?? EKReminder(eventStore:store)
    r.calendar = list
    // Editable title and body together form the action content.
    let lines = content.components(separatedBy: "\n")
    r.title = lines[0]
    r.notes = lines.dropFirst().joined(separator:"\n") + marker(taskID,customer)
    if let text = task["due"] as? String {
        let pieces = text.split(separator:"-").compactMap { Int($0) }
        guard pieces.count == 3 else { try fail("date_invalid") }
        var components = DateComponents()
        components.calendar = Calendar(identifier:.gregorian)
        components.timeZone = TimeZone(identifier:"Australia/Melbourne")
        components.year = pieces[0]; components.month = pieces[1]; components.day = pieces[2]
        r.dueDateComponents = components
    } else { r.dueDateComponents = nil }
    r.isCompleted = task["completed"] as? Bool ?? false
    try store.save(r,commit:true)
    return try serialize(r,taskID:taskID,customerID:customer)
}
do {
    let bytes = FileHandle.standardInput.readDataToEndOfFile()
    guard let input = try JSONSerialization.jsonObject(with:bytes) as? [String:Any] else { try fail("invalid_request") }
    let result = try run(input)
    let output = try JSONSerialization.data(withJSONObject:["ok":true,"result":result],options:[.sortedKeys])
    FileHandle.standardOutput.write(output)
} catch {
    let message = (error as? BridgeFailure)?.message ?? "local_operation_failed"
    let output = try! JSONSerialization.data(withJSONObject:["ok":false,"error":message])
    FileHandle.standardOutput.write(output)
    exit(1)
}
