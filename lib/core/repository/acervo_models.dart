/// Modelo de música do acervo global
class MusicaAcervo {
  final String id;
  final String titulo;
  final String artista;
  final String? tom;
  final String? bpm;
  final String? status;
  final String? cifra;
  final Map<String, String?> urls;
  final DateTime? createdAt;

  const MusicaAcervo({
    required this.id,
    required this.titulo,
    required this.artista,
    this.tom,
    this.bpm,
    this.status,
    this.cifra,
    this.urls = const {},
    this.createdAt,
  });

  factory MusicaAcervo.fromMap(Map<String, dynamic> map) {
    final urls = <String, String?>{};
    const colunasPistas = [
      'url_guitarra',
      'url_baixo',
      'url_piano',
      'url_bateria',
      'url_outros',
      'url_voz',
    ];
    for (final coluna in colunasPistas) {
      urls[coluna] = map[coluna]?.toString();
    }

    return MusicaAcervo(
      id: map['id']?.toString() ?? '',
      titulo: map['nome_musica']?.toString() ?? 'Sem título',
      artista: map['artistas']?['nome_artista']?.toString() ?? '',
      tom: map['tom']?.toString(),
      bpm: map['bpm_original']?.toString(),
      status: map['status']?.toString(),
      cifra: map['letra_cifra']?.toString(),
      urls: urls,
      createdAt: map['created_at'] != null
          ? DateTime.tryParse(map['created_at'].toString())
          : null,
    );
  }

  bool get emProcessamento => status == 'pending' || status == 'processing';
  bool get falhou => status == 'failed';
  
  /// Verifica se TODAS as 6 stems estão disponíveis
  bool get temTodasPistas => urls['url_guitarra'] != null && urls['url_guitarra']!.isNotEmpty
                           && urls['url_baixo'] != null && urls['url_baixo']!.isNotEmpty
                           && urls['url_piano'] != null && urls['url_piano']!.isNotEmpty
                           && urls['url_outros'] != null && urls['url_outros']!.isNotEmpty
                           && urls['url_bateria'] != null && urls['url_bateria']!.isNotEmpty
                           && urls['url_voz'] != null && urls['url_voz']!.isNotEmpty;
  
  /// Mantém compatibilidade - qualquer stem (para UI de progresso)
  bool get temPistas => urls.values.any((v) => v != null && v.isNotEmpty);
  
  /// Música pronta para tocar = status completed + TODAS as 6 stems
  bool get pronta => !emProcessamento && !falhou && temTodasPistas;
}