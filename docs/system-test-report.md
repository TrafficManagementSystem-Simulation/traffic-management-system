# System Test Report

Project: Traffic Management System (Simulation), UE24CS341A, Problem 16  
Run date: 2026-11-19  |  Python 3.13, pytest  |  Command: `pytest tests/integration tests/performance tests/security`

System tests run the whole application through its HTTP API: Sprint 1 end-to-end flows (integration), control-latency and 500-intersection scale tests (performance), and TLS, MFA, evidence encryption, anomaly alert and RBAC privilege-escalation tests (security).

## Summary

| Total | Passed | Failed | Skipped | Time (s) |
|---|---|---|---|---|
| 61 | 61 | 0 | 0 | 30.7 |

## Results by test module

| Module | Tests | Passed | Failed |
|---|---|---|---|
| `integration/test_sprint1_flows.py` | 5 | 5 | 0 |
| `performance/test_control_latency.py` | 2 | 2 | 0 |
| `performance/test_scale_500.py` | 2 | 2 | 0 |
| `security/test_anomaly_alerts.py` | 8 | 8 | 0 |
| `security/test_evidence_encryption.py` | 11 | 11 | 0 |
| `security/test_mfa_login.py` | 13 | 13 | 0 |
| `security/test_rbac_privilege_escalation.py` | 15 | 15 | 0 |
| `security/test_tls_minimum_version.py` | 5 | 5 | 0 |

## Test case list

| Module | Test | Result |
|---|---|---|
| test_sprint1_flows | `test_traffic_flows_from_sensor_to_a_longer_green_and_into_the_audit_log` | PASSED |
| test_sprint1_flows | `test_a_pedestrian_is_served_and_the_request_clears` | PASSED |
| test_sprint1_flows | `test_a_configuration_change_by_the_administrator_reaches_the_controller` | PASSED |
| test_sprint1_flows | `test_each_role_sees_only_its_own_modules` | PASSED |
| test_sprint1_flows | `test_every_page_renders` | PASSED |
| test_control_latency | `test_TC_Perf_01_95th_percentile_of_sensor_to_phase_update_is_within_one_second` | PASSED |
| test_control_latency | `test_the_api_path_is_also_fast` | PASSED |
| test_scale_500 | `test_TC_Scale_01_a_500_intersection_network_validates_and_simulates_in_time` | PASSED |
| test_scale_500 | `test_TC_Scale_01_live_monitoring_of_500_intersections_meets_the_control_loop_threshold` | PASSED |
| test_anomaly_alerts | `test_TC_Sec_06_rapid_repeated_overrides_raise_an_alert_within_60_seconds` | PASSED |
| test_anomaly_alerts | `test_a_few_overrides_are_normal` | PASSED |
| test_anomaly_alerts | `test_the_same_alert_is_not_repeated_every_second` | PASSED |
| test_anomaly_alerts | `test_off_hours_administrator_access_raises_an_alert` | PASSED |
| test_anomaly_alerts | `test_administrator_access_in_working_hours_and_operator_access_at_night_are_normal` | PASSED |
| test_anomaly_alerts | `test_repeated_failed_logins_raise_an_alert` | PASSED |
| test_anomaly_alerts | `test_hours_that_cross_midnight_work` | PASSED |
| test_anomaly_alerts | `test_only_administrators_read_security_alerts` | PASSED |
| test_evidence_encryption | `test_TC_Sec_04_nothing_identifiable_is_stored_in_plain_text` | PASSED |
| test_evidence_encryption | `test_TC_Sec_04_every_retrieval_creates_an_access_log_entry` | PASSED |
| test_evidence_encryption | `test_least_privilege_for_viewing` | PASSED |
| test_evidence_encryption | `test_storing_needs_the_sensor_key_and_a_known_intersection` | PASSED |
| test_evidence_encryption | `test_bad_uploads_are_rejected[change0]` | PASSED |
| test_evidence_encryption | `test_bad_uploads_are_rejected[change1]` | PASSED |
| test_evidence_encryption | `test_bad_uploads_are_rejected[change2]` | PASSED |
| test_evidence_encryption | `test_bad_uploads_are_rejected[change3]` | PASSED |
| test_evidence_encryption | `test_unknown_evidence_is_404_and_the_attempt_is_logged` | PASSED |
| test_evidence_encryption | `test_a_wrong_key_cannot_read_the_data_and_a_bad_key_is_reported` | PASSED |
| test_evidence_encryption | `test_size_and_type_limits` | PASSED |
| test_mfa_login | `test_the_totp_code_matches_the_rfc_6238_test_vectors` | PASSED |
| test_mfa_login | `test_TC_Sec_03_login_without_the_second_factor_is_rejected` | PASSED |
| test_mfa_login | `test_a_wrong_code_is_rejected_and_logged` | PASSED |
| test_mfa_login | `test_the_right_code_signs_in_a_multi_factor_session` | PASSED |
| test_mfa_login | `test_a_code_cannot_be_used_twice` | PASSED |
| test_mfa_login | `test_the_neighbouring_codes_cover_a_small_clock_difference` | PASSED |
| test_mfa_login | `test_a_wrong_password_never_reaches_the_second_factor` | PASSED |
| test_mfa_login | `test_an_operator_session_without_mfa_cannot_change_signal_state` | PASSED |
| test_mfa_login | `test_enrolling_upgrades_the_session_and_later_logins_need_a_code` | PASSED |
| test_mfa_login | `test_confirm_without_enrolling_first_is_refused` | PASSED |
| test_mfa_login | `test_an_administrator_can_reset_a_lost_authenticator` | PASSED |
| test_mfa_login | `test_the_requirement_can_be_switched_off_for_local_development` | PASSED |
| test_mfa_login | `test_the_overrides_made_in_other_tests_use_a_multi_factor_session` | PASSED |
| test_rbac_privilege_escalation | `test_TC_Sec_05_low_privilege_roles_cannot_use_administrator_functions[GET-/api/v1/admin/users-None]` | PASSED |
| test_rbac_privilege_escalation | `test_TC_Sec_05_low_privilege_roles_cannot_use_administrator_functions[POST-/api/v1/admin/users-body1]` | PASSED |
| test_rbac_privilege_escalation | `test_TC_Sec_05_low_privilege_roles_cannot_use_administrator_functions[PUT-/api/v1/admin/users/analyst/role-body2]` | PASSED |
| test_rbac_privilege_escalation | `test_TC_Sec_05_low_privilege_roles_cannot_use_administrator_functions[PUT-/api/v1/admin/intersections/INT-001/config-body3]` | PASSED |
| test_rbac_privilege_escalation | `test_TC_Sec_05_low_privilege_roles_cannot_use_administrator_functions[GET-/api/v1/admin/security-log-None]` | PASSED |
| test_rbac_privilege_escalation | `test_TC_Sec_05_low_privilege_roles_cannot_use_administrator_functions[POST-/api/v1/admin/backups-None]` | PASSED |
| test_rbac_privilege_escalation | `test_TC_Sec_05_low_privilege_roles_cannot_use_administrator_functions[GET-/api/v1/security/alerts-None]` | PASSED |
| test_rbac_privilege_escalation | `test_TC_Sec_05_low_privilege_roles_cannot_use_administrator_functions[POST-/api/v1/admin/users/operator/mfa/reset-None]` | PASSED |
| test_rbac_privilege_escalation | `test_TC_Sec_05_every_denied_attempt_is_logged` | PASSED |
| test_rbac_privilege_escalation | `test_a_user_cannot_promote_themselves` | PASSED |
| test_rbac_privilege_escalation | `test_signal_commands_are_for_operators_only[POST-/api/v1/intersections/INT-001/signal-command-body0]` | PASSED |
| test_rbac_privilege_escalation | `test_analyst_functions_are_closed_to_operators[GET-/api/v1/simulation/samples-None]` | PASSED |
| test_rbac_privilege_escalation | `test_analyst_functions_are_closed_to_operators[GET-/api/v1/reports-None]` | PASSED |
| test_rbac_privilege_escalation | `test_a_token_does_not_carry_over_a_role_change_it_is_checked_each_time` | PASSED |
| test_rbac_privilege_escalation | `test_least_privilege_defaults_for_a_new_user_role_must_be_chosen_explicitly` | PASSED |
| test_tls_minimum_version | `test_server_context_floor_is_tls_1_2` | PASSED |
| test_tls_minimum_version | `test_TC_Sec_02_tls_1_2_is_accepted` | PASSED |
| test_tls_minimum_version | `test_TC_Sec_02_default_client_negotiates_tls_1_2_or_newer` | PASSED |
| test_tls_minimum_version | `test_TC_Sec_02_connection_below_tls_1_2_is_refused` | PASSED |
| test_tls_minimum_version | `test_enforce_minimum_version_raises_the_floor` | PASSED |
