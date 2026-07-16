package io.github.langxi13.secretbase.autofill

import android.annotation.SuppressLint
import android.app.PendingIntent
import android.content.Intent
import android.graphics.drawable.Icon
import android.os.Build
import android.os.CancellationSignal
import android.service.autofill.AutofillService
import android.service.autofill.FillCallback
import android.service.autofill.FillRequest
import android.service.autofill.FillResponse
import android.service.autofill.InlinePresentation
import android.service.autofill.SaveCallback
import android.service.autofill.SaveInfo
import android.service.autofill.SaveRequest
import android.widget.RemoteViews
import androidx.autofill.inline.UiVersions
import androidx.autofill.inline.v1.InlineSuggestionUi
import io.github.langxi13.secretbase.R
import java.util.concurrent.atomic.AtomicInteger

class SecretBaseAutofillService : AutofillService() {
    private val parser = AutofillRequestParser()
    private val requestCodes = AtomicInteger(10_000)

    override fun onFillRequest(
        request: FillRequest,
        cancellationSignal: CancellationSignal,
        callback: FillCallback,
    ) {
        if (cancellationSignal.isCanceled) {
            callback.onSuccess(null)
            return
        }
        val parsed = request.fillContexts.lastOrNull()?.structure?.let(parser::parse)
        if (parsed == null || !isAllowed(parsed)) {
            callback.onSuccess(null)
            return
        }
        try {
            if (parsed.passwordIsNew) {
                callback.onSuccess(
                    FillResponse.Builder().apply {
                        buildSaveInfo(parsed)?.let(::setSaveInfo)
                    }.build(),
                )
                return
            }
            val authIntent = AutofillIntents.fillIntent(
                Intent(this, SecretBaseAutofillActivity::class.java),
                parsed,
            )
            val pendingIntent = PendingIntent.getActivity(
                this,
                nextRequestCode(),
                authIntent,
                PendingIntent.FLAG_CANCEL_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
            val presentation = suggestionPresentation(
                title = "使用 SecretBase",
                subtitle = parsed.targetLabel,
            )
            val response = FillResponse.Builder().apply {
                buildSaveInfo(parsed)?.let(::setSaveInfo)
                val inline = buildInlinePresentation(request, pendingIntent, parsed.targetLabel)
                @Suppress("DEPRECATION")
                if (inline != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                    setAuthentication(
                        parsed.authenticationIds,
                        pendingIntent.intentSender,
                        presentation,
                        inline,
                    )
                } else {
                    setAuthentication(
                        parsed.authenticationIds,
                        pendingIntent.intentSender,
                        presentation,
                    )
                }
            }.build()
            if (cancellationSignal.isCanceled) {
                callback.onSuccess(null)
            } else {
                callback.onSuccess(response)
            }
        } catch (_: Exception) {
            callback.onFailure("SecretBase 暂时无法处理自动填充请求")
        }
    }

    override fun onSaveRequest(request: SaveRequest, callback: SaveCallback) {
        val preferences = AutofillPreferences(this)
        if (!preferences.savePromptsEnabled) {
            callback.onSuccess()
            return
        }
        val parsed = parser.parseForSave(request.fillContexts.map { it.structure })
        if (parsed == null || !isAllowed(parsed)) {
            callback.onSuccess()
            return
        }
        val token = PendingAutofillSaveStore.put(parsed)
        if (token == null) {
            callback.onSuccess()
            return
        }
        val intent = Intent(this, SecretBaseAutofillActivity::class.java).apply {
            action = AutofillIntents.ACTION_SAVE
            putExtra(AutofillIntents.EXTRA_SAVE_TOKEN, token)
            putExtra(AutofillIntents.EXTRA_PACKAGE_NAME, parsed.packageName)
            putExtra(AutofillIntents.EXTRA_WEB_DOMAIN, parsed.webDomain)
            putExtra(AutofillIntents.EXTRA_WEB_SCHEME, parsed.webScheme)
        }
        val pendingIntent = PendingIntent.getActivity(
            this,
            nextRequestCode(),
            intent,
            PendingIntent.FLAG_CANCEL_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        callback.onSuccess(pendingIntent.intentSender)
    }

    private fun isAllowed(request: ParsedAutofillRequest): Boolean {
        if (request.packageName == packageName) return false
        return !AutofillPreferences(this).isBlocked(request.targetKey)
    }

    private fun buildSaveInfo(request: ParsedAutofillRequest): SaveInfo? {
        if (!AutofillPreferences(this).savePromptsEnabled) return null
        var type = SaveInfo.SAVE_DATA_TYPE_PASSWORD
        val optional = request.usernameId?.let {
            type = type or SaveInfo.SAVE_DATA_TYPE_USERNAME
            arrayOf(it)
        }
        return SaveInfo.Builder(type, arrayOf(request.passwordId)).apply {
            if (!optional.isNullOrEmpty()) setOptionalIds(optional)
        }.build()
    }

    private fun suggestionPresentation(title: String, subtitle: String): RemoteViews =
        RemoteViews(packageName, R.layout.autofill_suggestion).apply {
            setTextViewText(R.id.autofill_suggestion_title, title)
            setTextViewText(R.id.autofill_suggestion_subtitle, subtitle.take(120))
        }

    @SuppressLint("RestrictedApi")
    private fun buildInlinePresentation(
        request: FillRequest,
        pendingIntent: PendingIntent,
        targetLabel: String,
    ): InlinePresentation? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R ||
            !AutofillPreferences(this).inlineSuggestionsEnabled
        ) {
            return null
        }
        val inlineRequest = request.inlineSuggestionsRequest ?: return null
        if (inlineRequest.maxSuggestionCount <= 0) return null
        val spec = inlineRequest.inlinePresentationSpecs.firstOrNull() ?: return null
        if (!UiVersions.getVersions(spec.style).contains(UiVersions.INLINE_UI_VERSION_1)) {
            return null
        }
        return try {
            val content = InlineSuggestionUi.newContentBuilder(pendingIntent)
                .setTitle("SecretBase")
                .setSubtitle(targetLabel.take(80))
                .setContentDescription("使用 SecretBase 自动填充")
                .setStartIcon(Icon.createWithResource(this, R.mipmap.ic_launcher_round))
                .build()
            InlinePresentation(content.slice, spec, false)
        } catch (_: Exception) {
            null
        }
    }

    private fun nextRequestCode(): Int = requestCodes.updateAndGet { current ->
        if (current >= Int.MAX_VALUE - 1) 10_000 else current + 1
    }
}
