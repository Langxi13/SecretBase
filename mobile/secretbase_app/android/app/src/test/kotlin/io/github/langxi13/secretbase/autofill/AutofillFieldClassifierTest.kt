package io.github.langxi13.secretbase.autofill

import android.text.InputType
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AutofillFieldClassifierTest {
    @Test
    fun currentPasswordRanksAsExistingCredential() {
        val result = AutofillFieldClassifier.password(
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD,
            "current-password password",
        )

        assertTrue(result.score >= 100)
        assertFalse(result.isNew)
    }

    @Test
    fun newPasswordIsSeparatedFromExistingCredentialFill() {
        val result = AutofillFieldClassifier.password(
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD,
            "new-password password",
        )

        assertTrue(result.score > 0)
        assertTrue(result.isNew)
    }

    @Test
    fun emailFieldRanksAsUsername() {
        val score = AutofillFieldClassifier.usernameScore(
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS,
            "email",
        )

        assertTrue(score >= 100)
    }
}
