package io.github.langxi13.secretbase.autofill

import android.content.ComponentName
import android.content.Intent
import android.provider.Settings
import android.view.autofill.AutofillManager
import androidx.core.net.toUri
import io.github.langxi13.secretbase.MainActivity
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

internal class AutofillPlatform(
    private val activity: MainActivity,
) {
    fun handle(call: MethodCall, result: MethodChannel.Result): Boolean {
        when (call.method) {
            "getAutofillStatus" -> result.success(status())
            "requestAutofillService" -> {
                requestService()
                result.success(null)
            }
            "openAutofillSettings" -> {
                openSettings()
                result.success(null)
            }
            "setAutofillPreference" -> {
                setPreference(
                    call.argument<String>("name").orEmpty(),
                    call.argument<Boolean>("value") == true,
                    result,
                )
            }
            "clearAutofillBlockedTargets" -> {
                AutofillPreferences(activity).clearBlockedTargets()
                result.success(status())
            }
            "consumeAutofillVaultChanged" ->
                result.success(AutofillVaultChangeNotifier.consumeVaultChanged())
            else -> return false
        }
        return true
    }

    private fun status(): Map<String, Any> {
        val manager = activity.getSystemService(AutofillManager::class.java)
        val preferences = AutofillPreferences(activity)
        return mapOf(
            "supported" to (manager?.isAutofillSupported == true),
            "enabled" to isSecretBaseServiceEnabled(),
            "savePromptsEnabled" to preferences.savePromptsEnabled,
            "inlineSuggestionsEnabled" to preferences.inlineSuggestionsEnabled,
            "blockedTargetCount" to preferences.blockedTargetCount(),
        )
    }

    private fun isSecretBaseServiceEnabled(): Boolean {
        val configured = Settings.Secure.getString(
            activity.contentResolver,
            SECURE_AUTOFILL_SERVICE,
        ).orEmpty()
        val expected = ComponentName(activity, SecretBaseAutofillService::class.java)
        return configured
            .split(':')
            .mapNotNull(ComponentName::unflattenFromString)
            .any { it == expected }
    }

    private fun requestService() {
        val intent = Intent(Settings.ACTION_REQUEST_SET_AUTOFILL_SERVICE).apply {
            data = "package:${activity.packageName}".toUri()
        }
        runCatching { activity.startActivity(intent) }.onFailure { openSettings() }
    }

    private fun openSettings() {
        val intent = Intent(ACTION_AUTOFILL_SETTINGS)
        runCatching { activity.startActivity(intent) }.onFailure {
            activity.startActivity(Intent(Settings.ACTION_SETTINGS))
        }
    }

    private fun setPreference(
        name: String,
        value: Boolean,
        result: MethodChannel.Result,
    ) {
        val preferences = AutofillPreferences(activity)
        when (name) {
            "savePrompts" -> preferences.savePromptsEnabled = value
            "inlineSuggestions" -> preferences.inlineSuggestionsEnabled = value
            else -> {
                result.error("AUTOFILL_PREFERENCE_INVALID", "自动填充设置无效", null)
                return
            }
        }
        result.success(status())
    }

    companion object {
        private const val ACTION_AUTOFILL_SETTINGS = "android.settings.AUTOFILL_SETTINGS"
        private const val SECURE_AUTOFILL_SERVICE = "autofill_service"
    }
}
