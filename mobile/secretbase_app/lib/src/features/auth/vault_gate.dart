import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:secretbase/src/core/biometric_unlock.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/android_back_exit_guard.dart';
import 'package:secretbase/src/core/widgets/brand_mark.dart';
import 'package:secretbase/src/rust/mobile/error.dart';
import 'package:secretbase/src/state/vault_controller.dart';

class VaultGate extends ConsumerStatefulWidget {
  const VaultGate({super.key});

  @override
  ConsumerState<VaultGate> createState() => _VaultGateState();
}

class _VaultGateState extends ConsumerState<VaultGate> {
  final _formKey = GlobalKey<FormState>();
  final _passwordController = TextEditingController();
  final _confirmController = TextEditingController();
  bool _obscurePassword = true;
  bool _obscureConfirm = true;
  bool _biometricBusy = false;
  bool _biometricAttempted = false;
  bool _biometricPromptScheduled = false;
  String? _error;

  @override
  void dispose() {
    _passwordController.dispose();
    _confirmController.dispose();
    super.dispose();
  }

  Future<void> _submit(VaultPhase phase) async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() => _error = null);
    try {
      final controller = ref.read(vaultControllerProvider.notifier);
      if (phase == VaultPhase.setup) {
        await controller.create(_passwordController.text);
      } else {
        await controller.unlock(_passwordController.text);
      }
      await _dismissKeyboard();
      if (mounted) context.go('/vault');
    } catch (error) {
      if (mounted) setState(() => _error = mobileUnlockErrorMessage(error));
    }
  }

  Future<void> _unlockWithBiometric({required bool automatic}) async {
    if (_biometricBusy || !mounted) return;
    if (automatic && _biometricAttempted) return;
    if (automatic) _biometricAttempted = true;
    await _dismissKeyboard();
    if (!mounted) return;

    final platform = ref.read(biometricPlatformProvider);
    Uint8List? credential;
    try {
      final status = await platform.status();
      if (!status.enrolled || !status.credentialStored || !mounted) return;
      setState(() {
        _biometricBusy = true;
        _error = null;
      });
      credential = await platform.readCredential();
      await ref
          .read(vaultControllerProvider.notifier)
          .unlockWithDeviceCredential(credential);
      await _dismissKeyboard();
      if (mounted) context.go('/vault');
    } catch (error) {
      if (error is BiometricException && error.canceled) return;
      final invalidCredential =
          (error is MobileError_Failure &&
              error.code == 'BIOMETRIC_CREDENTIAL_INVALID') ||
          (error is BiometricException &&
              error.code == 'BIOMETRIC_CREDENTIAL_INVALID');
      if (invalidCredential) {
        try {
          await platform.deleteCredential();
        } catch (_) {
          // The Rust salt check still prevents a stale credential from unlocking.
        }
        ref.invalidate(biometricStatusProvider);
      }
      if (mounted) {
        setState(() {
          _error = error is MobileError_Failure
              ? mobileErrorMessage(error)
              : biometricErrorMessage(error);
        });
      }
    } finally {
      if (credential != null) clearSensitiveBytes(credential);
      if (mounted) setState(() => _biometricBusy = false);
    }
  }

  Future<void> _dismissKeyboard() async {
    FocusManager.instance.primaryFocus?.unfocus();
    try {
      await SystemChannels.textInput.invokeMethod<void>('TextInput.hide');
    } catch (_) {
      // The native biometric bridge still restores window insets on Android.
    }
    if (mounted) await WidgetsBinding.instance.endOfFrame;
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(vaultControllerProvider);
    final biometricStatus = ref.watch(biometricStatusProvider);
    if (state.phase == VaultPhase.locked &&
        !_biometricAttempted &&
        !_biometricPromptScheduled) {
      _biometricPromptScheduled = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _biometricPromptScheduled = false;
        if (mounted) _unlockWithBiometric(automatic: true);
      });
    } else if (state.phase != VaultPhase.locked) {
      _biometricAttempted = false;
      _biometricPromptScheduled = false;
    }
    return AndroidBackExitGuard(
      child: Scaffold(
        body: switch (state.phase) {
          VaultPhase.booting => const _BootView(),
          VaultPhase.failed => _FailureView(
            message: state.errorMessage ?? '无法初始化本机密码库',
            onRetry: ref.read(vaultControllerProvider.notifier).initialize,
          ),
          VaultPhase.unlocked => const _BootView(),
          VaultPhase.setup || VaultPhase.locked => _buildForm(
            context,
            state,
            biometricStatus.value,
          ),
        },
      ),
    );
  }

  Widget _buildForm(
    BuildContext context,
    VaultUiState state,
    BiometricStatus? biometricStatus,
  ) {
    final creating = state.phase == VaultPhase.setup;
    final scheme = Theme.of(context).colorScheme;
    return SafeArea(
      child: LayoutBuilder(
        builder: (context, constraints) {
          return SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 22),
            child: ConstrainedBox(
              constraints: BoxConstraints(
                minHeight: constraints.maxHeight - 44,
              ),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 460),
                  child: Form(
                    key: _formKey,
                    child: AutofillGroup(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Align(
                            alignment: Alignment.centerLeft,
                            child: BrandMark(),
                          ),
                          const SizedBox(height: 32),
                          Text(
                            creating ? '创建本机密码库' : '解锁密码库',
                            style: Theme.of(context).textTheme.headlineSmall
                                ?.copyWith(fontWeight: FontWeight.w800),
                          ),
                          const SizedBox(height: 9),
                          Text(
                            creating
                                ? '设置用于本机加密的主密码。主密码无法找回。'
                                : '输入主密码继续访问本机数据。',
                            style: Theme.of(context).textTheme.bodyMedium
                                ?.copyWith(color: scheme.onSurfaceVariant),
                          ),
                          const SizedBox(height: 22),
                          TextFormField(
                            controller: _passwordController,
                            obscureText: _obscurePassword,
                            autofocus: creating,
                            autofillHints: [
                              creating
                                  ? AutofillHints.newPassword
                                  : AutofillHints.password,
                            ],
                            textInputAction: creating
                                ? TextInputAction.next
                                : TextInputAction.done,
                            decoration: InputDecoration(
                              labelText: '主密码',
                              prefixIcon: const Icon(Icons.lock_outline),
                              suffixIcon: IconButton(
                                tooltip: _obscurePassword ? '显示主密码' : '隐藏主密码',
                                onPressed: () => setState(
                                  () => _obscurePassword = !_obscurePassword,
                                ),
                                icon: Icon(
                                  _obscurePassword
                                      ? Icons.visibility_outlined
                                      : Icons.visibility_off_outlined,
                                ),
                              ),
                            ),
                            validator: (value) {
                              if ((value ?? '').isEmpty) return '请输入主密码';
                              if (creating && value!.characters.length < 8) {
                                return '主密码至少需要 8 个字符';
                              }
                              return null;
                            },
                            onFieldSubmitted: creating
                                ? null
                                : (_) => _submit(state.phase),
                          ),
                          if (creating) ...[
                            const SizedBox(height: 14),
                            TextFormField(
                              controller: _confirmController,
                              obscureText: _obscureConfirm,
                              autofillHints: const [AutofillHints.newPassword],
                              textInputAction: TextInputAction.done,
                              decoration: InputDecoration(
                                labelText: '确认主密码',
                                prefixIcon: const Icon(
                                  Icons.verified_user_outlined,
                                ),
                                suffixIcon: IconButton(
                                  tooltip: _obscureConfirm
                                      ? '显示确认密码'
                                      : '隐藏确认密码',
                                  onPressed: () => setState(
                                    () => _obscureConfirm = !_obscureConfirm,
                                  ),
                                  icon: Icon(
                                    _obscureConfirm
                                        ? Icons.visibility_outlined
                                        : Icons.visibility_off_outlined,
                                  ),
                                ),
                              ),
                              validator: (value) =>
                                  value == _passwordController.text
                                  ? null
                                  : '两次输入的主密码不一致',
                              onFieldSubmitted: (_) => _submit(state.phase),
                            ),
                          ],
                          if (_error != null) ...[
                            const SizedBox(height: 14),
                            _InlineError(message: _error!),
                          ],
                          const SizedBox(height: 22),
                          if (!creating &&
                              biometricStatus?.credentialStored == true) ...[
                            OutlinedButton.icon(
                              onPressed: state.busy || _biometricBusy
                                  ? null
                                  : () =>
                                        _unlockWithBiometric(automatic: false),
                              icon: _biometricBusy
                                  ? const SizedBox(
                                      width: 18,
                                      height: 18,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                      ),
                                    )
                                  : const Icon(Icons.fingerprint),
                              label: const Text('使用指纹解锁'),
                            ),
                            const SizedBox(height: 10),
                          ],
                          FilledButton.icon(
                            onPressed: state.busy || _biometricBusy
                                ? null
                                : () => _submit(state.phase),
                            icon: state.busy
                                ? const SizedBox(
                                    width: 18,
                                    height: 18,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                    ),
                                  )
                                : Icon(
                                    creating
                                        ? Icons.add_moderator_outlined
                                        : Icons.lock_open,
                                  ),
                            label: Text(creating ? '创建并进入' : '解锁'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _BootView extends StatelessWidget {
  const _BootView();

  @override
  Widget build(BuildContext context) {
    return const SafeArea(
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            BrandMark(),
            SizedBox(height: 28),
            SizedBox(
              width: 26,
              height: 26,
              child: CircularProgressIndicator(strokeWidth: 2.5),
            ),
          ],
        ),
      ),
    );
  }
}

class _FailureView extends StatelessWidget {
  const _FailureView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const BrandMark(),
                const SizedBox(height: 32),
                Icon(
                  Icons.warning_amber_rounded,
                  size: 40,
                  color: Theme.of(context).colorScheme.error,
                ),
                const SizedBox(height: 12),
                Text(message, textAlign: TextAlign.center),
                const SizedBox(height: 18),
                OutlinedButton.icon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh),
                  label: const Text('重新初始化'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _InlineError extends StatelessWidget {
  const _InlineError({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.error_outline, size: 19, color: scheme.onErrorContainer),
          const SizedBox(width: 9),
          Expanded(
            child: Text(
              message,
              style: TextStyle(color: scheme.onErrorContainer),
            ),
          ),
        ],
      ),
    );
  }
}
