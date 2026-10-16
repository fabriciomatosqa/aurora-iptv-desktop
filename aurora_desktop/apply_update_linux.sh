#!/bin/sh
# Detached DEB updater. Runs as the current desktop user, not as root.
# Root permission is requested only for apt-get through PolicyKit (pkexec).
# All paths arrive as positional arguments and are never eval'ed.
set -u
PARENT_PID="$1"
PACKAGE="$2"
EXECUTABLE="$3"
STATUS="$4"
LOG="$5"
VERSION="$6"

write_status() {
  # Input values are validated by the Python launcher; diagnostic text is fixed.
  printf '{"status":"%s","exit_code":%s,"version":"%s"}\n' "$1" "$2" "$VERSION" > "$STATUS" || :
}
restart_app() {
  if [ -x "$EXECUTABLE" ]; then
    # The helper must not wait for the GUI, otherwise it could not finish.
    "$EXECUTABLE" >/dev/null 2>&1 &
  fi
}
write_status waiting 0
tries=0
while kill -0 "$PARENT_PID" 2>/dev/null; do
  tries=$((tries+1))
  if [ "$tries" -ge 240 ]; then
    write_status failed 20
    exit 20
  fi
  sleep 0.5
done

if [ ! -f "$PACKAGE" ] || [ ! -x "$EXECUTABLE" ]; then
  write_status failed 21
  restart_app
  exit 21
fi

if ! command -v pkexec >/dev/null 2>&1; then
  write_status failed 24
  restart_app
  exit 24
fi

write_status installing 0
# pkexec talks to the desktop's Polkit authentication agent if elevation is
# required. A failed/cancelled authentication must never silently claim success.
if pkexec /usr/bin/apt-get install -y "$PACKAGE" >"$LOG" 2>&1; then
  write_status ok 0
  restart_app
  exit 0
else
  result=$?
  write_status failed "$result"
  restart_app
  exit "$result"
fi
