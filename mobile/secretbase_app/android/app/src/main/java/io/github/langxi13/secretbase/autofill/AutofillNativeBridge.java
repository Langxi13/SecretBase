package io.github.langxi13.secretbase.autofill;

import androidx.annotation.Keep;

@Keep
public final class AutofillNativeBridge {
    static {
        System.loadLibrary("secretbase_mobile");
    }

    private AutofillNativeBridge() {}

    public static native String openWithCredential(
            String dataRoot,
            byte[] credential,
            String targetJson);

    public static native String openWithPassword(
            String dataRoot,
            byte[] passwordUtf8,
            String targetJson);

    public static native String select(String sessionToken, String selectionJson);

    public static native String cancel(String sessionToken);

    public static native String saveWithCredential(
            String dataRoot,
            byte[] credential,
            String draftJson);

    public static native String saveWithPassword(
            String dataRoot,
            byte[] passwordUtf8,
            String draftJson);
}
