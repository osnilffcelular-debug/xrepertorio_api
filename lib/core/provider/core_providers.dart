import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:projetox/core/cache.dart';
import 'package:projetox/core/repository.dart';
import 'package:projetox/core/service.dart';
import 'package:projetox/core/repository/repertorio_local_datasource.dart';

import 'package:projetox/features/maquina_ritmos/data/datasources/local_preset_datasource.dart';
import 'package:projetox/features/maquina_ritmos/data/datasources/remote_preset_datasource.dart';
import 'package:projetox/features/maquina_ritmos/data/repositories/preset_repository.dart';
import 'package:projetox/features/maquina_ritmos/data/repositories/pedal_repository.dart';
import 'package:projetox/features/maquina_ritmos/data/datasources/pedal_data_source.dart';

/// Provider do SupabaseClient (inicializado no main)
/// SEMPRE retorna um client (dummy em modo offline) para evitar assertion error
final supabaseClientProvider = Provider<SupabaseClient>((ref) {
  return Supabase.instance.client;
});

/// Provider que indica se o Supabase foi inicializado com credenciais REAIS
/// Usado apenas pela UI para decidir se mostra tela de login etc.
final supabaseInitializedProvider = Provider<bool>((ref) {
  throw UnimplementedError('supabaseInitializedProvider deve ser overridden no main');
});

/// Provider do SharedPreferences (inicializado no main, overridden no ProviderScope)
final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError('SharedPreferences deve ser inicializado antes do runApp');
});

/// Provider do RepertorioLocalDataSource (offline cache + fila)
final repertorioLocalDataSourceProvider = Provider<RepertorioLocalDataSource>((ref) {
  return RepertorioLocalDataSource(ref.watch(sharedPreferencesProvider));
});

/// Provider do PistasCache (singleton)
final pistasCacheProvider = Provider<PistasCache>((ref) {
  return PistasCache();
});

/// Provider do AuthRepository - SEMPRE cria o repository real
/// Em modo offline, o client dummy fará operações falharem com erro de rede gracioso
final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(ref.watch(supabaseClientProvider));
});

/// Provider do AuthService
final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService(
    ref.watch(authRepositoryProvider),
    ref.watch(sharedPreferencesProvider),
  );
});

/// Provider do RepertorioRepository
final repertorioRepositoryProvider = Provider<RepertorioRepository>((ref) {
  return RepertorioRepository(
    ref.watch(supabaseClientProvider),
    ref.watch(repertorioLocalDataSourceProvider),
  );
});

/// Provider do RepertorioService
final repertorioServiceProvider = Provider<RepertorioService>((ref) {
  return RepertorioService(
    ref.watch(repertorioRepositoryProvider),
    ref.watch(planosRepositoryProvider),
  );
});

/// Provider do AcervoRepository
final acervoRepositoryProvider = Provider<AcervoRepository>((ref) {
  return AcervoRepository(ref.watch(supabaseClientProvider));
});

/// Provider do AcervoService
final acervoServiceProvider = Provider<AcervoService>((ref) {
  return AcervoService(ref.watch(acervoRepositoryProvider));
});

/// Provider do AcquisitionService (busca + aquisição sob demanda)
final acquisitionServiceProvider = Provider<AcquisitionService>((ref) {
  return AcquisitionService(
    ref.watch(acervoRepositoryProvider),
    ref.watch(supabaseClientProvider),
  );
});

/// Provider do PistasRepository
final pistasRepositoryProvider = Provider<PistasRepository>((ref) {
  return PistasRepository(ref.watch(supabaseClientProvider));
});

/// Provider do PistasService
final pistasServiceProvider = Provider<PistasService>((ref) {
  return PistasService(
    ref.watch(pistasRepositoryProvider),
    ref.watch(pistasCacheProvider),
  );
});

/// Provider do PlanosRepository
final planosRepositoryProvider = Provider<PlanosRepository>((ref) {
  return PlanosRepository(ref.watch(supabaseClientProvider));
});

/// Provider do PlanosService
final planosServiceProvider = Provider<PlanosService>((ref) {
  return PlanosService(ref.watch(planosRepositoryProvider));
});

/// Provider do AudioService
final audioServiceProvider = Provider<AudioService>((ref) {
  return AudioService(ref.watch(pistasCacheProvider));
});

/// Provider do MirrorService
final mirrorServiceProvider = Provider<MirrorService>((ref) {
  return MirrorService();
});

/// Estado de autenticação (Stream)
final authStateProvider = StreamProvider<AuthState>((ref) {
  return ref.watch(authServiceProvider).onAuthStateChange;
});

/// Usuário atual (derivado do authState)
final currentUserProvider = Provider<User?>((ref) {
  final authState = ref.watch(authStateProvider);
  return authState.asData?.value.session?.user ?? 
         ref.watch(authServiceProvider).currentUser;
});

/// Se está autenticado
final isAuthenticatedProvider = Provider<bool>((ref) {
  final user = ref.watch(currentUserProvider);
  return user != null;
});

/// === MAQUINA DE RITMOS PROVIDERS ===

/// Local Preset DataSource
final localPresetDataSourceProvider = Provider<LocalPresetDataSource>((ref) {
  return LocalPresetDataSource(ref.watch(sharedPreferencesProvider));
});

/// Remote Preset DataSource - SEMPRE cria o datasource real
/// Em modo offline, o client dummy fará operações falharem com erro de rede gracioso
final remotePresetDataSourceProvider = Provider<RemotePresetDataSource>((ref) {
  return RemotePresetDataSource(ref.watch(supabaseClientProvider));
});

/// Preset Repository
final presetRepositoryProvider = Provider<PresetRepository>((ref) {
  return PresetRepository(
    ref.watch(localPresetDataSourceProvider),
    ref.watch(remotePresetDataSourceProvider),
  );
});

/// Local Pedal DataSource
final localPedalDataSourceProvider = Provider<LocalPedalDataSource>((ref) {
  return LocalPedalDataSource(ref.watch(sharedPreferencesProvider));
});

/// Pedal Repository
final pedalRepositoryProvider = Provider<PedalRepository>((ref) {
  return PedalRepository(ref.watch(localPedalDataSourceProvider));
});

/// === ALIASES PARA FEATURE PROVIDERS (evita duplicação/shadowing) ===
/// Local Preset DataSource
final coreLocalPresetDataSourceProvider = localPresetDataSourceProvider;

/// Preset Repository
final corePresetRepositoryProvider = presetRepositoryProvider;

/// Pedal Repository
final corePedalRepositoryProvider = pedalRepositoryProvider;

/// Local Pedal DataSource
final coreLocalPedalDataSourceProvider = localPedalDataSourceProvider;