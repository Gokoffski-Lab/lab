#!/usr/bin/env bash
# Run a Fiji script headless via Fiji's bundled JVM (bypasses the GUI-mode
# fiji-windows-x64.exe launcher, which swallows stdout and exit codes).
# Usage: fiji_headless.sh <script.groovy> "<key='value',...>"
FIJI="${FIJI_DIR:-$HOME/Documents/Fiji}"
JAVA=$(ls -d "$FIJI"/java/win64/*/bin/java.exe | head -1)
exec "$JAVA" -Xmx${FIJI_MEM:-8g} -XX:+UseG1GC \
  --add-opens=java.base/java.lang=ALL-UNNAMED --enable-native-access=ALL-UNNAMED \
  -Djava.awt.headless=true -Dpython.cachedir.skip=true \
  -Dplugins.dir="$FIJI" -Dimagej.dir="$FIJI" -Dij.dir="$FIJI" -Dfiji.dir="$FIJI" \
  -Djava.library.path="$FIJI/lib/win64" -Dscijava.context.strict=false \
  -Dscijava.app.directory="$FIJI" -Dscijava.log.level=warn \
  -cp "$FIJI/jars/*;$FIJI/jars/bio-formats/*;$FIJI/plugins/*" \
  net.imagej.Main --headless --run "$1" "$2"
