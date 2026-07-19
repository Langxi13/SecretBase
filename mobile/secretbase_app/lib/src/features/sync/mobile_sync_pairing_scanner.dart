import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:secretbase/src/core/widgets/responsive_dialog.dart';
import 'package:secretbase/src/features/sync/mobile_sync_pairing.dart';

Future<MobileSyncPairing?> showMobileSyncPairingScanner(BuildContext context) {
  return showResponsiveDialog<MobileSyncPairing>(
    context: context,
    maxWidth: 560,
    builder: (_) => const _MobileSyncPairingScanner(),
  );
}

class _MobileSyncPairingScanner extends StatefulWidget {
  const _MobileSyncPairingScanner();

  @override
  State<_MobileSyncPairingScanner> createState() =>
      _MobileSyncPairingScannerState();
}

class _MobileSyncPairingScannerState extends State<_MobileSyncPairingScanner> {
  final _scanner = MobileScannerController();
  final _manual = TextEditingController();
  String? _error;
  String? _lastRejectedValue;
  DateTime? _lastRejectedAt;
  bool _closing = false;

  @override
  void dispose() {
    _scanner.dispose();
    _manual.dispose();
    super.dispose();
  }

  void _handleCapture(BarcodeCapture capture) {
    if (_closing) return;
    for (final barcode in capture.barcodes) {
      final raw = barcode.rawValue?.trim();
      if (raw == null || raw.isEmpty) continue;
      _useValue(raw);
      return;
    }
  }

  void _useValue(String raw) {
    try {
      final pairing = MobileSyncPairing.parse(raw);
      _closing = true;
      _manual.clear();
      unawaited(_clearClipboardIfMatches(raw));
      Navigator.of(context).pop(pairing);
    } on MobileSyncPairingException catch (error) {
      final now = DateTime.now();
      if (_lastRejectedValue == raw &&
          _lastRejectedAt != null &&
          now.difference(_lastRejectedAt!) < const Duration(seconds: 2)) {
        return;
      }
      _lastRejectedValue = raw;
      _lastRejectedAt = now;
      if (mounted) setState(() => _error = error.message);
    }
  }

  Future<void> _toggleTorch() async {
    try {
      await _scanner.toggleTorch();
    } catch (_) {
      if (mounted) {
        setState(() => _error = '当前设备暂不支持闪光灯切换，请直接调整环境光线。');
      }
    }
  }

  Future<void> _clearClipboardIfMatches(String value) async {
    try {
      final current = await Clipboard.getData(Clipboard.kTextPlain);
      if (current?.text?.trim() == value.trim()) {
        await Clipboard.setData(const ClipboardData(text: ''));
      }
    } catch (_) {
      // 清理失败不影响扫码结果，配对链接不会写入应用持久化状态。
    }
  }

  @override
  Widget build(BuildContext context) {
    return DialogFrame(
      title: '扫描同步配对二维码',
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            '二维码只包含 WebDAV 地址、用户名和同步恢复信息，不包含 WebDAV 应用密码。',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 300,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: Stack(
                fit: StackFit.expand,
                children: [
                  MobileScanner(
                    controller: _scanner,
                    onDetect: _handleCapture,
                    errorBuilder: (context, error) => ColoredBox(
                      color: Colors.black,
                      child: Center(
                        child: Padding(
                          padding: const EdgeInsets.all(20),
                          child: Text(
                            '无法打开摄像头，请检查权限后重试；也可以直接粘贴配对链接。',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: Theme.of(
                                context,
                              ).textTheme.bodyMedium?.fontSize,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  Positioned(
                    top: 8,
                    right: 8,
                    child: Material(
                      color: Colors.black54,
                      shape: const CircleBorder(),
                      child: IconButton(
                        tooltip: '切换闪光灯',
                        onPressed: _toggleTorch,
                        color: Colors.white,
                        icon: const Icon(Icons.flash_on_outlined),
                      ),
                    ),
                  ),
                  IgnorePointer(
                    child: Center(
                      child: Container(
                        width: 210,
                        height: 210,
                        decoration: BoxDecoration(
                          border: Border.all(color: Colors.white, width: 2),
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _manual,
            maxLines: 3,
            autocorrect: false,
            enableSuggestions: false,
            onChanged: (_) => setState(() => _error = null),
            decoration: const InputDecoration(
              labelText: '也可以粘贴配对链接',
              hintText: 'secretbase://sync/join?...',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton.tonalIcon(
              onPressed: _manual.text.trim().isEmpty
                  ? null
                  : () => _useValue(_manual.text),
              icon: const Icon(Icons.link_outlined),
              label: const Text('使用配对链接'),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
        ],
      ),
    );
  }
}
