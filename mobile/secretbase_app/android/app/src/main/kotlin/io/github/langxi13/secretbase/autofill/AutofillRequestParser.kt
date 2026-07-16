package io.github.langxi13.secretbase.autofill

import android.app.assist.AssistStructure
import android.text.InputType
import android.view.View
import android.view.autofill.AutofillId
import android.view.autofill.AutofillValue

internal data class ParsedAutofillRequest(
    val packageName: String,
    val webDomain: String?,
    val webScheme: String?,
    val usernameId: AutofillId?,
    val passwordId: AutofillId,
    val usernameValue: String?,
    val passwordValue: String?,
    val passwordIsNew: Boolean,
) {
    val targetKey: String
        get() = webDomain?.let { "web:${it.lowercase()}" }
            ?: "app:${packageName.lowercase()}"

    val targetLabel: String
        get() = webDomain ?: packageName

    val authenticationIds: Array<AutofillId>
        get() = listOfNotNull(usernameId, passwordId).distinct().toTypedArray()
}

internal class AutofillRequestParser {
    private data class FieldCandidate(
        val id: AutofillId,
        val usernameScore: Int,
        val passwordScore: Int,
        val passwordIsNew: Boolean,
        val value: AutofillValue?,
    )

    private data class CapturedContext(
        val packageName: String,
        val webDomain: String?,
        val webScheme: String?,
        val usernameId: AutofillId?,
        val passwordId: AutofillId?,
        val usernameValue: String?,
        val passwordValue: String?,
        val passwordIsNew: Boolean,
    ) {
        fun toRequest(usernameSource: CapturedContext = this): ParsedAutofillRequest? {
            val requiredPasswordId = passwordId ?: return null
            return ParsedAutofillRequest(
                packageName = packageName,
                webDomain = webDomain,
                webScheme = webScheme,
                usernameId = usernameSource.usernameId,
                passwordId = requiredPasswordId,
                usernameValue = usernameSource.usernameValue,
                passwordValue = passwordValue,
                passwordIsNew = passwordIsNew,
            )
        }

        fun sameTarget(other: CapturedContext): Boolean =
            packageName.equals(other.packageName, ignoreCase = true) &&
                webDomain == other.webDomain
    }

    fun parse(
        structure: AssistStructure,
        preferNewPassword: Boolean = false,
    ): ParsedAutofillRequest? = capture(structure, preferNewPassword)?.toRequest()

    fun parseForSave(structures: List<AssistStructure>): ParsedAutofillRequest? {
        val contexts = structures
            .takeLast(MAX_SAVE_CONTEXTS)
            .mapNotNull { capture(it, preferNewPassword = true) }
        val passwordContext = contexts.asReversed().firstOrNull { it.passwordId != null }
            ?: return null
        if (passwordContext.passwordValue.isNullOrEmpty()) return null
        val usernameContext = contexts.asReversed().firstOrNull { context ->
            context.sameTarget(passwordContext) && !context.usernameValue.isNullOrEmpty()
        } ?: passwordContext
        return passwordContext.toRequest(usernameContext)
    }

    private fun capture(
        structure: AssistStructure,
        preferNewPassword: Boolean,
    ): CapturedContext? {
        val packageName = structure.activityComponent?.packageName.orEmpty()
        if (packageName.isBlank()) return null

        val candidates = mutableListOf<FieldCandidate>()
        var webDomain: String? = null
        var webScheme: String? = null
        var visited = 0

        fun visit(node: AssistStructure.ViewNode, depth: Int) {
            if (depth > MAX_DEPTH || visited >= MAX_NODES) return
            visited += 1
            if (webDomain == null) {
                webDomain = node.webDomain
                    ?.trim()
                    ?.trimEnd('.')
                    ?.lowercase()
                    ?.takeIf { it.isNotBlank() && it.length <= 253 }
                webScheme = node.webScheme
                    ?.trim()
                    ?.lowercase()
                    ?.takeIf { it == "http" || it == "https" }
            }
            val id = node.autofillId
            if (id != null && node.autofillType == View.AUTOFILL_TYPE_TEXT) {
                val descriptor = descriptor(node)
                val usernameScore = AutofillFieldClassifier.usernameScore(
                    node.inputType,
                    descriptor,
                )
                val password = AutofillFieldClassifier.password(
                    node.inputType,
                    descriptor,
                )
                val passwordScore = password.score
                if (usernameScore > 0 || passwordScore > 0) {
                    candidates += FieldCandidate(
                        id = id,
                        usernameScore = usernameScore,
                        passwordScore = passwordScore,
                        passwordIsNew = password.isNew,
                        value = node.autofillValue,
                    )
                }
            }
            repeat(node.childCount) { index ->
                visit(node.getChildAt(index), depth + 1)
            }
        }

        repeat(structure.windowNodeCount) { index ->
            visit(structure.getWindowNodeAt(index).rootViewNode, 0)
        }

        val password = candidates.maxByOrNull {
            it.passwordScore + if (preferNewPassword && it.passwordIsNew) 200 else 0
        }
            ?.takeIf { it.passwordScore > 0 }
        val username = candidates
            .asSequence()
            .filter { it.id != password?.id }
            .maxByOrNull { it.usernameScore }
            ?.takeIf { it.usernameScore > 0 }
        if (password == null && username == null) return null

        return CapturedContext(
            packageName = packageName,
            webDomain = webDomain,
            webScheme = webScheme,
            usernameId = username?.id,
            passwordId = password?.id,
            usernameValue = username?.value?.textValue?.toString()?.take(MAX_VALUE_CHARS),
            passwordValue = password?.value?.textValue?.toString()?.take(MAX_VALUE_CHARS),
            passwordIsNew = password?.passwordIsNew == true,
        )
    }

    private fun descriptor(node: AssistStructure.ViewNode): String {
        val values = mutableListOf<String>()
        node.autofillHints?.forEach(values::add)
        node.hint?.let(values::add)
        node.idEntry?.let(values::add)
        node.className?.let(values::add)
        node.htmlInfo?.attributes?.forEach { attribute ->
            if (attribute.first.lowercase() in HTML_ATTRIBUTE_NAMES) {
                values += attribute.second
            }
        }
        return values
            .joinToString(" ")
            .lowercase()
            .replace(Regex("[^a-z0-9_@.-]+"), " ")
            .take(MAX_DESCRIPTOR_CHARS)
    }

    companion object {
        private const val MAX_NODES = 1000
        private const val MAX_DEPTH = 40
        private const val MAX_SAVE_CONTEXTS = 8
        private const val MAX_DESCRIPTOR_CHARS = 2000
        private const val MAX_VALUE_CHARS = 10_000
        private val HTML_ATTRIBUTE_NAMES = setOf("autocomplete", "name", "id", "type")
    }
}

internal data class PasswordFieldClassification(
    val score: Int,
    val isNew: Boolean,
)

internal object AutofillFieldClassifier {
    fun password(inputType: Int, descriptor: String): PasswordFieldClassification {
        val variation = inputType and InputType.TYPE_MASK_VARIATION
        val passwordInput = variation in setOf(
            InputType.TYPE_TEXT_VARIATION_PASSWORD,
            InputType.TYPE_TEXT_VARIATION_WEB_PASSWORD,
            InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD,
            InputType.TYPE_NUMBER_VARIATION_PASSWORD,
        )
        val newPassword = descriptor.contains("new-password") ||
            descriptor.contains("newpassword") ||
            descriptor.contains("passwordnew")
        val currentPassword = descriptor.contains("current-password") ||
            descriptor.contains("currentpassword")
        val namedPassword = PASSWORD_MARKERS.any(descriptor::contains)
        val score = when {
            currentPassword -> 150
            namedPassword && !newPassword -> 125
            passwordInput && !newPassword -> 110
            newPassword -> 90
            passwordInput -> 60
            else -> 0
        }
        return PasswordFieldClassification(score = score, isNew = newPassword)
    }

    fun usernameScore(inputType: Int, descriptor: String): Int {
        val variation = inputType and InputType.TYPE_MASK_VARIATION
        val emailInput = variation == InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS ||
            variation == InputType.TYPE_TEXT_VARIATION_WEB_EMAIL_ADDRESS
        return when {
            descriptor.contains("username") || descriptor.contains("user-name") -> 140
            descriptor.contains("email") || descriptor.contains("e-mail") -> 130
            descriptor.contains("login") || descriptor.contains("account") -> 115
            emailInput -> 100
            else -> 0
        }
    }

    private val PASSWORD_MARKERS = listOf("password", "passwd", "passcode", "pwd")
}
