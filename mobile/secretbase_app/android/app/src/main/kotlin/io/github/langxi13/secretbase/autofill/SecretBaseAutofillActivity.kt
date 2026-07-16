package io.github.langxi13.secretbase.autofill

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.view.autofill.AutofillManager
import android.widget.ArrayAdapter
import android.widget.LinearLayout
import android.widget.ListView
import android.widget.ProgressBar
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.core.view.setPadding
import androidx.fragment.app.FragmentActivity
import com.google.android.material.appbar.MaterialToolbar
import com.google.android.material.button.MaterialButton
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.materialswitch.MaterialSwitch
import com.google.android.material.textfield.TextInputEditText
import io.github.langxi13.secretbase.BiometricCredentialStore
import io.github.langxi13.secretbase.R
import org.json.JSONObject
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class SecretBaseAutofillActivity : FragmentActivity() {
    private enum class Mode { FILL, SAVE }

    private lateinit var mode: Mode
    private lateinit var biometricStore: BiometricCredentialStore
    private lateinit var executor: ExecutorService
    private lateinit var targetView: TextView
    private lateinit var statusView: TextView
    private lateinit var errorView: TextView
    private lateinit var progress: ProgressBar
    private lateinit var authPanel: View
    private lateinit var passwordInput: TextInputEditText
    private lateinit var biometricButton: MaterialButton
    private lateinit var unlockButton: MaterialButton
    private lateinit var candidatePanel: View
    private lateinit var candidateList: ListView
    private lateinit var searchInput: TextInputEditText
    private lateinit var rememberBinding: MaterialSwitch
    private lateinit var savePanel: View
    private lateinit var saveTitle: TextInputEditText
    private lateinit var saveUrl: TextInputEditText
    private lateinit var saveUsername: TextView
    private lateinit var saveButton: MaterialButton

    private val candidateAdapter by lazy { AutofillCandidateAdapter(this) }
    private var allCandidates: List<NativeAutofillCandidate> = emptyList()
    private var sessionToken: String? = null
    private var saveToken: String? = null
    private var working = false
    private var completed = false

    override fun onCreate(savedInstanceState: Bundle?) {
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        super.onCreate(savedInstanceState)
        mode = when (intent.action) {
            AutofillIntents.ACTION_FILL -> Mode.FILL
            AutofillIntents.ACTION_SAVE -> Mode.SAVE
            else -> {
                finish()
                return
            }
        }
        setContentView(R.layout.activity_secretbase_autofill)
        executor = Executors.newSingleThreadExecutor()
        biometricStore = BiometricCredentialStore(this)
        bindViews()
        configureCommonUi()
        when (mode) {
            Mode.FILL -> configureFill()
            Mode.SAVE -> configureSave()
        }
    }

    override fun onDestroy() {
        sessionToken?.let(AutofillNativeClient::cancel)
        if (!completed) saveToken?.let(PendingAutofillSaveStore::remove)
        biometricStore.dispose()
        executor.shutdownNow()
        super.onDestroy()
    }

    private fun bindViews() {
        targetView = findViewById(R.id.autofill_target)
        statusView = findViewById(R.id.autofill_status)
        errorView = findViewById(R.id.autofill_error)
        progress = findViewById(R.id.autofill_progress)
        authPanel = findViewById(R.id.autofill_auth_panel)
        passwordInput = findViewById(R.id.autofill_password)
        biometricButton = findViewById(R.id.autofill_biometric_button)
        unlockButton = findViewById(R.id.autofill_unlock_button)
        candidatePanel = findViewById(R.id.autofill_candidate_panel)
        candidateList = findViewById(R.id.autofill_candidates)
        searchInput = findViewById(R.id.autofill_search)
        rememberBinding = findViewById(R.id.autofill_remember_binding)
        savePanel = findViewById(R.id.autofill_save_panel)
        saveTitle = findViewById(R.id.autofill_save_title)
        saveUrl = findViewById(R.id.autofill_save_url)
        saveUsername = findViewById(R.id.autofill_save_username)
        saveButton = findViewById(R.id.autofill_save_button)
    }

    private fun configureCommonUi() {
        findViewById<MaterialToolbar>(R.id.autofill_toolbar).apply {
            setNavigationIcon(android.R.drawable.ic_menu_close_clear_cancel)
            setNavigationContentDescription("关闭")
            setNavigationOnClickListener { cancelAndFinish() }
        }
        findViewById<MaterialButton>(R.id.autofill_block_button).setOnClickListener {
            AutofillPreferences(this).block(targetKey())
            Toast.makeText(this, "已对此目标停用自动填充", Toast.LENGTH_SHORT).show()
            cancelAndFinish()
        }
        passwordInput.setOnEditorActionListener { _, _, _ ->
            authenticateWithPassword()
            true
        }
        biometricButton.setOnClickListener { authenticateWithBiometric() }
        unlockButton.setOnClickListener { authenticateWithPassword() }
    }

    private fun configureFill() {
        targetView.text = targetLabel()
        statusView.text = "验证后选择要填充的条目"
        candidateList.adapter = candidateAdapter
        candidateList.setOnItemClickListener { _, _, position, _ ->
            val candidate = candidateAdapter.getItem(position)
            if (candidate.mappingConfident) {
                selectCandidate(
                    candidate,
                    candidate.usernameField,
                    candidate.passwordField,
                )
            } else {
                showFieldMapping(candidate)
            }
        }
        candidateList.setOnItemLongClickListener { _, _, position, _ ->
            showFieldMapping(candidateAdapter.getItem(position))
            true
        }
        searchInput.addTextChangedListener(SimpleTextWatcher { filterCandidates(it) })
        authPanel.visibility = View.VISIBLE
        candidatePanel.visibility = View.GONE
        savePanel.visibility = View.GONE
        configureBiometricButton(automatic = true)
    }

    private fun configureSave() {
        val token = intent.getStringExtra(AutofillIntents.EXTRA_SAVE_TOKEN)
        val pending = token?.let(PendingAutofillSaveStore::peek)
        if (token == null || pending == null) {
            showError("待保存的登录信息已过期，请重新登录后再试")
            authPanel.visibility = View.GONE
            savePanel.visibility = View.GONE
            return
        }
        saveToken = token
        targetView.text = pending.targetLabel
        statusView.text = "确认条目信息后保存到本机密码库"
        saveTitle.setText(pending.title)
        saveUrl.setText(pending.url)
        saveUsername.text = if (pending.username.isEmpty()) {
            getString(R.string.autofill_username_missing)
        } else {
            getString(
                R.string.autofill_username_value,
                pending.username.concatToString(),
            )
        }
        authPanel.visibility = View.GONE
        candidatePanel.visibility = View.GONE
        savePanel.visibility = View.VISIBLE
        saveButton.setOnClickListener {
            if (saveTitle.text?.toString()?.trim().isNullOrEmpty()) {
                showError("请输入条目名称")
                return@setOnClickListener
            }
            authPanel.visibility = View.VISIBLE
            statusView.text = "验证身份后保存"
            configureBiometricButton(automatic = true)
        }
    }

    private fun configureBiometricButton(automatic: Boolean) {
        val status = biometricStore.status()
        val available = status["enrolled"] == true && status["credentialStored"] == true
        biometricButton.visibility = if (available) View.VISIBLE else View.GONE
        if (!available) {
            passwordInput.requestFocus()
        } else if (automatic) {
            biometricButton.post { authenticateWithBiometric() }
        }
    }

    private fun authenticateWithBiometric() {
        if (working) return
        setWorking(true)
        hideError()
        biometricStore.read(
            onSuccess = { credential ->
                val copy = credential.copyOf()
                setWorking(false)
                when (mode) {
                    Mode.FILL -> openCandidatesWithCredential(copy)
                    Mode.SAVE -> saveWithCredential(copy)
                }
            },
            onError = { code, message ->
                setWorking(false)
                if (code != "BIOMETRIC_CANCELED") showError(message)
                passwordInput.requestFocus()
            },
        )
    }

    private fun authenticateWithPassword() {
        if (working) return
        val password = passwordInput.text?.toString().orEmpty()
        if (password.isEmpty()) {
            showError("请输入主密码")
            return
        }
        passwordInput.setText("")
        val bytes = password.toByteArray(Charsets.UTF_8)
        when (mode) {
            Mode.FILL -> openCandidatesWithPassword(bytes)
            Mode.SAVE -> saveWithPassword(bytes)
        }
    }

    private fun openCandidatesWithCredential(credential: ByteArray) {
        runNative(
            operation = {
                try {
                    AutofillNativeClient.openWithCredential(
                        filesDir.absolutePath,
                        credential,
                        AutofillIntents.targetJson(intent),
                    )
                } finally {
                    credential.fill(0)
                }
            },
            onSuccess = ::showCandidates,
        )
    }

    private fun openCandidatesWithPassword(password: ByteArray) {
        runNative(
            operation = {
                try {
                    AutofillNativeClient.openWithPassword(
                        filesDir.absolutePath,
                        password,
                        AutofillIntents.targetJson(intent),
                    )
                } finally {
                    password.fill(0)
                }
            },
            onSuccess = ::showCandidates,
        )
    }

    private fun showCandidates(result: NativeAutofillOpenResult) {
        sessionToken?.let(AutofillNativeClient::cancel)
        sessionToken = result.sessionToken
        allCandidates = result.candidates
        candidateAdapter.submit(allCandidates)
        authPanel.visibility = View.GONE
        candidatePanel.visibility = View.VISIBLE
        statusView.text = when {
            result.candidates.isEmpty() -> "没有可用于自动填充的条目"
            result.truncated -> "显示前 ${result.candidates.size} 个候选条目"
            else -> "${result.candidates.size} 个候选条目"
        }
    }

    private fun filterCandidates(query: String) {
        val normalized = query.trim().lowercase()
        val filtered = if (normalized.isEmpty()) {
            allCandidates
        } else {
            allCandidates.filter { candidate ->
                candidate.title.lowercase().contains(normalized) ||
                    candidate.usernamePreview.lowercase().contains(normalized) ||
                    candidate.matchLabel.lowercase().contains(normalized)
            }
        }
        candidateAdapter.submit(filtered)
        statusView.text = getString(R.string.autofill_candidate_count, filtered.size)
    }

    private fun showFieldMapping(candidate: NativeAutofillCandidate) {
        val names = candidate.fields.map { it.name }
        if (names.isEmpty()) {
            showError("该条目没有可填充字段")
            return
        }
        val usernameOptions = listOf("不填充账号") + names
        val usernameSpinner = Spinner(this).apply {
            adapter = ArrayAdapter(
                this@SecretBaseAutofillActivity,
                android.R.layout.simple_spinner_dropdown_item,
                usernameOptions,
            )
            setSelection((candidate.usernameField?.let(names::indexOf) ?: -1) + 1)
        }
        val passwordSpinner = Spinner(this).apply {
            adapter = ArrayAdapter(
                this@SecretBaseAutofillActivity,
                android.R.layout.simple_spinner_dropdown_item,
                names,
            )
            setSelection(names.indexOf(candidate.passwordField).coerceAtLeast(0))
        }
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding((20 * resources.displayMetrics.density).toInt())
            addView(TextView(this@SecretBaseAutofillActivity).apply { text = "账号字段" })
            addView(usernameSpinner)
            addView(TextView(this@SecretBaseAutofillActivity).apply {
                text = "密码字段"
                setPadding(0, (14 * resources.displayMetrics.density).toInt(), 0, 0)
            })
            addView(passwordSpinner)
        }
        MaterialAlertDialogBuilder(this)
            .setTitle(candidate.title)
            .setView(content)
            .setNegativeButton("取消", null)
            .setPositiveButton("填充") { _, _ ->
                val usernameField = usernameSpinner.selectedItemPosition
                    .takeIf { it > 0 }
                    ?.let { usernameOptions[it] }
                val passwordField = names[passwordSpinner.selectedItemPosition]
                if (usernameField == passwordField) {
                    showError("账号字段和密码字段不能相同")
                    return@setPositiveButton
                }
                selectCandidate(
                    candidate,
                    usernameField,
                    passwordField,
                )
            }
            .show()
    }

    private fun selectCandidate(
        candidate: NativeAutofillCandidate,
        usernameField: String?,
        passwordField: String,
    ) {
        val token = sessionToken ?: return
        runNative(
            operation = {
                AutofillNativeClient.select(
                    token,
                    candidate.entryId,
                    usernameField,
                    passwordField,
                    rememberBinding.isChecked,
                )
            },
            onSuccess = { values ->
                sessionToken = null
                returnFillResult(values)
            },
        )
    }

    private fun returnFillResult(values: NativeAutofillFillValues) {
        val passwordId = AutofillIntents.passwordId(intent)
        if (passwordId == null) {
            showError("目标密码输入框已失效")
            return
        }
        val presentation = android.widget.RemoteViews(
            packageName,
            R.layout.autofill_suggestion,
        ).apply {
            setTextViewText(R.id.autofill_suggestion_title, values.title)
            setTextViewText(
                R.id.autofill_suggestion_subtitle,
                values.username.ifBlank { "密码" },
            )
        }
        @Suppress("DEPRECATION")
        val dataset = android.service.autofill.Dataset.Builder(presentation).apply {
            AutofillIntents.usernameId(intent)?.let { usernameId ->
                if (values.username.isNotEmpty()) {
                    setValue(
                        usernameId,
                        android.view.autofill.AutofillValue.forText(values.username),
                    )
                }
            }
            setValue(
                passwordId,
                android.view.autofill.AutofillValue.forText(values.password),
            )
        }.build()
        val response = android.service.autofill.FillResponse.Builder()
            .addDataset(dataset)
            .build()
        completed = true
        setResult(
            Activity.RESULT_OK,
            Intent().putExtra(AutofillManager.EXTRA_AUTHENTICATION_RESULT, response),
        )
        finish()
    }

    private fun saveWithCredential(credential: ByteArray) {
        val draft = saveDraftJson() ?: run {
            credential.fill(0)
            setWorking(false)
            return
        }
        runNative(
            operation = {
                try {
                    AutofillNativeClient.saveWithCredential(
                        filesDir.absolutePath,
                        credential,
                        draft,
                    )
                } finally {
                    credential.fill(0)
                }
            },
            onSuccess = ::completeSave,
        )
    }

    private fun saveWithPassword(password: ByteArray) {
        val draft = saveDraftJson() ?: run {
            password.fill(0)
            setWorking(false)
            return
        }
        runNative(
            operation = {
                try {
                    AutofillNativeClient.saveWithPassword(
                        filesDir.absolutePath,
                        password,
                        draft,
                    )
                } finally {
                    password.fill(0)
                }
            },
            onSuccess = ::completeSave,
        )
    }

    private fun saveDraftJson(): String? {
        val token = saveToken ?: return null
        val pending = PendingAutofillSaveStore.peek(token) ?: run {
            showError("待保存的登录信息已过期")
            return null
        }
        return JSONObject()
            .put("title", saveTitle.text?.toString()?.trim().orEmpty())
            .put("url", saveUrl.text?.toString()?.trim().orEmpty())
            .put("username", pending.username.concatToString())
            .put("password", pending.password.concatToString())
            .toString()
    }

    private fun completeSave(result: NativeAutofillSaveResult) {
        saveToken?.let(PendingAutofillSaveStore::remove)
        saveToken = null
        completed = true
        AutofillVaultChangeNotifier.notifyVaultChanged()
        Toast.makeText(this, result.message, Toast.LENGTH_SHORT).show()
        setResult(Activity.RESULT_OK)
        finish()
    }

    private fun targetLabel(): String =
        intent.getStringExtra(AutofillIntents.EXTRA_WEB_DOMAIN)
            ?: intent.getStringExtra(AutofillIntents.EXTRA_PACKAGE_NAME)
            ?: "当前登录页面"

    private fun targetKey(): String =
        intent.getStringExtra(AutofillIntents.EXTRA_WEB_DOMAIN)
            ?.lowercase()
            ?.let { "web:$it" }
            ?: "app:${intent.getStringExtra(AutofillIntents.EXTRA_PACKAGE_NAME).orEmpty().lowercase()}"

    private fun cancelAndFinish() {
        setResult(Activity.RESULT_CANCELED)
        finish()
    }

    private fun setWorking(value: Boolean) {
        working = value
        progress.visibility = if (value) View.VISIBLE else View.GONE
        biometricButton.isEnabled = !value
        unlockButton.isEnabled = !value
        saveButton.isEnabled = !value
        candidateList.isEnabled = !value
    }

    private fun showError(message: String) {
        errorView.text = if (message.contains("主密码错误或加密文件已损坏")) {
            "主密码错误"
        } else {
            message
        }
        errorView.visibility = View.VISIBLE
    }

    private fun hideError() {
        errorView.visibility = View.GONE
        errorView.text = ""
    }

    private fun <T> runNative(operation: () -> T, onSuccess: (T) -> Unit) {
        if (working) return
        setWorking(true)
        hideError()
        executor.execute {
            val result = runCatching(operation)
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                setWorking(false)
                result.onSuccess(onSuccess).onFailure { error ->
                    if (error is AutofillNativeException &&
                        error.code == "BIOMETRIC_CREDENTIAL_INVALID"
                    ) {
                        biometricStore.delete()
                    }
                    showError(
                        if (error is AutofillNativeException) error.message
                        else "自动填充失败，请重试",
                    )
                }
            }
        }
    }
}

private class SimpleTextWatcher(
    private val onChanged: (String) -> Unit,
) : android.text.TextWatcher {
    override fun beforeTextChanged(value: CharSequence?, start: Int, count: Int, after: Int) = Unit

    override fun onTextChanged(value: CharSequence?, start: Int, before: Int, count: Int) {
        onChanged(value?.toString().orEmpty())
    }

    override fun afterTextChanged(value: android.text.Editable?) = Unit
}
