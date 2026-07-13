import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'package:secretbase/src/app.dart';
import 'package:secretbase/src/rust/frb_generated.dart';
import 'package:secretbase/src/state/preferences_controller.dart';
import 'package:secretbase/src/state/vault_controller.dart';
import 'package:shared_preferences/shared_preferences.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await RustLib.init();
  const platformChannel = MethodChannel('secretbase/platform');
  final dataRoot = await platformChannel.invokeMethod<String>(
    'getApplicationDataRoot',
  );
  if (dataRoot == null || dataRoot.isEmpty) {
    throw StateError('无法获取应用数据目录');
  }
  final preferences = await SharedPreferences.getInstance();

  runApp(
    ProviderScope(
      overrides: [
        dataRootProvider.overrideWithValue(dataRoot),
        sharedPreferencesProvider.overrideWithValue(preferences),
      ],
      child: const SecretBaseApp(),
    ),
  );
}
