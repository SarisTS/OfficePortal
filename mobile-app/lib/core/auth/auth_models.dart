/// Mirrors the relevant subset of `backend/app/models/employee.py::UserTypes`.
enum UserType {
  superAdmin('super_admin'),
  officeAdmin('office_admin'),
  staff('staff'),
  employee('employee');

  const UserType(this.wire);
  final String wire;

  static UserType fromWire(String value) {
    return UserType.values.firstWhere(
      (t) => t.wire == value,
      orElse: () => UserType.employee,
    );
  }
}

/// Subset of EmployeeResponse the mobile app needs in auth state.
/// Extend per-feature when a screen needs more fields — keep this
/// payload lean so the auth provider isn't a kitchen sink.
class AuthenticatedUser {
  final int id;
  final String name;
  final String? email;
  final UserType userType;
  final int? companyId;
  final int roleId;

  AuthenticatedUser({
    required this.id,
    required this.name,
    required this.email,
    required this.userType,
    required this.companyId,
    required this.roleId,
  });

  factory AuthenticatedUser.fromJson(Map<String, dynamic> json) {
    return AuthenticatedUser(
      id: json['id'] as int,
      name: json['name'] as String,
      email: json['email'] as String?,
      userType: UserType.fromWire(json['user_type'] as String),
      companyId: json['company_id'] as int?,
      roleId: json['role_id'] as int,
    );
  }
}
