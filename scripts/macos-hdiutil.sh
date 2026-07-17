#!/usr/bin/env bash

SECRETBASE_HDIUTIL_RETRY_ATTEMPTS="${SECRETBASE_HDIUTIL_RETRY_ATTEMPTS:-3}"
SECRETBASE_HDIUTIL_RETRY_DELAY_SECONDS="${SECRETBASE_HDIUTIL_RETRY_DELAY_SECONDS:-2}"

secretbase_hdiutil_retry_wait() {
    local attempt=$1
    local delay=$((attempt * SECRETBASE_HDIUTIL_RETRY_DELAY_SECONDS))
    if ((delay > 0)); then
        sleep "$delay"
    fi
}

secretbase_hdiutil_create_dmg() {
    local source_root=$1
    local volume_name=$2
    local output_path=$3
    local attempt status=1

    for ((attempt = 1; attempt <= SECRETBASE_HDIUTIL_RETRY_ATTEMPTS; attempt++)); do
        rm -f "$output_path"
        echo "Creating macOS DMG (attempt ${attempt}/${SECRETBASE_HDIUTIL_RETRY_ATTEMPTS})"
        if hdiutil create \
            -volname "$volume_name" \
            -srcfolder "$source_root" \
            -ov \
            -format UDZO \
            "$output_path"; then
            return 0
        else
            status=$?
        fi
        echo "hdiutil create failed with exit code $status" >&2
        if ((attempt < SECRETBASE_HDIUTIL_RETRY_ATTEMPTS)); then
            secretbase_hdiutil_retry_wait "$attempt"
        fi
    done
    return "$status"
}

secretbase_hdiutil_attach_dmg() {
    local image_path=$1
    local mount_root=$2
    local attempt status=1

    mkdir -p "$mount_root"
    for ((attempt = 1; attempt <= SECRETBASE_HDIUTIL_RETRY_ATTEMPTS; attempt++)); do
        hdiutil detach -force "$mount_root" >/dev/null 2>&1 || true
        echo "Attaching macOS DMG (attempt ${attempt}/${SECRETBASE_HDIUTIL_RETRY_ATTEMPTS})"
        if hdiutil attach \
            -readonly \
            -nobrowse \
            -mountpoint "$mount_root" \
            "$image_path"; then
            return 0
        else
            status=$?
        fi
        echo "hdiutil attach failed with exit code $status" >&2
        if ((attempt < SECRETBASE_HDIUTIL_RETRY_ATTEMPTS)); then
            secretbase_hdiutil_retry_wait "$attempt"
        fi
    done
    return "$status"
}

secretbase_hdiutil_detach() {
    local mount_root=$1
    local attempt status=1

    for ((attempt = 1; attempt <= SECRETBASE_HDIUTIL_RETRY_ATTEMPTS; attempt++)); do
        echo "Detaching macOS DMG (attempt ${attempt}/${SECRETBASE_HDIUTIL_RETRY_ATTEMPTS})"
        if hdiutil detach "$mount_root"; then
            return 0
        else
            status=$?
        fi
        echo "hdiutil detach failed with exit code $status" >&2
        if ((attempt < SECRETBASE_HDIUTIL_RETRY_ATTEMPTS)); then
            secretbase_hdiutil_retry_wait "$attempt"
        fi
    done
    return "$status"
}
