import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:projetox/core/repository/repertorio_local_datasource.dart';
import 'package:projetox/core/repository/repertorio_repository.dart';
import 'package:projetox/core/service/repertorio_service.dart';
import 'package:projetox/core/service/planos_service.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// Serviço que monitora conectividade e sincroniza operações pendentes
class SyncService {
  SyncService._internal();
  static final SyncService _instance = SyncService._internal();
  factory SyncService() => _instance;

  StreamSubscription<List<ConnectivityResult>>? _sub;
  bool _isSyncing = false;

  final RepertorioLocalDataSource _local = RepertorioLocalDataSource(
    // SharedPreferences will be injected via DI later; for now we rely on GetIt
    // In production use di<SharedPreferences>()
    // Placeholder: will be set via init()
    null as dynamic,
  );

  /// Inicializa o serviço (chamar após setupDependencies)
  Future<void> init() async {
    // SharedPreferences will be available via GetIt
    // For simplicity, we assume DI already set up.
    _sub = Connectivity().onConnectivityChanged.listen(_onConnectivityChanged);
    // Also trigger sync if already online
    final result = await Connectivity().checkConnectivity();
    if (!result.contains(ConnectivityResult.none)) {
      _syncPending();
    }
  }

  void _onConnectivityChanged(List<ConnectivityResult> results) {
    if (!_isSyncing && !results.contains(ConnectivityResult.none)) {
      _syncPending();
    }
  }

  Future<void> _syncPending() async {
    if (_isSyncing) return;
    _isSyncing = true;
    try {
      final ops = await _local.carregarPendentes();
      for (final op in ops) {
        await _processOperation(op);
        await _local.removerPendente(op.id);
      }
    } finally {
      _isSyncing = false;
    }
  }

  Future<void> _processOperation(PendingOperation op) async {
    // We need access to services; they are in DI / providers.
    // For simplicity, we use Supabase client directly here.
    final client = Supabase.instance.client;
    switch (op.tipo) {
      case PendingOpType.adicionar:
        final repo = RepertorioRepository(client);
        await repo.adicionarMusica(
          musicaAcervoId: op.dados['musicaAcervoId'] as String,
          tom: op.dados['tom'] as String?,
          bpm: op.dados['bpm'] as int?,
          cifra: op.dados['cifra'] as String?,
        );
        break;
      case PendingOpType.remover:
        final repo = RepertorioRepository(client);
        await repo.removerMusica(op.dados['id'] as String);
        break;
      case PendingOpType.atualizar:
        final repo = RepertorioRepository(client);
        await repo.atualizarMusica(
          id: op.dados['id'] as String,
          tom: op.dados['tom'] as String?,
          bpm: op.dados['bpm'] as int?,
          cifra: op.dados['cifra'] as String?,
        );
        break;
      case PendingOpType.uploadPistas:
        // TODO: implement upload de pistas se necessário
        break;
    }
  }

  void dispose() {
    _sub?.cancel();
  }
}