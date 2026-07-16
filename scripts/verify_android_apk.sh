#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <apk-path> [required-abis]" >&2
  echo "Example: $0 app-release.apk armeabi-v7a,arm64-v8a,x86_64" >&2
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 2
fi

apk_path=$1
required_abis=${2:-arm64-v8a}

if [[ ! -f "$apk_path" ]]; then
  echo "APK does not exist: $apk_path" >&2
  exit 1
fi

for command in unzip strings; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Required command is missing: $command" >&2
    exit 1
  fi
done

apkanalyzer=${APKANALYZER:-${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}/cmdline-tools/latest/bin/apkanalyzer}
if [[ ! -x "$apkanalyzer" ]]; then
  echo "apkanalyzer was not found; set APKANALYZER or ANDROID_SDK_ROOT" >&2
  exit 1
fi

unzip -tq "$apk_path" >/dev/null
archive_entries=$(unzip -Z1 "$apk_path")

IFS=',' read -r -a abi_list <<<"$required_abis"
for abi in "${abi_list[@]}"; do
  library_path="lib/$abi/libsecretbase_mobile.so"
  if ! grep -Fxq "$library_path" <<<"$archive_entries"; then
    echo "Required Rust library is missing: $library_path" >&2
    exit 1
  fi
done

manifest=$($apkanalyzer manifest print "$apk_path")
for expected in \
  'package="io.github.langxi13.secretbase"' \
  'android:minSdkVersion="29"' \
  'android:targetSdkVersion="36"' \
  'android:allowBackup="false"' \
  'android:usesCleartextTraffic="false"' \
  'android:networkSecurityConfig=' \
  'android.permission.USE_BIOMETRIC' \
  'android.permission.REQUEST_INSTALL_PACKAGES' \
  'androidx.core.content.FileProvider' \
  'android:grantUriPermissions="true"' \
  'android:enableOnBackInvokedCallback="true"'; do
  if ! grep -Fq "$expected" <<<"$manifest"; then
    echo "Manifest requirement is missing: $expected" >&2
    exit 1
  fi
done

if grep -Fq 'android:debuggable="true"' <<<"$manifest" && [[ "$apk_path" != *debug* ]]; then
  echo "Non-debug APK is marked debuggable" >&2
  exit 1
fi

temporary_dir=$(mktemp -d)
trap 'rm -rf "$temporary_dir"' EXIT
forbidden_build_pattern='(/home/[^/]+/(work|projects?)/|/Users/[^/]+/(work|projects?)/|/usr/local/[^/]*(Work|Project)[^/]*/|/root/\.(cargo|rustup)/)'
if [[ -n "${SECRETBASE_PRIVATE_SCAN_PATTERN:-}" ]]; then
  forbidden_build_pattern="(${forbidden_build_pattern}|${SECRETBASE_PRIVATE_SCAN_PATTERN})"
fi

for abi in "${abi_list[@]}"; do
  library_path="lib/$abi/libsecretbase_mobile.so"
  output_path="$temporary_dir/${abi//\//_}.so"
  unzip -p "$apk_path" "$library_path" >"$output_path"
  strings "$output_path" >"$output_path.strings"
  if grep -Eq "$forbidden_build_pattern" "$output_path.strings"; then
    echo "Rust library contains a private or machine-specific build path: $library_path" >&2
    exit 1
  fi
done

echo "Verified Android APK: $apk_path"
