#!/usr/bin/env bash
# Install the APK on an emulator, start it, and check the DJ comes up and serves its page.
set -u
adb install -r -g party-dj.apk
adb logcat -c
adb shell am start -n com.party.dj/.MainActivity
# The app first asks for the party's details: fill in a Diwali party, like a person would.
adb forward tcp:8765 tcp:8765
for i in $(seq 1 60); do
  if adb logcat -d -s python.stdout:I | grep -q "Setup page is open"; then break; fi
  sleep 3
done
sleep 3
adb exec-out screencap -p > setup.png || true
curl -s -m 20 -X POST -d "kind=diwali&host=Amit&co_host=Priya&city=Melbourne&date=$(date +%F)&start=19:00&hours=5&moment=21:00" \
  http://localhost:8765/setup | head -c 200
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
