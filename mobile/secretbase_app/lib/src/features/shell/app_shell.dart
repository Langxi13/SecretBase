import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:secretbase/src/core/widgets/android_back_exit_guard.dart';
import 'package:secretbase/src/core/widgets/brand_mark.dart';
import 'package:secretbase/src/features/ai/ai_manager_screen.dart';
import 'package:secretbase/src/features/entries/entries_screen.dart';
import 'package:secretbase/src/features/groups/groups_screen.dart';
import 'package:secretbase/src/features/settings/settings_screen.dart';
import 'package:secretbase/src/features/tags/tags_screen.dart';
import 'package:secretbase/src/state/vault_controller.dart';

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  int _index = 0;
  int _filterGeneration = 0;
  EntryFilterPreset _entryPreset = const EntryFilterPreset();
  bool _exiting = false;

  static const _destinations = [
    NavigationDestination(
      icon: Icon(Icons.key_outlined),
      selectedIcon: Icon(Icons.key),
      label: '条目',
    ),
    NavigationDestination(
      icon: Icon(Icons.folder_outlined),
      selectedIcon: Icon(Icons.folder),
      label: '密码组',
    ),
    NavigationDestination(
      icon: Icon(Icons.sell_outlined),
      selectedIcon: Icon(Icons.sell),
      label: '标签',
    ),
    NavigationDestination(
      icon: Icon(Icons.auto_awesome_outlined),
      selectedIcon: Icon(Icons.auto_awesome),
      label: '管家',
    ),
    NavigationDestination(
      icon: Icon(Icons.settings_outlined),
      selectedIcon: Icon(Icons.settings),
      label: '设置',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final vaultPhase = ref.watch(
      vaultControllerProvider.select((state) => state.phase),
    );
    ref.listen(vaultControllerProvider, (previous, next) {
      if (previous?.phase == VaultPhase.unlocked &&
          next.phase != VaultPhase.unlocked &&
          !_exiting) {
        context.go('/');
      }
    });
    if (vaultPhase != VaultPhase.unlocked && !_exiting) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) context.go('/');
      });
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    final width = MediaQuery.sizeOf(context).width;
    final wide = width >= 840;
    final extendedRail = width >= 1120;
    final body = IndexedStack(
      index: _index,
      children: [
        EntriesScreen(
          preset: _entryPreset,
          onExitPreset: _returnFromEntryPreset,
        ),
        GroupsScreen(onOpenGroup: _openGroup),
        TagsScreen(onOpenTag: _openTag),
        const AiManagerScreen(),
        const SettingsScreen(),
      ],
    );

    final scaffold = wide
        ? Scaffold(
            body: SafeArea(
              child: Row(
                children: [
                  NavigationRail(
                    selectedIndex: _index,
                    onDestinationSelected: _selectDestination,
                    extended: extendedRail,
                    leading: Padding(
                      padding: const EdgeInsets.fromLTRB(10, 12, 10, 22),
                      child: extendedRail
                          ? const BrandMark(compact: true)
                          : Container(
                              width: 38,
                              height: 38,
                              decoration: BoxDecoration(
                                color: Theme.of(context).colorScheme.primary,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Icon(
                                Icons.shield_outlined,
                                color: Theme.of(context).colorScheme.onPrimary,
                              ),
                            ),
                    ),
                    destinations: _destinations
                        .map(
                          (item) => NavigationRailDestination(
                            icon: item.icon,
                            selectedIcon: item.selectedIcon,
                            label: Text(item.label),
                          ),
                        )
                        .toList(),
                  ),
                  const VerticalDivider(width: 1),
                  Expanded(child: body),
                ],
              ),
            ),
          )
        : Scaffold(
            body: SafeArea(child: body),
            bottomNavigationBar: DecoratedBox(
              decoration: BoxDecoration(
                border: Border(
                  top: BorderSide(
                    color: Theme.of(context).colorScheme.outlineVariant,
                  ),
                ),
              ),
              child: NavigationBar(
                selectedIndex: _index,
                labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
                onDestinationSelected: _selectDestination,
                destinations: _destinations,
              ),
            ),
          );

    return AndroidBackExitGuard(
      resetToken: '$_index:$_filterGeneration',
      onBeforeExit: _handleBackBeforeExit,
      onExit: _lockBeforeExit,
      child: scaffold,
    );
  }

  void _selectDestination(int value) {
    if (value == _index) return;
    setState(() => _index = value);
  }

  bool _handleBackBeforeExit() {
    if (_entryPreset.origin != null) {
      _returnFromEntryPreset();
      return true;
    }
    if (_index != 0) {
      setState(() {
        _filterGeneration += 1;
        _entryPreset = EntryFilterPreset(generation: _filterGeneration);
        _index = 0;
      });
      return true;
    }
    return false;
  }

  Future<bool> _lockBeforeExit() async {
    _exiting = true;
    try {
      await ref.read(vaultControllerProvider.notifier).lock();
      return true;
    } catch (_) {
      _exiting = false;
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('无法安全锁定密码库，请重试')));
      }
      return false;
    }
  }

  void _openGroup(String name) {
    setState(() {
      _filterGeneration += 1;
      _entryPreset = EntryFilterPreset(
        group: name,
        origin: EntryFilterOrigin.groups,
        generation: _filterGeneration,
      );
      _index = 0;
    });
  }

  void _openTag(String name) {
    setState(() {
      _filterGeneration += 1;
      _entryPreset = EntryFilterPreset(
        tag: name,
        origin: EntryFilterOrigin.tags,
        generation: _filterGeneration,
      );
      _index = 0;
    });
  }

  void _returnFromEntryPreset() {
    final origin = _entryPreset.origin;
    setState(() {
      _filterGeneration += 1;
      _entryPreset = EntryFilterPreset(generation: _filterGeneration);
      _index = switch (origin) {
        EntryFilterOrigin.groups => 1,
        EntryFilterOrigin.tags => 2,
        null => 0,
      };
    });
  }
}
