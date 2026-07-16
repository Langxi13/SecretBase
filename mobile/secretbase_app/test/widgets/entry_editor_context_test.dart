import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/features/entries/entry_editor_dialog.dart';
import 'package:secretbase/src/rust/mobile/models.dart';

void main() {
  testWidgets('new entry inherits the active password group', (tester) async {
    const group = TaxonomyRecord(
      name: '工作账号',
      description: '',
      color: '#006B68',
      count: 8,
    );

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: Scaffold(
            body: Consumer(
              builder: (context, ref, child) => SizedBox(
                width: 900,
                height: 760,
                child: EntryEditorDialog(
                  availableTags: const [],
                  availableGroups: const [group],
                  initialGroups: const {'工作账号'},
                  ref: ref,
                ),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('工作账号'), findsOneWidget);
    expect(find.text('新建条目'), findsOneWidget);
  });
}
