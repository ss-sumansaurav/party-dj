#!/usr/bin/env bash
# Install the APK on an emulator, start it, and check the DJ comes up and serves its page.
set -u
adb install -r -g party-dj.apk
adb logcat -c
adb shell am start -n com.party.dj/.MainActivity
ok=0
for i in $(seq 1 120); do
  if adb logcat -d -s python.stdout:I | grep -q "The DJ page is open"; then ok=1; break; fi
  if adb logcat -d | grep -q "FATAL EXCEPTION"; then break; fi
  sleep 5
done
adb forward tcp:8765 tcp:8765
state=$(curl -s -m 10 http://localhost:8765/state || true)
songs=$(curl -s -m 10 http://localhost:8765/api/songs | head -c 200 || true)
started=$(curl -s -m 30 -X POST http://localhost:8765/start || true)
next=$(curl -s -m 120 -X POST http://localhost:8765/next | head -c 600 || true)
sleep 8
adb exec-out screencap -p > screen.png || true
log=$( { adb logcat -d -s python.stdout python.stderr AndroidRuntime:E chromium:I | tail -80; } | sed 's/%/%25/g' | awk '{printf "%s%%0A", $0}')
echo "::notice title=App log::${log}"
echo "::notice title=Page checks::state=${state}%0Asongs=${songs}%0Astart=${started}%0Anext=${next}"
[ "$ok" = 1 ] && [ -n "$state" ] && echo "$next" | grep -q '"vid"'
