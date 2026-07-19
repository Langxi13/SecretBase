import 'package:flutter_riverpod/flutter_riverpod.dart';

final aiActivityControllerProvider =
    NotifierProvider<AiActivityController, bool>(AiActivityController.new);

class AiActivityController extends Notifier<bool> {
  int _nextToken = 0;
  int? _activeToken;

  @override
  bool build() => false;

  int? acquire() {
    if (state) return null;
    final token = ++_nextToken;
    _activeToken = token;
    state = true;
    return token;
  }

  bool start() {
    return acquire() != null;
  }

  void finish([int? token]) {
    if (token != null && token != _activeToken) return;
    _activeToken = null;
    state = false;
  }
}
