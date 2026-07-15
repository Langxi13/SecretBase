import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/responsive_dialog.dart';
import 'package:secretbase/src/features/ai/ai_activity_controller.dart';
import 'package:secretbase/src/features/ai/ai_transport.dart';
import 'package:secretbase/src/features/ai/ai_providers.dart';
import 'package:secretbase/src/rust/api/mobile.dart' as rust_api;
import 'package:secretbase/src/rust/mobile/models.dart';

Future<AiStatus?> showAiSettingsDialog({
  required BuildContext context,
  required WidgetRef ref,
}) {
  return showResponsiveDialog<AiStatus>(
    context: context,
    dismissible: false,
    maxWidth: 660,
    builder: (_) => const AiSettingsDialog(),
  );
}

class AiSettingsDialog extends ConsumerStatefulWidget {
  const AiSettingsDialog({super.key});

  @override
  ConsumerState<AiSettingsDialog> createState() => _AiSettingsDialogState();
}

class _AiSettingsDialogState extends ConsumerState<AiSettingsDialog> {
  final _baseUrlController = TextEditingController();
  final _apiKeyController = TextEditingController();
  final _modelController = TextEditingController();
  AiStatus? _status;
  List<String> _models = [];
  String? _model;
  String _providerId = 'deepseek';
  bool _manualModel = false;
  bool _loading = true;
  bool _working = false;
  bool _obscureKey = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _baseUrlController.dispose();
    _apiKeyController.dispose();
    _modelController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final status = await rust_api.aiStatus();
      if (!mounted) return;
      setState(() {
        _status = status;
        _baseUrlController.text = status.configured
            ? status.baseUrl
            : aiProviderById('deepseek').baseUrl;
        _providerId = status.configured
            ? inferAiProviderId(status.baseUrl)
            : 'deepseek';
        _model = status.configured ? status.model : null;
        _modelController.text = _model ?? '';
        if (_model != null) _models = [_model!];
        _loading = false;
      });
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = mobileErrorMessage(error);
          _loading = false;
        });
      }
    }
  }

  Future<void> _fetchModels() async {
    final activity = ref.read(aiActivityControllerProvider.notifier);
    if (!activity.start()) {
      setState(() => _error = '当前 AI 请求完成后才能获取模型列表');
      return;
    }
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      final request = await rust_api.prepareAiModelsRequest(
        baseUrl: _baseUrlController.text,
        apiKey: _apiKeyController.text,
      );
      final response = await AiTransport.send(request);
      final models = await rust_api.parseAiModelsResponse(content: response);
      if (!mounted) return;
      setState(() {
        _models = models;
        _model = models.contains(_model) ? _model : models.first;
        _modelController.text = _model ?? '';
        _manualModel = false;
        _working = false;
      });
    } catch (error) {
      if (mounted) {
        setState(() {
          _working = false;
          _manualModel = true;
          _modelController.text = _model ?? '';
          _error = '${_errorMessage(error)}，可以手动填写模型 ID';
        });
      }
    } finally {
      activity.finish();
    }
  }

  Future<void> _save() async {
    final model = (_manualModel ? _modelController.text : _model ?? '').trim();
    if (model.isEmpty) {
      setState(() => _error = '请选择或填写模型 ID');
      return;
    }
    final activity = ref.read(aiActivityControllerProvider.notifier);
    if (!activity.start()) {
      setState(() => _error = '当前 AI 请求完成后才能修改服务设置');
      return;
    }
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      final request = await rust_api.prepareAiVerifyRequest(
        baseUrl: _baseUrlController.text,
        apiKey: _apiKeyController.text,
        model: model,
      );
      final response = await AiTransport.send(request);
      await rust_api.verifyAiResponse(content: response);
      final status = await rust_api.saveAiSettings(
        baseUrl: _baseUrlController.text,
        apiKey: _apiKeyController.text,
        model: model,
      );
      if (mounted) Navigator.of(context).pop(status);
    } catch (error) {
      if (mounted) {
        setState(() {
          _working = false;
          _error = _errorMessage(error);
        });
      }
    } finally {
      activity.finish();
    }
  }

  void _selectProvider(String? value) {
    if (value == null || value == _providerId) return;
    final provider = aiProviderById(value);
    setState(() {
      _providerId = value;
      _baseUrlController.text = provider.baseUrl;
      _apiKeyController.clear();
      _models = [];
      _model = null;
      _modelController.clear();
      _manualModel = false;
      _error = provider.aggregator
          ? 'OpenRouter 是聚合服务，请同时确认其隐私政策和实际模型供应方。'
          : null;
    });
  }

  void _resetOfficialUrl() {
    final provider = aiProviderById(_providerId);
    if (provider.baseUrl.isEmpty) return;
    setState(() => _baseUrlController.text = provider.baseUrl);
  }

  Future<void> _clear() async {
    if (ref.read(aiActivityControllerProvider)) {
      setState(() => _error = '当前 AI 请求完成后才能清除服务设置');
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('清除 AI 设置'),
        content: const Text('确认清除本机加密保存的 AI 服务配置？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('清除'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    final status = await rust_api.clearAiSettings();
    if (mounted) Navigator.of(context).pop(status);
  }

  @override
  Widget build(BuildContext context) {
    final anotherRequestActive = ref.watch(aiActivityControllerProvider);
    final blocked = _working || anotherRequestActive;
    return DialogFrame(
      title: 'AI 服务设置',
      onClose: _working ? () {} : null,
      child: _loading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        if (anotherRequestActive && !_working) ...[
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: Theme.of(
                                context,
                              ).colorScheme.secondaryContainer,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: const Text('当前 AI 请求正在后台处理，完成后即可修改服务设置。'),
                          ),
                          const SizedBox(height: 14),
                        ],
                        DropdownButtonFormField<String>(
                          initialValue: _providerId,
                          isExpanded: true,
                          decoration: const InputDecoration(
                            labelText: '服务厂商',
                            prefixIcon: Icon(Icons.hub_outlined),
                          ),
                          items: aiProviderPresets
                              .map(
                                (provider) => DropdownMenuItem(
                                  value: provider.id,
                                  child: Text(
                                    provider.aggregator
                                        ? '${provider.name}（聚合服务）'
                                        : provider.name,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              )
                              .toList(),
                          onChanged: blocked ? null : _selectProvider,
                        ),
                        const SizedBox(height: 14),
                        TextField(
                          controller: _baseUrlController,
                          enabled: !blocked,
                          keyboardType: TextInputType.url,
                          decoration: InputDecoration(
                            labelText: 'Base URL',
                            prefixIcon: const Icon(Icons.cloud_outlined),
                            hintText: 'https://api.example.com/v1',
                            helperText: '自动填充后仍可手动修改，仅支持 HTTPS',
                            suffixIcon: _providerId == 'custom'
                                ? null
                                : IconButton(
                                    tooltip: '恢复官方地址',
                                    onPressed: blocked
                                        ? null
                                        : _resetOfficialUrl,
                                    icon: const Icon(Icons.restart_alt),
                                  ),
                          ),
                        ),
                        const SizedBox(height: 14),
                        TextField(
                          controller: _apiKeyController,
                          enabled: !blocked,
                          obscureText: _obscureKey,
                          decoration: InputDecoration(
                            labelText: 'API Key',
                            prefixIcon: const Icon(Icons.vpn_key_outlined),
                            hintText: _status?.configured == true
                                ? '留空则继续使用 ${_status!.apiKeyMask}'
                                : null,
                            suffixIcon: IconButton(
                              tooltip: _obscureKey
                                  ? '显示 API Key'
                                  : '隐藏 API Key',
                              onPressed: () =>
                                  setState(() => _obscureKey = !_obscureKey),
                              icon: Icon(
                                _obscureKey
                                    ? Icons.visibility_outlined
                                    : Icons.visibility_off_outlined,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 14),
                        OutlinedButton.icon(
                          onPressed: blocked ? null : _fetchModels,
                          icon: const Icon(Icons.sync, size: 18),
                          label: const Text('获取模型列表'),
                        ),
                        const SizedBox(height: 8),
                        TextButton.icon(
                          onPressed: blocked
                              ? null
                              : () => setState(() {
                                  _manualModel = true;
                                  _modelController.text = _model ?? '';
                                }),
                          icon: const Icon(Icons.edit_outlined, size: 18),
                          label: const Text('手动填写模型 ID'),
                        ),
                        const SizedBox(height: 14),
                        if (_manualModel)
                          TextField(
                            controller: _modelController,
                            enabled: !blocked,
                            decoration: const InputDecoration(
                              labelText: '模型 ID',
                              prefixIcon: Icon(Icons.memory_outlined),
                              hintText: '填写厂商控制台中的模型 ID',
                            ),
                          )
                        else
                          DropdownButtonFormField<String>(
                            initialValue: _models.contains(_model)
                                ? _model
                                : null,
                            isExpanded: true,
                            decoration: const InputDecoration(
                              labelText: '模型',
                              prefixIcon: Icon(Icons.memory_outlined),
                            ),
                            items: _models
                                .map(
                                  (model) => DropdownMenuItem(
                                    value: model,
                                    child: Text(
                                      model,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                )
                                .toList(),
                            onChanged: blocked
                                ? null
                                : (value) => setState(() => _model = value),
                          ),
                        if (_error != null) ...[
                          const SizedBox(height: 16),
                          Text(
                            _error!,
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.error,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
                if (_working) const LinearProgressIndicator(minHeight: 2),
                const Divider(height: 1),
                SafeArea(
                  top: false,
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Row(
                      children: [
                        if (_status?.configured == true)
                          TextButton.icon(
                            onPressed: blocked ? null : _clear,
                            icon: const Icon(Icons.delete_outline, size: 18),
                            label: const Text('清除设置'),
                          ),
                        const Spacer(),
                        TextButton(
                          onPressed: _working
                              ? null
                              : () => Navigator.of(context).pop(),
                          child: const Text('取消'),
                        ),
                        const SizedBox(width: 8),
                        FilledButton.icon(
                          onPressed: blocked ? null : _save,
                          icon: const Icon(Icons.verified_outlined, size: 18),
                          label: Text(_working ? '验证中' : '验证并保存'),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }

  String _errorMessage(Object error) {
    if (error is AiTransportException) return error.message;
    return mobileErrorMessage(error);
  }
}
