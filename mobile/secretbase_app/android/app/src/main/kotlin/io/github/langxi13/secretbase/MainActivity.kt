package io.github.langxi13.secretbase

import android.app.KeyguardManager
import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import android.os.Bundle
import android.os.PersistableBundle
import android.view.WindowManager
import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterFragmentActivity() {
    companion object {
        private const val PLATFORM_CHANNEL = "secretbase/platform"
        private const val SECURITY_CHANNEL = "secretbase/security"
        private const val REQUEST_CREATE_DOCUMENT = 7001
    }

    private var securityChannel: MethodChannel? = null
    private var biometricCredentialStore: BiometricCredentialStore? = null
    private var receiverRegistered = false
    private var pendingExportResult: MethodChannel.Result? = null
    private var pendingExportBytes: ByteArray? = null
    private val screenReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == Intent.ACTION_SCREEN_OFF) {
                notifyFlutter("deviceLocked")
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        super.onCreate(savedInstanceState)
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        biometricCredentialStore = BiometricCredentialStore(this)
        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            PLATFORM_CHANNEL,
        ).setMethodCallHandler { call, result ->
            when (call.method) {
                "getApplicationDataRoot" -> result.success(filesDir.absolutePath)
                else -> result.notImplemented()
            }
        }
        securityChannel = MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            SECURITY_CHANNEL,
        ).also { channel ->
            channel.setMethodCallHandler { call, result ->
                when (call.method) {
                    "copySensitive" -> {
                        val text = call.argument<String>("text").orEmpty()
                        copySensitive(text)
                        result.success(null)
                    }
                    "clearClipboardIfMatches" -> {
                        val text = call.argument<String>("text").orEmpty()
                        clearClipboardIfMatches(text)
                        result.success(null)
                    }
                    "saveDocument" -> {
                        val filename = call.argument<String>("filename").orEmpty()
                        val bytes = call.argument<ByteArray>("bytes")
                        if (filename.isBlank() || bytes == null) {
                            result.error("INVALID_EXPORT", "导出文件参数无效", null)
                        } else {
                            startDocumentExport(filename, bytes, result)
                        }
                    }
                    "biometricStatus" -> biometricCredentialStore?.status(result)
                        ?: result.error("BIOMETRIC_UNAVAILABLE", "生物识别服务不可用", null)
                    "storeBiometricCredential" -> {
                        val credential = call.argument<ByteArray>("credential")
                        if (credential == null || credential.isEmpty()) {
                            result.error("BIOMETRIC_CREDENTIAL_INVALID", "设备解锁凭据无效", null)
                        } else {
                            biometricCredentialStore?.store(credential, result)
                                ?: run {
                                    credential.fill(0)
                                    result.error("BIOMETRIC_UNAVAILABLE", "生物识别服务不可用", null)
                                }
                        }
                    }
                    "readBiometricCredential" -> biometricCredentialStore?.read(result)
                        ?: result.error("BIOMETRIC_UNAVAILABLE", "生物识别服务不可用", null)
                    "deleteBiometricCredential" -> biometricCredentialStore?.delete(result)
                        ?: result.success(false)
                    else -> result.notImplemented()
                }
            }
        }
        val filter = IntentFilter(Intent.ACTION_SCREEN_OFF)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(screenReceiver, filter, RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(screenReceiver, filter)
        }
        receiverRegistered = true
    }

    override fun onPause() {
        super.onPause()
        val keyguard = getSystemService(KEYGUARD_SERVICE) as KeyguardManager
        if (keyguard.isDeviceLocked) {
            notifyFlutter("deviceLocked")
        }
    }

    override fun onDestroy() {
        if (receiverRegistered) {
            unregisterReceiver(screenReceiver)
            receiverRegistered = false
        }
        pendingExportResult?.error("EXPORT_INTERRUPTED", "导出操作已中断", null)
        pendingExportResult = null
        pendingExportBytes = null
        biometricCredentialStore?.dispose()
        biometricCredentialStore = null
        securityChannel = null
        super.onDestroy()
    }

    @Deprecated("Android Activity Result API compatibility")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQUEST_CREATE_DOCUMENT) return
        val result = pendingExportResult
        val bytes = pendingExportBytes
        pendingExportResult = null
        pendingExportBytes = null
        if (resultCode != Activity.RESULT_OK || data?.data == null) {
            result?.success(false)
            return
        }
        try {
            contentResolver.openOutputStream(data.data!!, "w")?.use { output ->
                output.write(bytes ?: ByteArray(0))
                output.flush()
            } ?: throw IllegalStateException("无法打开导出目标")
            result?.success(true)
        } catch (_: Exception) {
            result?.error("SAVE_FAILED", "无法写入所选文件", null)
        }
    }

    private fun notifyFlutter(event: String) {
        runOnUiThread { securityChannel?.invokeMethod(event, null) }
    }

    private fun copySensitive(text: String) {
        val clipboard = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
        val clip = ClipData.newPlainText("SecretBase", text)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            clip.description.extras = PersistableBundle().apply {
                putBoolean("android.content.extra.IS_SENSITIVE", true)
            }
        }
        clipboard.setPrimaryClip(clip)
    }

    private fun clearClipboardIfMatches(expected: String) {
        val clipboard = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
        val current = clipboard.primaryClip
            ?.takeIf { it.itemCount > 0 }
            ?.getItemAt(0)
            ?.coerceToText(this)
            ?.toString()
        if (current == expected) {
            clipboard.clearPrimaryClip()
        }
    }

    @Suppress("DEPRECATION")
    private fun startDocumentExport(
        filename: String,
        bytes: ByteArray,
        result: MethodChannel.Result,
    ) {
        if (pendingExportResult != null) {
            result.error("EXPORT_BUSY", "已有导出操作正在进行", null)
            return
        }
        pendingExportResult = result
        pendingExportBytes = bytes
        val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "application/octet-stream"
            putExtra(Intent.EXTRA_TITLE, filename.take(120))
        }
        startActivityForResult(intent, REQUEST_CREATE_DOCUMENT)
    }
}
