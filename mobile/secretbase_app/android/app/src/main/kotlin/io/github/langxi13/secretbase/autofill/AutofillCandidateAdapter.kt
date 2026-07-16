package io.github.langxi13.secretbase.autofill

import android.content.Context
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.BaseAdapter
import android.widget.TextView
import io.github.langxi13.secretbase.R

internal class AutofillCandidateAdapter(context: Context) : BaseAdapter() {
    private val inflater = LayoutInflater.from(context)
    private var items: List<NativeAutofillCandidate> = emptyList()

    fun submit(values: List<NativeAutofillCandidate>) {
        items = values
        notifyDataSetChanged()
    }

    override fun getCount(): Int = items.size

    override fun getItem(position: Int): NativeAutofillCandidate = items[position]

    override fun getItemId(position: Int): Long = items[position].entryId.hashCode().toLong()

    override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
        val view: View
        val holder: Holder
        if (convertView == null) {
            view = inflater.inflate(R.layout.autofill_candidate_item, parent, false)
            holder = Holder(
                title = view.findViewById(R.id.autofill_candidate_title),
                account = view.findViewById(R.id.autofill_candidate_account),
                match = view.findViewById(R.id.autofill_candidate_match),
            )
            view.tag = holder
        } else {
            view = convertView
            holder = convertView.tag as Holder
        }
        val item = getItem(position)
        holder.title.text = item.title
        holder.account.text = item.usernamePreview.ifBlank {
            item.usernameField?.let { "账号字段：$it" } ?: "仅填充密码"
        }
        holder.match.text = if (item.mappingConfident) {
            item.matchLabel
        } else {
            "${item.matchLabel} · 需确认字段"
        }
        return view
    }

    private data class Holder(
        val title: TextView,
        val account: TextView,
        val match: TextView,
    )
}
