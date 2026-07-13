import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/rust/api/mobile.dart' as rust_api;
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/vault_controller.dart';

class EntryQuery {
  const EntryQuery({
    required this.page,
    required this.pageSize,
    required this.search,
    required this.deleted,
    this.tag,
    this.group,
    this.starred,
  });

  final int page;
  final int pageSize;
  final String search;
  final String? tag;
  final String? group;
  final bool? starred;
  final bool deleted;

  @override
  bool operator ==(Object other) {
    return other is EntryQuery &&
        page == other.page &&
        pageSize == other.pageSize &&
        search == other.search &&
        tag == other.tag &&
        group == other.group &&
        starred == other.starred &&
        deleted == other.deleted;
  }

  @override
  int get hashCode =>
      Object.hash(page, pageSize, search, tag, group, starred, deleted);
}

final entryPageProvider = FutureProvider.autoDispose
    .family<EntryPage, EntryQuery>((ref, query) async {
      ref.watch(vaultRevisionProvider);
      return rust_api.listEntries(
        page: query.page,
        pageSize: query.pageSize,
        search: query.search,
        tag: query.tag,
        group: query.group,
        starred: query.starred,
        deleted: query.deleted,
      );
    });

final taxonomyProvider = FutureProvider.autoDispose
    .family<List<TaxonomyRecord>, String>((ref, kind) async {
      ref.watch(vaultRevisionProvider);
      return rust_api.listTaxonomy(kind: kind);
    });

final recoverySnapshotsProvider =
    FutureProvider.autoDispose<List<RecoverySnapshot>>((ref) async {
      ref.watch(vaultRevisionProvider);
      return rust_api.listRecoverySnapshots();
    });
