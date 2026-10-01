#!/bin/sh
set -eu
cd "$(dirname "$0")/../mobile_web"
if ! command -v flutter >/dev/null 2>&1; then
  if [ -x "$HOME/sdks/flutter/bin/flutter" ]; then
    export PATH="$HOME/sdks/flutter/bin:$PATH"
  else
    echo "Install Flutter, then re-run this script." >&2
    exit 1
  fi
fi
flutter create --platforms=android,ios,web --project-name vibeprompt .
flutter pub get
