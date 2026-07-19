import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/rust/api/mobile.dart' as rust_api;
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/vault_controller.dart';

class AiUndoUiState {
  const AiUndoUiState({this.pending, this.working = false});

  final AiUndoState? pending;
  final bool working;

  AiUndoUiState copyWith({
    AiUndoState? pending,
    bool? working,
    bool clear = false,
  }) {
    return AiUndoUiState(
      pending: clear ? null : pending ?? this.pending,
      working: working ?? this.working,
    );
  }
}

final aiUndoControllerProvider =
    NotifierProvider<AiUndoController, AiUndoUiState>(AiUndoController.new);

class AiUndoController extends Notifier<AiUndoUiState> {
  @override
  AiUndoUiState build() {
    ref.listen(vaultRevisionProvider, (previous, next) {
      final pending = state.pending;
      if (pending != null && pending.revision != next) {
        state = state.copyWith(clear: true, working: false);
      }
    });
    Future.microtask(refresh);
    return const AiUndoUiState();
  }

  Future<void> refresh() async {
    try {
      final pending = await rust_api.pendingAiUndo();
      state = AiUndoUiState(pending: pending);
    } catch (_) {
      state = const AiUndoUiState();
    }
  }

  void record(AiApplyResult result) {
    state = AiUndoUiState(
      pending: AiUndoState(
        revision: result.revision,
        message: result.message,
        undoToken: result.undoToken,
        appliedCount: result.appliedCount,
      ),
    );
  }

  Future<String> undo() async {
    final pending = state.pending;
    if (pending == null || state.working) return '没有可撤回的 AI 操作';
    state = state.copyWith(working: true);
    try {
      final result = await rust_api.undoAiPreview(
        undoToken: pending.undoToken,
        expectedRevision: pending.revision,
      );
      state = state.copyWith(clear: true, working: false);
      var refreshed = true;
      try {
        await ref.read(vaultControllerProvider.notifier).refreshStatus();
      } catch (_) {
        refreshed = false;
      }
      ref.invalidate(entryPageProvider);
      ref.invalidate(taxonomyProvider);
      ref.invalidate(recoverySnapshotsProvider);
      return refreshed ? result.message : '${result.message}，但界面刷新不完整，请稍后重试。';
    } catch (_) {
      state = state.copyWith(clear: true, working: false);
      rethrow;
    }
  }
}
