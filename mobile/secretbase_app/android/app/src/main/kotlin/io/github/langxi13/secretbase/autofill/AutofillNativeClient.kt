package io.github.langxi13.secretbase.autofill

import org.json.JSONArray
import org.json.JSONObject

internal data class NativeAutofillField(
    val name: String,
    val hidden: Boolean,
    val copyable: Boolean,
)

internal data class NativeAutofillCandidate(
    val entryId: String,
    val title: String,
    val usernamePreview: String,
    val usernameField: String?,
    val passwordField: String,
    val fields: List<NativeAutofillField>,
    val matched: Boolean,
    val matchLabel: String,
    val mappingConfident: Boolean,
)

internal data class NativeAutofillOpenResult(
    val sessionToken: String,
    val targetLabel: String,
    val candidates: List<NativeAutofillCandidate>,
    val truncated: Boolean,
)

internal data class NativeAutofillFillValues(
    val title: String,
    val username: String,
    val password: String,
)

internal data class NativeAutofillSaveResult(
    val revision: Long,
    val message: String,
)

internal class AutofillNativeException(
    val code: String,
    override val message: String,
    val retryable: Boolean,
) : Exception(message)

internal object AutofillNativeClient {
    fun openWithCredential(
        dataRoot: String,
        credential: ByteArray,
        targetJson: String,
    ): NativeAutofillOpenResult = parseOpen(
        data(AutofillNativeBridge.openWithCredential(dataRoot, credential, targetJson)),
    )

    fun openWithPassword(
        dataRoot: String,
        passwordUtf8: ByteArray,
        targetJson: String,
    ): NativeAutofillOpenResult = parseOpen(
        data(AutofillNativeBridge.openWithPassword(dataRoot, passwordUtf8, targetJson)),
    )

    fun select(
        sessionToken: String,
        entryId: String,
        usernameField: String?,
        passwordField: String,
        rememberBinding: Boolean,
    ): NativeAutofillFillValues {
        val selection = JSONObject()
            .put("entry_id", entryId)
            .putNullable("username_field", usernameField)
            .put("password_field", passwordField)
            .put("remember_binding", rememberBinding)
        val value = data(AutofillNativeBridge.select(sessionToken, selection.toString()))
        return NativeAutofillFillValues(
            title = value.getString("title"),
            username = value.optString("username"),
            password = value.getString("password"),
        )
    }

    fun cancel(sessionToken: String) {
        runCatching { data(AutofillNativeBridge.cancel(sessionToken)) }
    }

    fun saveWithCredential(
        dataRoot: String,
        credential: ByteArray,
        draftJson: String,
    ): NativeAutofillSaveResult = parseSave(
        data(AutofillNativeBridge.saveWithCredential(dataRoot, credential, draftJson)),
    )

    fun saveWithPassword(
        dataRoot: String,
        passwordUtf8: ByteArray,
        draftJson: String,
    ): NativeAutofillSaveResult = parseSave(
        data(AutofillNativeBridge.saveWithPassword(dataRoot, passwordUtf8, draftJson)),
    )

    private fun data(content: String): JSONObject {
        val payload = runCatching { JSONObject(content) }.getOrElse {
            throw AutofillNativeException(
                "AUTOFILL_NATIVE_FAILED",
                "自动填充返回了无效结果",
                true,
            )
        }
        if (payload.optBoolean("ok")) return payload.getJSONObject("data")
        val error = payload.optJSONObject("error")
        throw AutofillNativeException(
            error?.optString("code").orEmpty().ifBlank { "AUTOFILL_NATIVE_FAILED" },
            error?.optString("message").orEmpty().ifBlank { "自动填充失败，请重试" },
            error?.optBoolean("retryable") == true,
        )
    }

    private fun parseOpen(value: JSONObject): NativeAutofillOpenResult =
        NativeAutofillOpenResult(
            sessionToken = value.getString("session_token"),
            targetLabel = value.getString("target_label"),
            candidates = value.getJSONArray("candidates").mapObjects(::parseCandidate),
            truncated = value.optBoolean("truncated"),
        )

    private fun parseCandidate(value: JSONObject): NativeAutofillCandidate =
        NativeAutofillCandidate(
            entryId = value.getString("entry_id"),
            title = value.getString("title"),
            usernamePreview = value.optString("username_preview"),
            usernameField = value.optionalString("username_field"),
            passwordField = value.getString("password_field"),
            fields = value.getJSONArray("fields").mapObjects { field ->
                NativeAutofillField(
                    name = field.getString("name"),
                    hidden = field.optBoolean("hidden"),
                    copyable = field.optBoolean("copyable"),
                )
            },
            matched = value.optBoolean("matched"),
            matchLabel = value.optString("match_label"),
            mappingConfident = value.optBoolean("mapping_confident"),
        )

    private fun parseSave(value: JSONObject): NativeAutofillSaveResult =
        NativeAutofillSaveResult(
            revision = value.optLong("revision"),
            message = value.optString("message"),
        )

    private fun <T> JSONArray.mapObjects(transform: (JSONObject) -> T): List<T> =
        List(length()) { index -> transform(getJSONObject(index)) }

    private fun JSONObject.optionalString(name: String): String? =
        if (isNull(name)) null else optString(name).takeIf { it.isNotEmpty() }

    private fun JSONObject.putNullable(name: String, value: String?): JSONObject =
        if (value == null) put(name, JSONObject.NULL) else put(name, value)
}
