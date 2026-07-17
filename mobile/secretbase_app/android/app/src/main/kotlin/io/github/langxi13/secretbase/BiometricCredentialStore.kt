package io.github.langxi13.secretbase

import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyInfo
import android.security.keystore.KeyPermanentlyInvalidatedException
import android.security.keystore.KeyProperties
import android.security.keystore.StrongBoxUnavailableException
import android.security.keystore.UserNotAuthenticatedException
import android.util.AtomicFile
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.fragment.app.FragmentActivity
import io.flutter.plugin.common.MethodChannel
import java.io.File
import java.security.KeyStore
import java.security.UnrecoverableKeyException
import javax.crypto.AEADBadTagException
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.GCMParameterSpec

internal class BiometricCredentialStore(
    private val activity: FragmentActivity,
) {
    companion object {
        private const val KEY_ALIAS = "secretbase_device_unlock_v1"
        private const val KEYSTORE = "AndroidKeyStore"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
        private const val FILE_VERSION: Byte = 1
        private const val MAX_CREDENTIAL_BYTES = 512
    }

    private val biometricManager = BiometricManager.from(activity)
    private val executor = ContextCompat.getMainExecutor(activity)
    private val credentialFile = AtomicFile(
        File(activity.filesDir, "biometric/device-unlock.v1"),
    )
    private var prompt: BiometricPrompt? = null
    private data class ActiveResult(
        val success: (Any?) -> Unit,
        val error: (String, String) -> Unit,
    )

    private var activeResult: ActiveResult? = null
    private var pendingCredential: ByteArray? = null
    private enum class KeyAvailability { PRESENT, MISSING, UNKNOWN }

    fun status(result: MethodChannel.Result) {
        result.success(status())
    }

    fun status(): Map<String, Any> {
        val authentication = biometricManager.canAuthenticate(
            BiometricManager.Authenticators.BIOMETRIC_STRONG,
        )
        val keyAvailability = keyAvailability()
        if (credentialFile.baseFile.exists() && keyAvailability == KeyAvailability.MISSING) {
            clearCredential()
        }
        return mapOf(
            "supported" to (authentication != BiometricManager.BIOMETRIC_ERROR_NO_HARDWARE),
            "enrolled" to (authentication == BiometricManager.BIOMETRIC_SUCCESS),
            "credentialStored" to (
                credentialFile.baseFile.exists() && keyAvailability != KeyAvailability.MISSING
            ),
            "hardwareBacked" to (
                keyAvailability == KeyAvailability.PRESENT && keyIsHardwareBacked()
            ),
            "code" to authentication,
        )
    }

    fun store(credential: ByteArray, result: MethodChannel.Result) {
        if (credential.size > MAX_CREDENTIAL_BYTES) {
            credential.fill(0)
            result.error("BIOMETRIC_CREDENTIAL_INVALID", "设备解锁凭据无效", null)
            return
        }
        if (!begin(result, credential)) return
        if (!ensureAvailable()) return
        try {
            val cipher = Cipher.getInstance(TRANSFORMATION).apply {
                init(Cipher.ENCRYPT_MODE, getOrCreateKey())
            }
            authenticate(
                cipher = cipher,
                title = "开启指纹解锁",
                subtitle = "验证指纹以保护本机解锁密钥",
            ) { authenticatedCipher ->
                val secret = pendingCredential ?: return@authenticate fail(
                    "BIOMETRIC_CREDENTIAL_INVALID",
                    "设备解锁凭据已失效",
                )
                try {
                    val encrypted = authenticatedCipher.doFinal(secret)
                    writeCredential(authenticatedCipher.iv, encrypted)
                    finish(true)
                } catch (_: Exception) {
                    clearCredential()
                    fail("BIOMETRIC_STORAGE_FAILED", "无法保存指纹解锁凭据")
                }
            }
        } catch (_: Exception) {
            clearCredential()
            fail("BIOMETRIC_STORAGE_FAILED", "无法初始化指纹安全存储")
        }
    }

    fun read(result: MethodChannel.Result) {
        read(
            onSuccess = result::success,
            onError = { code, message -> result.error(code, message, null) },
        )
    }

    fun read(
        onSuccess: (ByteArray) -> Unit,
        onError: (String, String) -> Unit,
    ) {
        if (!begin(
                onSuccess = { value ->
                    if (value is ByteArray) {
                        onSuccess(value)
                    } else {
                        onError("BIOMETRIC_STORAGE_FAILED", "生物识别未返回安全凭据")
                    }
                },
                onError = onError,
            )
        ) return
        if (!credentialFile.baseFile.exists()) {
            fail("BIOMETRIC_NOT_ENABLED", "尚未开启指纹解锁")
            return
        }
        if (!ensureAvailable()) return
        val stored = try {
            readCredential()
        } catch (_: IllegalStateException) {
            clearCredential()
            fail("BIOMETRIC_CREDENTIAL_INVALID", "指纹解锁凭据已损坏，请重新开启")
            return
        } catch (_: Exception) {
            fail("BIOMETRIC_STORAGE_FAILED", "暂时无法读取指纹解锁凭据，请重试")
            return
        }
        pendingCredential = stored.second
        val key = try {
            loadKey()
        } catch (_: KeyPermanentlyInvalidatedException) {
            clearCredential()
            fail("BIOMETRIC_CREDENTIAL_INVALID", "设备指纹已发生变化，请重新开启指纹解锁")
            return
        } catch (_: UserNotAuthenticatedException) {
            fail("BIOMETRIC_TEMPORARILY_UNAVAILABLE", "设备尚未完成解锁，请稍后重试")
            return
        } catch (_: UnrecoverableKeyException) {
            fail("BIOMETRIC_TEMPORARILY_UNAVAILABLE", "Android 安全存储暂时不可用，请稍后重试")
            return
        } catch (_: Exception) {
            fail("BIOMETRIC_TEMPORARILY_UNAVAILABLE", "Android 安全存储暂时不可用，请稍后重试")
            return
        }
        if (key == null) {
            clearCredential()
            fail("BIOMETRIC_CREDENTIAL_INVALID", "指纹解锁凭据已失效，请重新开启")
            return
        }
        val cipher = try {
            Cipher.getInstance(TRANSFORMATION).apply {
                init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, stored.first))
            }
        } catch (_: KeyPermanentlyInvalidatedException) {
            clearCredential()
            fail("BIOMETRIC_CREDENTIAL_INVALID", "设备指纹已发生变化，请重新开启指纹解锁")
            return
        } catch (_: UserNotAuthenticatedException) {
            fail("BIOMETRIC_TEMPORARILY_UNAVAILABLE", "设备尚未完成解锁，请稍后重试")
            return
        } catch (_: Exception) {
            fail("BIOMETRIC_TEMPORARILY_UNAVAILABLE", "暂时无法启动指纹解锁，请稍后重试")
            return
        }
        authenticate(
            cipher = cipher,
            title = "解锁 SecretBase",
            subtitle = "使用已录入的指纹继续",
        ) { authenticatedCipher ->
            try {
                val plaintext = authenticatedCipher.doFinal(stored.second)
                finish(plaintext)
            } catch (_: AEADBadTagException) {
                clearCredential()
                fail("BIOMETRIC_CREDENTIAL_INVALID", "指纹解锁凭据已损坏，请重新开启")
            } catch (_: KeyPermanentlyInvalidatedException) {
                clearCredential()
                fail("BIOMETRIC_CREDENTIAL_INVALID", "设备指纹已发生变化，请重新开启指纹解锁")
            } catch (_: UserNotAuthenticatedException) {
                fail("BIOMETRIC_TEMPORARILY_UNAVAILABLE", "本次指纹认证已失效，请重试")
            } catch (_: Exception) {
                fail("BIOMETRIC_STORAGE_FAILED", "暂时无法读取指纹解锁凭据，请重试")
            }
        }
    }

    fun delete(result: MethodChannel.Result) {
        if (activeResult != null) {
            result.error("BIOMETRIC_BUSY", "生物识别操作正在进行", null)
            return
        }
        result.success(delete())
    }

    fun delete(): Boolean {
        if (activeResult != null) return false
        val existed = credentialFile.baseFile.exists() ||
            keyAvailability() == KeyAvailability.PRESENT
        clearCredential()
        return existed
    }

    fun dispose() {
        prompt?.cancelAuthentication()
        prompt = null
        pendingCredential?.fill(0)
        pendingCredential = null
        activeResult?.error("BIOMETRIC_CANCELED", "生物识别操作已取消")
        activeResult = null
    }

    private fun begin(result: MethodChannel.Result, credential: ByteArray? = null): Boolean {
        return begin(
            credential = credential,
            onSuccess = result::success,
            onError = { code, message -> result.error(code, message, null) },
        )
    }

    private fun begin(
        credential: ByteArray? = null,
        onSuccess: (Any?) -> Unit,
        onError: (String, String) -> Unit,
    ): Boolean {
        if (activeResult != null) {
            credential?.fill(0)
            onError("BIOMETRIC_BUSY", "生物识别操作正在进行")
            return false
        }
        activeResult = ActiveResult(success = onSuccess, error = onError)
        pendingCredential = credential
        return true
    }

    private fun ensureAvailable(): Boolean {
        return when (
            biometricManager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG)
        ) {
            BiometricManager.BIOMETRIC_SUCCESS -> true
            BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED -> {
                fail("BIOMETRIC_NOT_ENROLLED", "请先在系统设置中录入指纹")
                false
            }
            BiometricManager.BIOMETRIC_ERROR_NO_HARDWARE -> {
                fail("BIOMETRIC_UNAVAILABLE", "当前设备不支持强生物识别")
                false
            }
            else -> {
                fail("BIOMETRIC_UNAVAILABLE", "生物识别暂时不可用，请使用主密码")
                false
            }
        }
    }

    private fun authenticate(
        cipher: Cipher,
        title: String,
        subtitle: String,
        onSuccess: (Cipher) -> Unit,
    ) {
        restoreWindowAfterPrompt()
        val callback = object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                val authenticatedCipher = result.cryptoObject?.cipher
                if (authenticatedCipher == null) {
                    fail("BIOMETRIC_STORAGE_FAILED", "生物识别未返回安全凭据")
                    return
                }
                onSuccess(authenticatedCipher)
            }

            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                when (errorCode) {
                    BiometricPrompt.ERROR_NEGATIVE_BUTTON,
                    BiometricPrompt.ERROR_USER_CANCELED,
                    BiometricPrompt.ERROR_CANCELED -> fail(
                        "BIOMETRIC_CANCELED",
                        "已取消指纹验证",
                    )
                    BiometricPrompt.ERROR_LOCKOUT,
                    BiometricPrompt.ERROR_LOCKOUT_PERMANENT -> fail(
                        "BIOMETRIC_LOCKED_OUT",
                        "指纹验证已锁定，请使用主密码",
                    )
                    BiometricPrompt.ERROR_NO_BIOMETRICS -> fail(
                        "BIOMETRIC_NOT_ENROLLED",
                        "请先在系统设置中录入指纹",
                    )
                    else -> fail("BIOMETRIC_UNAVAILABLE", errString.toString())
                }
            }
        }
        prompt = BiometricPrompt(activity, executor, callback)
        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle(title)
            .setSubtitle(subtitle)
            .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
            .setNegativeButtonText("使用主密码")
            .setConfirmationRequired(true)
            .build()
        prompt?.authenticate(promptInfo, BiometricPrompt.CryptoObject(cipher))
    }

    private fun getOrCreateKey(): SecretKey = loadKey() ?: generateKey(useStrongBox = true)

    private fun generateKey(useStrongBox: Boolean): SecretKey {
        val builder = KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .setUserAuthenticationRequired(true)
            .setInvalidatedByBiometricEnrollment(true)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            builder.setUserAuthenticationParameters(
                0,
                KeyProperties.AUTH_BIOMETRIC_STRONG,
            )
        } else {
            @Suppress("DEPRECATION")
            builder.setUserAuthenticationValidityDurationSeconds(-1)
        }
        builder.setUnlockedDeviceRequired(true)
        if (useStrongBox && activity.packageManager.hasSystemFeature("android.hardware.strongbox_keystore")) {
            builder.setIsStrongBoxBacked(true)
        }
        return try {
            KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE).run {
                init(builder.build())
                generateKey()
            }
        } catch (_: StrongBoxUnavailableException) {
            generateKey(useStrongBox = false)
        }
    }

    private fun loadKey(): SecretKey? {
        val keyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        return keyStore.getKey(KEY_ALIAS, null) as? SecretKey
    }

    private fun keyAvailability(): KeyAvailability = try {
        val keyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        if (keyStore.containsAlias(KEY_ALIAS)) {
            KeyAvailability.PRESENT
        } else {
            KeyAvailability.MISSING
        }
    } catch (_: Exception) {
        KeyAvailability.UNKNOWN
    }

    private fun keyIsHardwareBacked(): Boolean = try {
        val key = loadKey() ?: return false
        val factory = SecretKeyFactory.getInstance(key.algorithm, KEYSTORE)
        val keyInfo = factory.getKeySpec(key, KeyInfo::class.java) as KeyInfo
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            when (keyInfo.getSecurityLevel()) {
                KeyProperties.SECURITY_LEVEL_TRUSTED_ENVIRONMENT,
                KeyProperties.SECURITY_LEVEL_STRONGBOX,
                KeyProperties.SECURITY_LEVEL_UNKNOWN_SECURE -> true
                else -> false
            }
        } else {
            @Suppress("DEPRECATION")
            keyInfo.isInsideSecureHardware()
        }
    } catch (_: Exception) {
        false
    }

    private fun writeCredential(iv: ByteArray, encrypted: ByteArray) {
        credentialFile.baseFile.parentFile?.mkdirs()
        val output = credentialFile.startWrite()
        try {
            output.write(byteArrayOf(FILE_VERSION, iv.size.toByte()))
            output.write(iv)
            output.write(encrypted)
            credentialFile.finishWrite(output)
        } catch (error: Exception) {
            credentialFile.failWrite(output)
            throw error
        }
    }

    private fun readCredential(): Pair<ByteArray, ByteArray> {
        val content = credentialFile.readFully()
        if (content.size < 3 || content[0] != FILE_VERSION) {
            throw IllegalStateException("invalid biometric credential")
        }
        val ivLength = content[1].toInt() and 0xff
        if (ivLength !in 12..32 || content.size <= 2 + ivLength) {
            throw IllegalStateException("invalid biometric credential")
        }
        return content.copyOfRange(2, 2 + ivLength) to
            content.copyOfRange(2 + ivLength, content.size)
    }

    private fun clearCredential() {
        try {
            credentialFile.delete()
        } catch (_: Exception) {
            credentialFile.baseFile.delete()
        }
        try {
            val keyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }
            if (keyStore.containsAlias(KEY_ALIAS)) keyStore.deleteEntry(KEY_ALIAS)
        } catch (_: Exception) {
            // The stale encrypted file is already removed; a missing key is harmless.
        }
    }

    private fun finish(value: Any?) {
        val result = activeResult ?: return
        activeResult = null
        prompt = null
        pendingCredential?.fill(0)
        pendingCredential = null
        result.success(value)
        if (value is ByteArray) value.fill(0)
        restoreWindowAfterPrompt()
    }

    private fun fail(code: String, message: String) {
        val result = activeResult ?: return
        activeResult = null
        prompt = null
        pendingCredential?.fill(0)
        pendingCredential = null
        result.error(code, message)
        restoreWindowAfterPrompt()
    }

    private fun restoreWindowAfterPrompt() {
        val decorView = activity.window.decorView
        decorView.post {
            WindowCompat.getInsetsController(activity.window, decorView)
                .hide(WindowInsetsCompat.Type.ime())
            ViewCompat.requestApplyInsets(decorView)
            decorView.requestLayout()
        }
    }
}
