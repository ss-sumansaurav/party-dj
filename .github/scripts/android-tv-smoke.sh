#!/usr/bin/env bash
# Android TV: install, check it's on the TV home screen, start a party and drive it with the remote's keys.
set -u
adb install -r -g party-dj.apk
adb shell cmd package query-activities -a android.intent.action.MAIN -c android.intent.category.LEANBACK_LAUNCHER | grep -q com.party.dj && tvhome=1 || tvhome=0
adb logcat -c
adb shell am start -n com.party.dj/.MainActivity
adb forward tcp:8765 tcp:8765
for i in $(seq 1 90); do
  if adb logcat -d -s python.stdout:I | grep -q "Setup page is open"; then break; fi
  sleep 3
done
sleep 3
adb exec-out screencap -p > tv-setup.png || true
curl -s -m 20 -X POST -d "kind=diwali&host=Amit&co_host=Priya&city=Melbourne&date=$(date +%F)&start=19:00&hours=5&moment=21:00" \
  http://localhost:8765/setup | head -c 100
ok=0
for i in $(seq 1 120); do
  if adb logcat -d -s python.stdout:I | grep -q "page: players ready"; then ok=1; break; fi
  if adb logcat -d | grep -q "FATAL EXCEPTION"; then break; fi
  sleep 5
done
sleep 3
adb exec-out screencap -p > tv-dj.png || true
# The remote: OK on the START button (in focus by itself), then move around with the arrows.
adb shell input keyevent KEYCODE_DPAD_CENTER
started=0
for i in $(seq 1 20); do
  if adb logcat -d -s python.stdout:I | grep -q "Party started"; then started=1; break; fi
  sleep 2
done
for k in DPAD_DOWN DPAD_DOWN DPAD_RIGHT DPAD_DOWN; do adb shell input keyevent KEYCODE_$k; sleep 1; done
sleep 2
adb exec-out screencap -p > tv-remote.png || true
moves=$(adb logcat -d -s python.stdout:I | grep -c "page: focus:" || true)
log=$( { adb logcat -d -s python.stdout python.stderr AndroidRuntime:E | grep -v "Finding songs" | tail -60; } | sed 's/%/%25/g' | awk '{printf "%s%%0A", $0}')
echo "::notice title=TV log::${log}"
echo "::notice title=TV checks::tv_home=${tvhome} players=${ok} started_by_remote=${started} focus_moves=${moves}"
[ "$tvhome" = 1 ] && [ "$ok" = 1 ] && [ "$started" = 1 ] && [ "$moves" -ge 3 ]
