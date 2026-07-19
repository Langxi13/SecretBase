import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/features/entries/entries_screen.dart';
import 'package:secretbase/src/features/shell/app_shell.dart';

void main() {
  test('切换到其他主导航后返回键先回到条目页', () {
    expect(
      resolveAppShellBackAction(
        selectedIndex: 4,
        origin: EntryFilterOrigin.groups,
      ),
      AppShellBackAction.showEntries,
    );
  });

  test('条目页有来源筛选时下一次返回才回到来源分类', () {
    expect(
      resolveAppShellBackAction(
        selectedIndex: 0,
        origin: EntryFilterOrigin.tags,
      ),
      AppShellBackAction.returnToOrigin,
    );
  });

  test('普通条目首页返回交给系统退出守卫', () {
    expect(
      resolveAppShellBackAction(selectedIndex: 0, origin: null),
      AppShellBackAction.none,
    );
  });
}
