import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:officeportal_mobile/app.dart';

void main() {
  // ProviderScope makes Riverpod providers (auth state, api client,
  // router) reachable from every widget below it. Single instance per
  // app process.
  runApp(const ProviderScope(child: OfficePortalApp()));
}
