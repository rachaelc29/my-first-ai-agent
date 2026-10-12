#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo 'This build requires macOS and Apple Command Line Tools.'
  exit 1
fi
xcrun --find swiftc >/dev/null
app_path="$HOME/Library/Application Support/PropertyCRMSync/RemindersBridge.app"
mkdir -p "$app_path/Contents/MacOS"
cp mac/Info.plist "$app_path/Contents/Info.plist"
xcrun swiftc -swift-version 5 mac/RemindersBridge.swift -framework EventKit -o "$app_path/Contents/MacOS/RemindersBridge"
codesign --force --sign - "$app_path" >/dev/null
echo 'Mac bridge built locally. No reminder has been accessed.'
