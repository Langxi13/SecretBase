package io.github.langxi13.secretbase.autofill

import android.content.Context
import androidx.core.content.edit

internal class AutofillPreferences(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences(
        PREFERENCES_NAME,
        Context.MODE_PRIVATE,
    )

    var savePromptsEnabled: Boolean
        get() = preferences.getBoolean(KEY_SAVE_PROMPTS, true)
        set(value) {
            preferences.edit { putBoolean(KEY_SAVE_PROMPTS, value) }
        }

    var inlineSuggestionsEnabled: Boolean
        get() = preferences.getBoolean(KEY_INLINE_SUGGESTIONS, true)
        set(value) {
            preferences.edit { putBoolean(KEY_INLINE_SUGGESTIONS, value) }
        }

    fun isBlocked(targetKey: String): Boolean = blockedTargets().contains(targetKey)

    fun block(targetKey: String) {
        val values = blockedTargets().toMutableSet()
        values += targetKey.take(MAX_TARGET_KEY_LENGTH)
        preferences.edit { putStringSet(KEY_BLOCKED_TARGETS, values) }
    }

    fun blockedTargetCount(): Int = blockedTargets().size

    fun clearBlockedTargets() {
        preferences.edit { remove(KEY_BLOCKED_TARGETS) }
    }

    private fun blockedTargets(): Set<String> =
        preferences.getStringSet(KEY_BLOCKED_TARGETS, emptySet())?.toSet().orEmpty()

    companion object {
        private const val PREFERENCES_NAME = "secretbase_autofill"
        private const val KEY_SAVE_PROMPTS = "save_prompts"
        private const val KEY_INLINE_SUGGESTIONS = "inline_suggestions"
        private const val KEY_BLOCKED_TARGETS = "blocked_targets"
        private const val MAX_TARGET_KEY_LENGTH = 320
    }
}
