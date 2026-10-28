import 'package:supabase_flutter/supabase_flutter.dart'
    hide AuthException;

import '../result/exceptions.dart';
import '../result/helpers.dart';
import '../result/result.dart';
import 'repertorio_models.dart';
import 'repertorio_local_datasource.dart';

/// Repository para operações do repertório do usuário (online + offline fallback)
class RepertorioRepository {
  final SupabaseClient _client;
  final RepertorioLocalDataSource? _local;

  RepertorioRepository(this._client, [this._local]);

  static const _tabela = 'repertorio_global';

  /// Busca repertório do usuário logado
  Future<Result<List<MusicaRepertorio>>> buscarMeuRepertorio() async {
    return runCatchingAsync(() async {
      final userId = _client.auth.currentUser?.id;
      if (userId == null) throw AuthException.unauthorized();

      final response = await _client
          .from(_tabela)
          .select('''
            id, nome_musica, tom, bpm_original, letra_cifra,
            url_guitarra, url_baixo, url_piano, url_bateria, url_outros, url_voz,
            artistas(nome_artista),
            created_at, updated_at
          ''')
          .eq('user_id', userId)
          .order('nome_musica');

      return (response as List)
          .map((e) => MusicaRepertorio.fromMap(e as Map<String, dynamic>))
          .toList();
    });
  }

  /// Adiciona música ao repertório
  Future<Result<MusicaRepertorio>> adicionarMusica({
    required String musicaAcervoId,
    String? tom,
    int? bpm,
    String? cifra,
  }) async {
    return runCatchingAsync(() async {
      final userId = _client.auth.currentUser?.id;
      if (userId == null) throw AuthException.unauthorized();

      // Busca dados da música no acervo
      final acervoResponse = await _client
          .from(_tabela)
          .select('''
            id, nome_musica, artista_id, tom, bpm_original, letra_cifra,
            url_guitarra, url_baixo, url_piano, url_bateria, url_outros, url_voz,
            artistas(nome_artista)
          ''')
          .eq('id', musicaAcervoId)
          .maybeSingle();

      if (acervoResponse == null) {
        throw ValidationException.custom('musica', 'Música não encontrada no acervo');
      }

      final dados = {
        'user_id': userId,
        'nome_musica': acervoResponse['nome_musica'],
        'artista_id': acervoResponse['artista_id'],
        'tom': tom ?? acervoResponse['tom'],
        'bpm_original': bpm?.toString() ?? acervoResponse['bpm_original'],
        'letra_cifra': cifra ?? acervoResponse['letra_cifra'],
        'url_guitarra': acervoResponse['url_guitarra'],
        'url_baixo': acervoResponse['url_baixo'],
        'url_piano': acervoResponse['url_piano'],
        'url_bateria': acervoResponse['url_bateria'],
        'url_outros': acervoResponse['url_outros'],
        'url_voz': acervoResponse['url_voz'],
      };

      final response = await _client.from(_tabela).insert(dados).select().single();
      return MusicaRepertorio.fromMap(response);
    });
  }

  /// Remove música do repertório
  Future<Result<void>> removerMusica(String id) async {
    return runCatchingAsync(() async {
      final userId = _client.auth.currentUser?.id;
      if (userId == null) throw AuthException.unauthorized();

      await _client.from(_tabela).delete().eq('id', id).eq('user_id', userId);
    });
  }

  /// Atualiza música do repertório
  Future<Result<MusicaRepertorio>> atualizarMusica({
    required String id,
    String? tom,
    int? bpm,
    String? cifra,
  }) async {
    return runCatchingAsync(() async {
      final userId = _client.auth.currentUser?.id;
      if (userId == null) throw AuthException.unauthorized();

      final dados = <String, dynamic>{};
      if (tom != null) dados['tom'] = tom;
      if (bpm != null) dados['bpm_original'] = bpm.toString();
      if (cifra != null) dados['letra_cifra'] = cifra;

      final response = await _client
          .from(_tabela)
          .update(dados)
          .eq('id', id)
          .eq('user_id', userId)
          .select()
          .single();

      return MusicaRepertorio.fromMap(response);
    });
  }

  /// Busca músicas por IDs
  Future<Result<List<MusicaRepertorio>>> buscarPorIds(List<String> ids) async {
    return runCatchingAsync(() async {
      final userId = _client.auth.currentUser?.id;
      if (userId == null) throw AuthException.unauthorized();

      if (ids.isEmpty) return [];

      final response = await _client
          .from(_tabela)
          .select('''
            id, nome_musica, tom, bpm_original, letra_cifra,
            url_guitarra, url_baixo, url_piano, url_bateria, url_outros, url_voz,
            artistas(nome_artista),
            created_at, updated_at
          ''')
          .eq('user_id', userId)
          .inFilter('id', ids);

      return (response as List)
          .map((e) => MusicaRepertorio.fromMap(e as Map<String, dynamic>))
          .toList();
    });
  }
}