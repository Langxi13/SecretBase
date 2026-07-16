package io.github.langxi13.secretbase.autofill

import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

internal data class PendingAutofillSave(
    val title: String,
    val url: String,
    val targetLabel: String,
    val username: CharArray,
    val password: CharArray,
    val createdAtMillis: Long = System.currentTimeMillis(),
) {
    fun clear() {
        username.fill('\u0000')
        password.fill('\u0000')
    }
}

internal object PendingAutofillSaveStore {
    private const val TTL_MILLIS = 120_000L
    private const val MAX_PENDING = 3
    private val values = ConcurrentHashMap<String, PendingAutofillSave>()

    fun put(request: ParsedAutofillRequest): String? {
        val password = request.passwordValue?.takeIf { it.isNotEmpty() } ?: return null
        cleanup()
        while (values.size >= MAX_PENDING) {
            val oldest = values.minByOrNull { it.value.createdAtMillis }?.key ?: break
            remove(oldest)
        }
        val token = UUID.randomUUID().toString()
        val domain = request.webDomain
        val title = domain?.removePrefix("www.")?.take(200)
            ?: request.packageName.substringAfterLast('.').ifBlank { "新登录信息" }.take(200)
        val url = domain?.let { "${request.webScheme ?: "https"}://$it" }.orEmpty()
        values[token] = PendingAutofillSave(
            title = title,
            url = url,
            targetLabel = request.targetLabel.take(320),
            username = request.usernameValue.orEmpty().toCharArray(),
            password = password.toCharArray(),
        )
        return token
    }

    fun peek(token: String): PendingAutofillSave? {
        cleanup()
        return values[token]
    }

    fun remove(token: String) {
        values.remove(token)?.clear()
    }

    private fun cleanup() {
        val cutoff = System.currentTimeMillis() - TTL_MILLIS
        values.entries
            .filter { it.value.createdAtMillis < cutoff }
            .map { it.key }
            .forEach(::remove)
    }
}
