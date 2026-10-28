import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'auth_preferences.dart';
import 'home_screen.dart';
import 'login_widget.dart';
import 'tema_xr.dart';
import 'core/cache/pistas_cache.dart';
import 'core/provider.dart';
import 'core/sync/sync_service.dart';

/// Configurações carregadas via --dart-define (compile-time) ou variáveis de ambiente.
/// Exemplo de build: flutter run --dart-define=SUPABASE_URL=https://... --dart-define=SUPABASE_ANON_KEY=...
const String _supabaseUrl = String.fromEnvironment('SUPABASE_URL');
const String _supabaseAnonKey = String.fromEnvironment('SUPABASE_ANON_KEY');

/// Se true, permite rodar o app sem credenciais do Supabase (para testes locais)
const bool _allowOfflineMode = bool.fromEnvironment('ALLOW_OFFLINE_MODE', defaultValue: true);

Future<void> main() async {
  runZonedGuarded(() async {
    WidgetsFlutterBinding.ensureInitialized();

    // Inicializa SharedPreferences ANTES do runApp
    final prefs = await SharedPreferences.getInstance();

    // Inicializa cache de pistas
    final pistasCache = PistasCache();
    await pistasCache.init();

    // SEMPRE inicializa Supabase (mesmo em modo offline com credenciais dummy)
    // para evitar assertion error: _instance, _isInitialized
    bool supabaseInitialized = false;
    if (_supabaseUrl.isNotEmpty && _supabaseAnonKey.isNotEmpty) {
      try {
        await Supabase.initialize(
          url: _supabaseUrl,
          publishableKey: _supabaseAnonKey,
        );
        supabaseInitialized = true;
      } catch (e) {
        if (!_allowOfflineMode) rethrow;
        debugPrint('⚠️ Falha ao inicializar Supabase: $e');
      }
    } else {
      // Modo offline ou sem credenciais: inicializa com dummy para evitar crash
      // Operações falharão graciosamente quando tentadas
      final dummyUrl = 'https://dummy.supabase.co';
      final dummyKey = 'dummy-key';
      try {
        await Supabase.initialize(
          url: dummyUrl,
          publishableKey: dummyKey,
        );
        debugPrint('⚠️ Modo offline: Supabase inicializado com credenciais dummy. Funcionalidades de nuvem desabilitadas.');
      } catch (e) {
        if (!_allowOfflineMode) rethrow;
        debugPrint('⚠️ Falha ao inicializar Supabase (dummy): $e');
      }
      supabaseInitialized = false; // Marca como não inicializado "de verdade"
    }

    // Inicializa sincronização offline/online
    await SyncService().init();

    runApp(
      ProviderScope(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(prefs),
          supabaseInitializedProvider.overrideWithValue(supabaseInitialized),
        ],
        child: const MeuApp(),
      ),
    );
  }, (error, stack) {
    // Log errors to console (visible in logcat)
    debugPrint('💥 Uncaught error: $error\n$stack');
  });
}

class MeuApp extends ConsumerWidget {
  const MeuApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Se Supabase não inicializado, pula autenticação e vai direto para Home
    final supabaseReady = ref.watch(supabaseInitializedProvider);
    
    if (!supabaseReady) {
      return MaterialApp(
        title: 'XRepertório',
        debugShowCheckedModeBanner: false,
        theme: temaXRepertorio(),
        home: const HomeScreen(loginScreenBuilder: null),
      );
    }

    // Observa estado de autenticação para decidir tela inicial
    final authState = ref.watch(authStateProvider);

    return MaterialApp(
      title: 'XRepertório',
      debugShowCheckedModeBanner: false,
      theme: temaXRepertorio(),
      home: authState.when(
        data: (state) => state.session != null
            ? HomeScreen(loginScreenBuilder: (_) => const LoginWidget())
            : const LoginWidget(),
        loading: () => const Scaffold(
          body: Center(child: CircularProgressIndicator()),
        ),
        error: (error, _) => Scaffold(
          body: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, size: 64, color: Colors.red),
                const SizedBox(height: 16),
                Text('Erro de autenticação: $error'),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: () => ref.invalidate(authStateProvider),
                  child: const Text('Tentar novamente'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
