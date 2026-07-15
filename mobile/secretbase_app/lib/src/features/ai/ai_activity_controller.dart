import 'package:flutter_riverpod/flutter_riverpod.dart';

final aiActivityControllerProvider =
    NotifierProvider<AiActivityController, bool>(AiActivityController.new);

class AiActivityController extends Notifier<bool> {
  @override
  bool build() => false;

  bool start() {
    if (state) return false;
    state = true;
    return true;
  }

  void finish() {
    state = false;
  }
}
