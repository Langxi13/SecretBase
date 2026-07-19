import 'package:flutter/material.dart';

/// 创建或加入同步空间时使用的表单。
///
/// 控制器由上层协调器持有，组件只负责输入状态、校验和展示，避免把
/// WebDAV 网络操作与大段表单布局耦合在同一个文件中。
class MobileSyncSetupForm extends StatefulWidget {
  const MobileSyncSetupForm({
    required this.url,
    required this.username,
    required this.password,
    required this.recovery,
    required this.device,
    required this.joining,
    required this.working,
    required this.mergeExisting,
    required this.autoSync,
    required this.onJoiningChanged,
    required this.onMergeChanged,
    required this.onAutoSyncChanged,
    required this.onScanPairing,
    required this.onPastePairing,
    required this.onTestConnection,
    required this.onSubmit,
    this.errorMessage,
    this.connectionTestPassed = false,
    this.onReload,
    this.onInputChanged,
    super.key,
  });

  final TextEditingController url;
  final TextEditingController username;
  final TextEditingController password;
  final TextEditingController recovery;
  final TextEditingController device;
  final bool joining;
  final bool working;
  final bool mergeExisting;
  final bool autoSync;
  final ValueChanged<bool> onJoiningChanged;
  final ValueChanged<bool> onMergeChanged;
  final ValueChanged<bool> onAutoSyncChanged;
  final VoidCallback onScanPairing;
  final VoidCallback onPastePairing;
  final VoidCallback onTestConnection;
  final VoidCallback onSubmit;
  final String? errorMessage;
  final bool connectionTestPassed;
  final VoidCallback? onReload;
  final VoidCallback? onInputChanged;

  @override
  State<MobileSyncSetupForm> createState() => _MobileSyncSetupFormState();
}

class _MobileSyncSetupFormState extends State<MobileSyncSetupForm> {
  bool _obscurePassword = true;

  @override
  void initState() {
    super.initState();
    _bindControllers(widget);
  }

  @override
  void didUpdateWidget(covariant MobileSyncSetupForm oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.url != widget.url ||
        oldWidget.username != widget.username ||
        oldWidget.password != widget.password ||
        oldWidget.recovery != widget.recovery ||
        oldWidget.device != widget.device) {
      _unbindControllers(oldWidget);
      _bindControllers(widget);
    }
  }

  @override
  void dispose() {
    _unbindControllers(widget);
    super.dispose();
  }

  void _bindControllers(MobileSyncSetupForm form) {
    for (final controller in _controllers(form)) {
      controller.addListener(_rebuild);
    }
  }

  void _unbindControllers(MobileSyncSetupForm form) {
    for (final controller in _controllers(form)) {
      controller.removeListener(_rebuild);
    }
  }

  Iterable<TextEditingController> _controllers(MobileSyncSetupForm form) sync* {
    yield form.url;
    yield form.username;
    yield form.password;
    yield form.recovery;
    yield form.device;
  }

  void _rebuild() {
    if (mounted) setState(() {});
  }

  void _inputChanged(String _) {
    widget.onInputChanged?.call();
    _rebuild();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SegmentedButton<bool>(
          segments: const [
            ButtonSegment(
              value: false,
              label: Text('创建空间'),
              icon: Icon(Icons.add_link_outlined),
            ),
            ButtonSegment(
              value: true,
              label: Text('加入空间'),
              icon: Icon(Icons.login_outlined),
            ),
          ],
          selected: {widget.joining},
          onSelectionChanged: widget.working
              ? null
              : (value) => widget.onJoiningChanged(value.first),
        ),
        const SizedBox(height: 14),
        _field(
          widget.url,
          'WebDAV 地址',
          'https://dav.example/secretbase',
          keyboardType: TextInputType.url,
        ),
        _field(
          widget.username,
          '用户名',
          'WebDAV 用户名',
          keyboardType: TextInputType.emailAddress,
        ),
        _passwordField(),
        _field(widget.device, '设备名称', '例如：我的 Android 手机'),
        if (widget.joining) ...[
          _field(widget.recovery, 'SBSYNC2 恢复码', '从已配置设备复制', maxLines: 3),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              OutlinedButton.icon(
                onPressed: widget.working ? null : widget.onScanPairing,
                icon: const Icon(Icons.qr_code_scanner_outlined),
                label: const Text('扫描二维码'),
              ),
              TextButton.icon(
                onPressed: widget.working ? null : widget.onPastePairing,
                icon: const Icon(Icons.content_paste_outlined),
                label: const Text('粘贴配对链接'),
              ),
            ],
          ),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            dense: true,
            value: widget.mergeExisting,
            onChanged: widget.working
                ? null
                : (value) => widget.onMergeChanged(value ?? false),
            title: const Text('当前 Vault 有数据时尝试合并'),
          ),
        ],
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          dense: true,
          value: widget.autoSync,
          onChanged: widget.working ? null : widget.onAutoSyncChanged,
          title: const Text('自动同步'),
        ),
        const SizedBox(height: 8),
        Text(
          '使用不可变加密快照，不要求 WebDAV 提供 ETag；密码字段和值不会以明文上传。',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        if (widget.joining && widget.recovery.text.trim().isEmpty) ...[
          const SizedBox(height: 10),
          _feedbackPanel(
            '加入现有空间还需要同步恢复码，或先扫描/粘贴配对信息。测试连接只验证 WebDAV，不会替代恢复码。',
            warning: true,
          ),
        ],
        if (widget.connectionTestPassed) ...[
          const SizedBox(height: 10),
          _feedbackPanel('WebDAV 连接测试已通过，可以继续提交配置。', success: true),
        ],
        if (widget.errorMessage != null && widget.errorMessage!.isNotEmpty) ...[
          const SizedBox(height: 10),
          _feedbackPanel(widget.errorMessage!, onReload: widget.onReload),
        ],
        const SizedBox(height: 14),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          alignment: WrapAlignment.end,
          children: [
            OutlinedButton.icon(
              onPressed: widget.working ? null : widget.onTestConnection,
              icon: const Icon(Icons.network_check_outlined),
              label: const Text('测试连接'),
            ),
            FilledButton.icon(
              onPressed: widget.working ? null : widget.onSubmit,
              icon: Icon(
                widget.joining ? Icons.login : Icons.cloud_upload_outlined,
              ),
              label: Text(
                widget.working
                    ? '处理中...'
                    : widget.joining
                    ? '加入并同步'
                    : '创建并上传',
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _feedbackPanel(
    String message, {
    bool warning = false,
    bool success = false,
    VoidCallback? onReload,
  }) {
    final scheme = Theme.of(context).colorScheme;
    final background = success
        ? scheme.tertiaryContainer
        : warning
        ? scheme.secondaryContainer
        : scheme.errorContainer;
    final foreground = success
        ? scheme.onTertiaryContainer
        : warning
        ? scheme.onSecondaryContainer
        : scheme.onErrorContainer;
    return Material(
      color: background,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              success
                  ? Icons.check_circle_outline
                  : warning
                  ? Icons.info_outline
                  : Icons.error_outline,
              size: 18,
              color: foreground,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(message, style: TextStyle(color: foreground)),
            ),
            if (onReload != null) ...[
              const SizedBox(width: 8),
              TextButton(onPressed: onReload, child: const Text('重新读取')),
            ],
          ],
        ),
      ),
    );
  }

  Widget _passwordField() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: TextField(
        controller: widget.password,
        obscureText: _obscurePassword,
        autocorrect: false,
        enableSuggestions: false,
        onChanged: _inputChanged,
        textInputAction: TextInputAction.next,
        decoration: InputDecoration(
          labelText: '应用密码',
          hintText: '不会上传到 AI 或写入界面偏好',
          border: const OutlineInputBorder(),
          isDense: true,
          suffixIcon: IconButton(
            tooltip: _obscurePassword ? '显示密码' : '隐藏密码',
            onPressed: () =>
                setState(() => _obscurePassword = !_obscurePassword),
            icon: Icon(
              _obscurePassword
                  ? Icons.visibility_outlined
                  : Icons.visibility_off_outlined,
            ),
          ),
        ),
      ),
    );
  }

  Widget _field(
    TextEditingController controller,
    String label,
    String hint, {
    TextInputType? keyboardType,
    int maxLines = 1,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: TextField(
        controller: controller,
        maxLines: maxLines,
        keyboardType: keyboardType,
        autocorrect: false,
        enableSuggestions: false,
        onChanged: _inputChanged,
        decoration: InputDecoration(
          labelText: label,
          hintText: hint,
          border: const OutlineInputBorder(),
          isDense: true,
        ),
      ),
    );
  }
}
