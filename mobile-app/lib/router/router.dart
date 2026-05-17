import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:officeportal_mobile/core/auth/auth_state.dart';
import 'package:officeportal_mobile/features/dashboard/dashboard_screen.dart';
import 'package:officeportal_mobile/features/login/login_screen.dart';

/// Builds the GoRouter and re-evaluates redirects whenever AuthState
/// changes. The redirect rules:
///
///   loading         → stay on /splash
///   unauthenticated → redirect any non-login path to /login
///   authenticated   → redirect /login back to /dashboard
final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/splash',
    redirect: (context, state) {
      final auth = ref.read(authProvider);
      final loc = state.matchedLocation;

      switch (auth.status) {
        case AuthStatus.loading:
          return loc == '/splash' ? null : '/splash';
        case AuthStatus.unauthenticated:
          return loc == '/login' ? null : '/login';
        case AuthStatus.authenticated:
          if (loc == '/login' || loc == '/splash') return '/dashboard';
          return null;
      }
    },
    // Refreshable: when auth state changes, GoRouter re-evaluates
    // the redirect. ChangeNotifier wrapper bridges Riverpod's
    // StateNotifier to GoRouter's listenable.
    refreshListenable: _AuthRefreshNotifier(ref),
    routes: [
      GoRoute(path: '/splash', builder: (_, __) => const _SplashScreen()),
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
      GoRoute(
        path: '/dashboard',
        builder: (_, __) => const DashboardScreen(),
      ),
    ],
  );
});

class _AuthRefreshNotifier extends ChangeNotifier {
  _AuthRefreshNotifier(Ref ref) {
    ref.listen(authProvider, (_, __) => notifyListeners());
  }
}

class _SplashScreen extends StatelessWidget {
  const _SplashScreen();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: CircularProgressIndicator()),
    );
  }
}
