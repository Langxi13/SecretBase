import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/features/update/mobile_update_controller.dart';

class MobileUpdateCoordinator extends ConsumerStatefulWidget {
  const MobileUpdateCoordinator({required this.child, super.key});

  final Widget child;

  @override
  ConsumerState<MobileUpdateCoordinator> createState() =>
      _MobileUpdateCoordinatorState();
}

class _MobileUpdateCoordinatorState
    extends ConsumerState<MobileUpdateCoordinator>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        unawaited(
          ref.read(mobileUpdateControllerProvider.notifier).maybeCheck(),
        );
      }
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(ref.read(mobileUpdateControllerProvider.notifier).maybeCheck());
    }
  }

  @override
  Widget build(BuildContext context) => widget.child;
}

class MobileUpdateBanner extends ConsumerWidget {
  const MobileUpdateBanner({this.onOpenSettings, super.key});

  final VoidCallback? onOpenSettings;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(mobileUpdateControllerProvider);
    if (!const {
      MobileUpdatePhase.available,
      MobileUpdatePhase.downloading,
      MobileUpdatePhase.ready,
      MobileUpdatePhase.reinstallRequired,
    }.contains(state.phase)) {
      return const SizedBox.shrink();
    }
    final scheme = Theme.of(context).colorScheme;
    final ready = state.phase == MobileUpdatePhase.ready;
    return Material(
      color: ready ? scheme.primaryContainer : scheme.secondaryContainer,
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
          child: Row(
            children: [
              Icon(
                ready ? Icons.system_update_alt : Icons.update,
                size: 19,
                color: ready
                    ? scheme.onPrimaryContainer
                    : scheme.onSecondaryContainer,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  switch (state.phase) {
                    MobileUpdatePhase.downloading =>
                      '正在下载 ${state.asset?.version ?? ''} · ${state.progress}%',
                    MobileUpdatePhase.ready =>
                      '${state.asset?.version ?? '新版本'} 已准备安装',
                    MobileUpdatePhase.reinstallRequired => '当前测试版需要迁移到正式签名版本',
                    _ =>
                      state.downloadedBytes > 0
                          ? '更新已暂停 · ${state.progress}%'
                          : '发现新版本 ${state.asset?.version ?? ''}',
                  },
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(
                    context,
                  ).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w700),
                ),
              ),
              TextButton(onPressed: onOpenSettings, child: const Text('查看')),
            ],
          ),
        ),
      ),
    );
  }
}
