package io.github.langxi13.secretbase.autofill

import android.content.Intent
import android.view.autofill.AutofillId
import org.json.JSONObject

internal object AutofillIntents {
    const val ACTION_FILL = "io.github.langxi13.secretbase.action.AUTOFILL_FILL"
    const val ACTION_SAVE = "io.github.langxi13.secretbase.action.AUTOFILL_SAVE"
    const val EXTRA_PACKAGE_NAME = "autofill.package_name"
    const val EXTRA_WEB_DOMAIN = "autofill.web_domain"
    const val EXTRA_WEB_SCHEME = "autofill.web_scheme"
    const val EXTRA_USERNAME_ID = "autofill.username_id"
    const val EXTRA_PASSWORD_ID = "autofill.password_id"
    const val EXTRA_SAVE_TOKEN = "autofill.save_token"

    fun fillIntent(
        intent: Intent,
        request: ParsedAutofillRequest,
    ): Intent = intent.apply {
        action = ACTION_FILL
        putExtra(EXTRA_PACKAGE_NAME, request.packageName)
        putExtra(EXTRA_WEB_DOMAIN, request.webDomain)
        putExtra(EXTRA_WEB_SCHEME, request.webScheme)
        putExtra(EXTRA_USERNAME_ID, request.usernameId)
        putExtra(EXTRA_PASSWORD_ID, request.passwordId)
    }

    fun targetJson(intent: Intent): String = JSONObject()
        .put("package_name", intent.getStringExtra(EXTRA_PACKAGE_NAME).orEmpty())
        .putNullable("web_domain", intent.getStringExtra(EXTRA_WEB_DOMAIN))
        .putNullable("web_scheme", intent.getStringExtra(EXTRA_WEB_SCHEME))
        .toString()

    @Suppress("DEPRECATION")
    fun usernameId(intent: Intent): AutofillId? =
        intent.getParcelableExtra(EXTRA_USERNAME_ID)

    @Suppress("DEPRECATION")
    fun passwordId(intent: Intent): AutofillId? =
        intent.getParcelableExtra(EXTRA_PASSWORD_ID)

    private fun JSONObject.putNullable(name: String, value: String?): JSONObject =
        if (value == null) put(name, JSONObject.NULL) else put(name, value)
}
