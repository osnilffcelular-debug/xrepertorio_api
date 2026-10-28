import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'repertorio_models.dart';

/// Armazenamento local simples do repertório (offline-first)
class RepertorioLocalDataSource {
  static const _keyRepertorio = 'repertorio_local';
  static const _keyPendingOps = 'repertorio_pending_ops';

  final SharedPreferences _prefs;

  RepertorioLocalDataSource(this._prefs);

  /// Carrega repertório salvo localmente
  Future<List<MusicaRepertorio>> carregarRepertorio() async {
    final jsonStr = _prefs.getString(_keyRepertorio);
    if (jsonStr == null) return [];
    final List<dynamic> list = json.decode(jsonStr);
    return list.map((e) => MusicaRepertorio.fromMap(e as Map<String, dynamic>)).toList();
  }

  /// Salva repertório completo localmente
  Future<void> salvarRepertorio(List<MusicaRepertorio> musicas) async {
    final jsonStr = json.encode(musicas.map((m) => m.toMap()).toList());
    await _prefs.setString(_keyRepertorio, jsonStr);
  }

  /// Adiciona uma música ao cache local
  Future<void> adicionarLocal(MusicaRepertorio musica) async {
    final lista = await carregarRepertorio();
    lista.add(musica);
    await salvarRepertorio(lista);
  }

  /// Atualiza música no cache local
  Future<void> atualizarLocal(MusicaRepertorio musica) async {
    final lista = await carregarRepertorio();
    final idx = lista.indexWhere((m) => m.id == musica.id);
    if (idx != -1) {
      lista[idx] = musica;
      await salvarRepertorio(lista);
    }
  }

  /// Remove música do cache local
  Future<void> removerLocal(String id) async {
    final lista = await carregarRepertorio();
    lista.removeWhere((m) => m.id == id);
    await salvarRepertorio(lista);
  }

  /// Operações pendentes para sincronização
  Future<List<PendingOperation>> carregarPendentes() async {
    final jsonStr = _prefs.getString(_keyPendingOps);
    if (jsonStr == null) return [];
    final List<dynamic> list = json.decode(jsonStr);
    return list.map((e) => PendingOperation.fromMap(e as Map<String, dynamic>)).toList();
  }

  Future<void> salvarPendentes(List<PendingOperation> ops) async {
    final jsonStr = json.encode(ops.map((e) => e.toMap()).toList());
    await _prefs.setString(_keyPendingOps, jsonStr);
  }

  Future<void> adicionarPendente(PendingOperation op) async {
    final ops = await carregarPendentes();
    ops.add(op);
    await salvarPendentes(ops);
  }

  Future<void> removerPendente(String idOperacao) async {
    final ops = await carregarPendentes();
    ops.removeWhere((o) => o.id == idOperacao);
    await salvarPendentes(ops);
  }
}

/// Tipos de operação pendente
enum PendingOpType { adicionar, atualizar, remover, uploadPistas }

/// Modelo de operação pendente para sincronização
class PendingOperation {
  final String id;
  final PendingOpType tipo;
  final Map<String, dynamic> dados;
  final DateTime timestamp;

  const PendingOperation({
    required this.id,
    required this.tipo,
    required this.dados,
    required this.timestamp,
  });

  factory PendingOperation.fromMap(Map<String, dynamic> map) {
    return PendingOperation(
      id: map['id'] as String,
      tipo: PendingOpType.values.byName(map['tipo'] as String),
      dados: Map<String, dynamic>.from(map['dados'] as Map),
      timestamp: DateTime.parse(map['timestamp'] as String),
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'tipo': tipo.name,
      'dados': dados,
      'timestamp': timestamp.toIso8601String(),
    };
  }
}