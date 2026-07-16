package io.github.langxi13.secretbase.autofill

import java.util.concurrent.atomic.AtomicBoolean

internal object AutofillVaultChangeNotifier {
    private val changed = AtomicBoolean(false)

    fun notifyVaultChanged() {
        changed.set(true)
    }

    fun consumeVaultChanged(): Boolean = changed.getAndSet(false)
}
