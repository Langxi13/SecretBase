import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
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
      label: 'AI',
    ),
    NavigationDestination(
      icon: Icon(Icons.settings_outlined),
      selectedIcon: Icon(Icons.settings),
      label: '设置',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    ref.listen(vaultControllerProvider, (previous, next) {
      if (previous?.phase == VaultPhase.unlocked &&
          next.phase != VaultPhase.unlocked) {
        context.go('/');
      }
    });

    final width = MediaQuery.sizeOf(context).width;
    final wide = width >= 840;
    final extendedRail = width >= 1120;
    final body = IndexedStack(
      index: _index,
      children: [
        EntriesScreen(preset: _entryPreset),
        GroupsScreen(onOpenGroup: _openGroup),
        TagsScreen(onOpenTag: _openTag),
        const AiManagerScreen(),
        const SettingsScreen(),
      ],
    );

    if (wide) {
      return Scaffold(
        body: SafeArea(
          child: Row(
            children: [
              NavigationRail(
                selectedIndex: _index,
                onDestinationSelected: (value) =>
                    setState(() => _index = value),
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
      );
    }

    return Scaffold(
      body: SafeArea(child: body),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (value) => setState(() => _index = value),
        destinations: _destinations,
      ),
    );
  }

  void _openGroup(String name) {
    setState(() {
      _filterGeneration += 1;
      _entryPreset = EntryFilterPreset(
        group: name,
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
        generation: _filterGeneration,
      );
      _index = 0;
    });
  }
}
