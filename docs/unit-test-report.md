# Unit Test Report

Project: Traffic Management System (Simulation), UE24CS341A, Problem 16  
Run date: 2026-11-19  |  Python 3.13, pytest  |  Command: `pytest tests/unit`

Unit tests exercise each module in isolation (admin, common, detection, incident, infra, reporting, signal_control, simulation, ui) with an in-memory database and a frozen clock. Test names carry the SRS/STP test-case ID where one applies (for example `TC_Sig_01`).

## Summary

| Total | Passed | Failed | Skipped | Time (s) |
|---|---|---|---|---|
| 295 | 295 | 0 | 0 | 68.0 |

## Results by test module

| Module | Tests | Passed | Failed |
|---|---|---|---|
| `unit/admin/test_intersection_config.py` | 10 | 10 | 0 |
| `unit/admin/test_rbac_login.py` | 12 | 12 | 0 |
| `unit/common/test_app_shell.py` | 11 | 11 | 0 |
| `unit/common/test_repository_layout.py` | 6 | 6 | 0 |
| `unit/detection/test_classifier_and_synthetic.py` | 8 | 8 | 0 |
| `unit/detection/test_counting_and_pedestrians.py` | 9 | 9 | 0 |
| `unit/detection/test_detection_api.py` | 10 | 10 | 0 |
| `unit/incident/test_incident_detection.py` | 14 | 14 | 0 |
| `unit/infra/test_availability.py` | 12 | 12 | 0 |
| `unit/infra/test_backup_restore.py` | 8 | 8 | 0 |
| `unit/infra/test_interop_api.py` | 5 | 5 | 0 |
| `unit/infra/test_portability.py` | 24 | 24 | 0 |
| `unit/reporting/test_traffic_reports.py` | 9 | 9 | 0 |
| `unit/signal_control/test_adaptive_controller.py` | 11 | 11 | 0 |
| `unit/signal_control/test_field_failsafe.py` | 7 | 7 | 0 |
| `unit/signal_control/test_green_wave.py` | 11 | 11 | 0 |
| `unit/signal_control/test_override_and_audit.py` | 14 | 14 | 0 |
| `unit/signal_control/test_preemption.py` | 11 | 11 | 0 |
| `unit/signal_control/test_signal_api.py` | 8 | 8 | 0 |
| `unit/signal_control/test_timing_plugins.py` | 5 | 5 | 0 |
| `unit/simulation/test_compare_and_replay.py` | 12 | 12 | 0 |
| `unit/simulation/test_engine_and_networks.py` | 24 | 24 | 0 |
| `unit/simulation/test_simulation_api.py` | 8 | 8 | 0 |
| `unit/ui/test_accessibility_wcag.py` | 46 | 46 | 0 |

## Test case list

| Module | Test | Result |
|---|---|---|
| test_intersection_config | `test_TC_Adm_02_change_is_validated_versioned_and_applied_without_restart` | PASSED |
| test_intersection_config | `test_invalid_change_is_rejected_and_nothing_changes` | PASSED |
| test_intersection_config | `test_cycle_that_cannot_hold_the_minimum_greens_is_rejected` | PASSED |
| test_intersection_config | `test_unknown_setting_is_rejected` | PASSED |
| test_intersection_config | `test_history_keeps_every_version_newest_first` | PASSED |
| test_intersection_config | `test_unknown_intersection_is_404` | PASSED |
| test_intersection_config | `test_new_intersection_can_be_added` | PASSED |
| test_intersection_config | `test_duplicate_or_badly_named_intersection_is_rejected` | PASSED |
| test_intersection_config | `test_default_configuration_is_valid` | PASSED |
| test_intersection_config | `test_booleans_are_not_accepted_as_numbers` | PASSED |
| test_rbac_login | `test_login_returns_token_and_role` | PASSED |
| test_rbac_login | `test_wrong_password_is_rejected_and_logged` | PASSED |
| test_rbac_login | `test_unknown_user_gets_the_same_answer_as_a_wrong_password` | PASSED |
| test_rbac_login | `test_passwords_are_stored_hashed` | PASSED |
| test_rbac_login | `test_missing_or_bad_token_is_401_and_logged` | PASSED |
| test_rbac_login | `test_me_lists_the_permissions_of_the_role` | PASSED |
| test_rbac_login | `test_TC_Adm_01_analyst_is_denied_an_admin_function_and_it_is_logged` | PASSED |
| test_rbac_login | `test_least_privilege_defaults_for_admin_endpoints` | PASSED |
| test_rbac_login | `test_administrator_creates_a_user_who_can_sign_in` | PASSED |
| test_rbac_login | `test_user_creation_rejects_bad_input` | PASSED |
| test_rbac_login | `test_administrator_can_change_a_role` | PASSED |
| test_rbac_login | `test_roles_endpoint_lists_every_role` | PASSED |
| test_app_shell | `test_every_page_renders[/]` | PASSED |
| test_app_shell | `test_every_page_renders[/operator]` | PASSED |
| test_app_shell | `test_every_page_renders[/detection]` | PASSED |
| test_app_shell | `test_every_page_renders[/simulation]` | PASSED |
| test_app_shell | `test_every_page_renders[/incidents]` | PASSED |
| test_app_shell | `test_every_page_renders[/reports]` | PASSED |
| test_app_shell | `test_every_page_renders[/admin]` | PASSED |
| test_app_shell | `test_static_files_are_served` | PASSED |
| test_app_shell | `test_openapi_page_is_available` | PASSED |
| test_app_shell | `test_clock_can_be_frozen_and_advanced` | PASSED |
| test_app_shell | `test_errors_use_one_shape` | PASSED |
| test_repository_layout | `test_every_agreed_file_and_folder_exists` | PASSED |
| test_repository_layout | `test_each_module_has_its_unit_test_folder_with_tests` | PASSED |
| test_repository_layout | `test_each_module_has_code_and_the_ui_has_a_page_per_module` | PASSED |
| test_repository_layout | `test_no_extra_top_level_packages_under_src_tms` | PASSED |
| test_repository_layout | `test_the_security_folder_covers_tls_mfa_rbac_and_privacy` | PASSED |
| test_repository_layout | `test_only_the_agreed_script_files_exist` | PASSED |
| test_classifier_and_synthetic | `test_TC_VDC_01_classification_accuracy_is_at_least_90_percent` | PASSED |
| test_classifier_and_synthetic | `test_every_class_is_recognised_most_of_the_time` | PASSED |
| test_classifier_and_synthetic | `test_typical_vehicles` | PASSED |
| test_classifier_and_synthetic | `test_boundary_values_do_not_crash_and_stay_in_the_class_list` | PASSED |
| test_classifier_and_synthetic | `test_accuracy_of_nothing_is_zero` | PASSED |
| test_classifier_and_synthetic | `test_validation_csv_file_reaches_the_same_accuracy` | PASSED |
| test_classifier_and_synthetic | `test_same_seed_gives_the_same_feed_and_a_new_seed_changes_it` | PASSED |
| test_classifier_and_synthetic | `test_feed_has_the_requested_volume_and_pedestrians` | PASSED |
| test_counting_and_pedestrians | `test_TC_VDC_02_counts_match_the_ground_truth_over_15_minutes` | PASSED |
| test_counting_and_pedestrians | `test_counts_are_kept_per_approach_lane_and_class` | PASSED |
| test_counting_and_pedestrians | `test_count_field_adds_several_vehicles_at_once` | PASSED |
| test_counting_and_pedestrians | `test_bucket_start_rounds_down_to_the_interval` | PASSED |
| test_counting_and_pedestrians | `test_the_interval_is_configurable_per_intersection` | PASSED |
| test_counting_and_pedestrians | `test_density_is_vehicles_per_minute_over_the_window` | PASSED |
| test_counting_and_pedestrians | `test_density_is_zero_without_data` | PASSED |
| test_counting_and_pedestrians | `test_pedestrian_request_is_pending_until_served` | PASSED |
| test_counting_and_pedestrians | `test_pedestrian_detection_creates_a_request` | PASSED |
| test_detection_api | `test_valid_detection_is_accepted` | PASSED |
| test_detection_api | `test_sensor_key_is_required` | PASSED |
| test_detection_api | `test_a_signed_in_user_without_the_sensor_key_cannot_post` | PASSED |
| test_detection_api | `test_malformed_json_is_400` | PASSED |
| test_detection_api | `test_validation_failures_are_422` | PASSED |
| test_detection_api | `test_approach_must_exist_at_the_intersection` | PASSED |
| test_detection_api | `test_unknown_intersection_is_404` | PASSED |
| test_detection_api | `test_features_are_classified_when_no_class_is_given` | PASSED |
| test_detection_api | `test_counts_and_density_endpoints_need_sign_in` | PASSED |
| test_detection_api | `test_pedestrian_requests_endpoint` | PASSED |
| test_incident_detection | `test_TC_Inc_01_an_injected_congestion_is_detected_within_60_seconds` | PASSED |
| test_incident_detection | `test_normal_busy_traffic_is_not_an_incident` | PASSED |
| test_incident_detection | `test_a_steady_heavy_flow_is_normal_but_a_sudden_jump_is_not` | PASSED |
| test_incident_detection | `test_a_stalled_vehicle_is_found_once_it_has_been_stopped_for_30_seconds` | PASSED |
| test_incident_detection | `test_a_vehicle_that_moves_again_is_not_stalled` | PASSED |
| test_incident_detection | `test_a_collision_report_becomes_a_high_severity_incident` | PASSED |
| test_incident_detection | `test_TC_Inc_02_the_alert_has_location_type_and_severity_and_is_ready_within_5_seconds` | PASSED |
| test_incident_detection | `test_the_same_incident_is_not_alerted_twice_until_it_is_resolved` | PASSED |
| test_incident_detection | `test_acknowledge_and_resolve_flow` | PASSED |
| test_incident_detection | `test_TC_Inc_03_dispatch_is_transmitted_acknowledged_and_logged` | PASSED |
| test_incident_detection | `test_a_service_that_does_not_answer_is_reported_and_logged` | PASSED |
| test_incident_detection | `test_bad_dispatch_requests` | PASSED |
| test_incident_detection | `test_api_end_to_end` | PASSED |
| test_incident_detection | `test_the_api_reports_a_failing_service_as_502` | PASSED |
| test_availability | `test_a_period_without_problems_is_100_percent` | PASSED |
| test_availability | `test_three_hours_down_in_a_30_day_month_meets_the_target` | PASSED |
| test_availability | `test_four_hours_down_misses_the_target` | PASSED |
| test_availability | `test_planned_maintenance_is_not_counted_against_the_service` | PASSED |
| test_availability | `test_only_the_part_of_an_outage_outside_maintenance_counts` | PASSED |
| test_availability | `test_unhealthy_heartbeats_count_as_downtime` | PASSED |
| test_availability | `test_a_service_that_started_mid_month_is_judged_from_its_first_heartbeat` | PASSED |
| test_availability | `test_no_heartbeats_means_unknown_not_100` | PASSED |
| test_availability | `test_the_current_month_is_measured_up_to_now` | PASSED |
| test_availability | `test_heartbeats_are_written_about_every_30_seconds` | PASSED |
| test_availability | `test_maintenance_window_validation` | PASSED |
| test_availability | `test_api` | PASSED |
| test_backup_restore | `test_TC_BCP_01_restore_returns_configuration_and_traffic_history_within_the_rto` | PASSED |
| test_backup_restore | `test_the_backup_is_a_consistent_copy_with_a_manifest` | PASSED |
| test_backup_restore | `test_TC_BCP_01_the_daily_run_keeps_the_backup_no_older_than_the_rpo` | PASSED |
| test_backup_restore | `test_old_backups_are_pruned` | PASSED |
| test_backup_restore | `test_a_damaged_backup_is_refused_and_the_live_data_is_left_alone` | PASSED |
| test_backup_restore | `test_restore_errors` | PASSED |
| test_backup_restore | `test_a_named_older_backup_can_be_restored` | PASSED |
| test_backup_restore | `test_admin_api` | PASSED |
| test_interop_api | `test_TC_Interop_01_a_sample_third_party_client_reads_the_published_contract` | PASSED |
| test_interop_api | `test_the_contract_checker_catches_a_changed_response` | PASSED |
| test_interop_api | `test_every_published_path_is_versioned` | PASSED |
| test_interop_api | `test_meta_is_public_and_data_needs_sign_in` | PASSED |
| test_interop_api | `test_location_is_part_of_the_configuration` | PASSED |
| test_portability | `test_TC_Port_01_the_same_code_runs_in_two_environments_chosen_only_by_settings` | PASSED |
| test_portability | `test_environment_variables_win_over_the_settings_file` | PASSED |
| test_portability | `test_the_settings_file_may_name_it_through_tms_env_file` | PASSED |
| test_portability | `test_file_format_comments_quotes_and_blank_lines` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[database_url]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[sensor_api_key]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[autotick]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[seed_demo]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[token_hours]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[tls_cert]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[tls_key]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[timing_algorithm]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[plugins]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[require_mfa]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[evidence_key]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[admin_hours]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[preemption_key]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[host]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[port]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[backup_dir]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[backup_keep]` | PASSED |
| test_portability | `test_every_setting_can_be_changed_from_outside_the_code[backups_enabled]` | PASSED |
| test_portability | `test_the_shipped_environment_files_load_and_differ` | PASSED |
| test_portability | `test_no_environment_specific_paths_are_written_in_the_modules` | PASSED |
| test_traffic_reports | `test_period_boundaries` | PASSED |
| test_traffic_reports | `test_TC_Rpt_01_a_daily_report_covers_volume_incidents_and_signal_performance` | PASSED |
| test_traffic_reports | `test_another_day_has_no_data_but_still_reports` | PASSED |
| test_traffic_reports | `test_weekly_and_monthly_reports_include_the_same_data` | PASSED |
| test_traffic_reports | `test_TC_Rpt_01_scheduled_reports_are_generated_automatically_when_a_period_ends` | PASSED |
| test_traffic_reports | `test_regenerating_refreshes_the_report_instead_of_duplicating_it` | PASSED |
| test_traffic_reports | `test_the_background_check_runs_at_most_once_a_minute` | PASSED |
| test_traffic_reports | `test_csv_export_has_one_row_per_metric` | PASSED |
| test_traffic_reports | `test_api_generate_list_and_download` | PASSED |
| test_adaptive_controller | `test_green_times_follow_the_traffic_but_stay_inside_the_limits` | PASSED |
| test_adaptive_controller | `test_TC_Sig_01_green_time_changes_within_one_control_cycle` | PASSED |
| test_adaptive_controller | `test_a_full_cycle_runs_green_yellow_all_red_then_the_next_phase` | PASSED |
| test_adaptive_controller | `test_invalid_plan_is_rejected_and_the_old_plan_is_kept` | PASSED |
| test_adaptive_controller | `test_validate_plan_rejects_unsafe_plans` | PASSED |
| test_adaptive_controller | `test_apply_plan_records_the_plan_and_the_source` | PASSED |
| test_adaptive_controller | `test_while_an_override_is_active_the_computed_plan_is_stored_not_applied` | PASSED |
| test_adaptive_controller | `test_TC_VDC_03_pedestrian_phase_runs_within_one_cycle_of_the_request` | PASSED |
| test_adaptive_controller | `test_a_request_just_after_the_all_red_waits_for_the_next_one_but_still_inside_a_cycle` | PASSED |
| test_adaptive_controller | `test_after_the_pedestrian_stage_the_next_vehicle_phase_gets_its_green` | PASSED |
| test_adaptive_controller | `test_view_state_describes_the_signal` | PASSED |
| test_field_failsafe | `test_TC_Rel_01_signals_stay_safe_for_four_hours_without_the_central_platform` | PASSED |
| test_field_failsafe | `test_a_green_is_always_followed_by_yellow_then_all_red_never_straight_to_the_other_green` | PASSED |
| test_field_failsafe | `test_with_no_plan_ever_received_the_safe_default_is_used` | PASSED |
| test_field_failsafe | `test_after_a_restart_the_plan_comes_back_from_local_storage` | PASSED |
| test_field_failsafe | `test_a_damaged_store_falls_back_to_the_safe_default` | PASSED |
| test_field_failsafe | `test_when_the_link_returns_the_new_plan_starts_at_the_next_cycle` | PASSED |
| test_field_failsafe | `test_unsafe_plans_from_the_centre_are_refused` | PASSED |
| test_green_wave | `test_offsets_follow_the_travel_time_between_intersections` | PASSED |
| test_green_wave | `test_offsets_wrap_around_the_cycle` | PASSED |
| test_green_wave | `test_TC_Sig_05_a_platoon_crosses_three_coordinated_intersections_without_stopping` | PASSED |
| test_green_wave | `test_bad_corridors_are_rejected[change0]` | PASSED |
| test_green_wave | `test_bad_corridors_are_rejected[change1]` | PASSED |
| test_green_wave | `test_bad_corridors_are_rejected[change2]` | PASSED |
| test_green_wave | `test_bad_corridors_are_rejected[change3]` | PASSED |
| test_green_wave | `test_bad_corridors_are_rejected[change4]` | PASSED |
| test_green_wave | `test_bad_corridors_are_rejected[change5]` | PASSED |
| test_green_wave | `test_offsets_can_be_applied_to_a_simulation_network_and_it_still_runs` | PASSED |
| test_green_wave | `test_api` | PASSED |
| test_override_and_audit | `test_TC_Sig_02_override_is_applied_within_2_seconds_and_reverts_on_command` | PASSED |
| test_override_and_audit | `test_the_override_ends_by_itself_when_the_time_is_up` | PASSED |
| test_override_and_audit | `test_holding_the_current_phase_extends_its_green` | PASSED |
| test_override_and_audit | `test_all_red_hold` | PASSED |
| test_override_and_audit | `test_interlock_blocks_an_override_during_the_pedestrian_stage` | PASSED |
| test_override_and_audit | `test_bad_commands_are_rejected_with_a_reason[XX-30-invalid_phase]` | PASSED |
| test_override_and_audit | `test_bad_commands_are_rejected_with_a_reason[EW-5-invalid_duration]` | PASSED |
| test_override_and_audit | `test_bad_commands_are_rejected_with_a_reason[EW-999-invalid_duration]` | PASSED |
| test_override_and_audit | `test_bad_commands_are_rejected_with_a_reason[EW-30-invalid_duration]` | PASSED |
| test_override_and_audit | `test_bad_commands_are_rejected_with_a_reason[ALL_RED-2-invalid_duration]` | PASSED |
| test_override_and_audit | `test_clearing_when_nothing_is_overridden_is_harmless` | PASSED |
| test_override_and_audit | `test_TC_Sig_03_every_state_change_is_in_the_audit_log` | PASSED |
| test_override_and_audit | `test_audit_entries_name_the_actor_and_the_command` | PASSED |
| test_override_and_audit | `test_audit_can_be_filtered_and_limited` | PASSED |
| test_preemption | `test_TC_Sig_04_preemption_is_applied_within_3_seconds_and_the_corridor_turns_green` | PASSED |
| test_preemption | `test_a_corridor_that_is_already_green_stays_green_with_no_clearance` | PASSED |
| test_preemption | `test_normal_operation_resumes_after_the_hold_or_when_cleared` | PASSED |
| test_preemption | `test_every_preemption_state_change_is_audited_as_preemption` | PASSED |
| test_preemption | `test_an_emergency_vehicle_may_cut_a_pedestrian_stage_short_but_an_operator_may_not` | PASSED |
| test_preemption | `test_bad_requests_are_rejected[Q-A1-30-invalid_approach]` | PASSED |
| test_preemption | `test_bad_requests_are_rejected[N--30-invalid_vehicle]` | PASSED |
| test_preemption | `test_bad_requests_are_rejected[N-A1-5-invalid_duration]` | PASSED |
| test_preemption | `test_bad_requests_are_rejected[N-A1-999-invalid_duration]` | PASSED |
| test_preemption | `test_api_needs_the_secure_channel_key` | PASSED |
| test_preemption | `test_operators_still_see_the_preemption_in_the_state_and_audit_log` | PASSED |
| test_signal_api | `test_signal_state_needs_a_signed_in_user` | PASSED |
| test_signal_api | `test_operator_overrides_and_returns_to_auto` | PASSED |
| test_signal_api | `test_TC_Adm_01_analyst_is_denied_the_override` | PASSED |
| test_signal_api | `test_bad_commands_are_400` | PASSED |
| test_signal_api | `test_unknown_intersection_is_404` | PASSED |
| test_signal_api | `test_interlock_conflict_is_409` | PASSED |
| test_signal_api | `test_audit_log_endpoint_is_for_operators_and_administrators` | PASSED |
| test_signal_api | `test_tick_and_recompute_endpoints` | PASSED |
| test_timing_plugins | `test_TC_Maint_01_a_new_algorithm_is_used_by_the_controller` | PASSED |
| test_timing_plugins | `test_an_unsafe_plugin_still_cannot_apply_an_unsafe_plan` | PASSED |
| test_timing_plugins | `test_unknown_or_invalid_plugins_are_rejected` | PASSED |
| test_timing_plugins | `test_the_setting_chooses_the_algorithm_when_the_app_starts` | PASSED |
| test_timing_plugins | `test_detection_and_reporting_modules_do_not_know_about_the_plugins` | PASSED |
| test_compare_and_replay | `test_TC_Sim_04_comparison_lines_up_the_metrics_of_each_scenario` | PASSED |
| test_compare_and_replay | `test_compare_needs_two_different_existing_runs` | PASSED |
| test_compare_and_replay | `test_compare_runs_handles_three_scenarios_and_missing_values` | PASSED |
| test_compare_and_replay | `test_positions_are_interpolated_between_samples` | PASSED |
| test_compare_and_replay | `test_TC_Sim_05_playback_at_any_speed_ends_on_the_same_positions[0.5]` | PASSED |
| test_compare_and_replay | `test_TC_Sim_05_playback_at_any_speed_ends_on_the_same_positions[1]` | PASSED |
| test_compare_and_replay | `test_TC_Sim_05_playback_at_any_speed_ends_on_the_same_positions[2]` | PASSED |
| test_compare_and_replay | `test_TC_Sim_05_playback_at_any_speed_ends_on_the_same_positions[4]` | PASSED |
| test_compare_and_replay | `test_TC_Sim_05_playback_at_any_speed_ends_on_the_same_positions[8]` | PASSED |
| test_compare_and_replay | `test_changing_speed_during_playback_does_not_desync` | PASSED |
| test_compare_and_replay | `test_playback_stops_at_the_end_and_rejects_bad_speeds` | PASSED |
| test_compare_and_replay | `test_replay_endpoint` | PASSED |
| test_engine_and_networks | `test_both_sample_networks_are_valid` | PASSED |
| test_engine_and_networks | `test_TC_Sim_01_orphan_nodes_and_links_are_reported` | PASSED |
| test_engine_and_networks | `test_unreachable_exit_is_reported` | PASSED |
| test_engine_and_networks | `test_garbage_is_rejected_not_crashed[None]` | PASSED |
| test_engine_and_networks | `test_garbage_is_rejected_not_crashed[broken1]` | PASSED |
| test_engine_and_networks | `test_garbage_is_rejected_not_crashed[broken2]` | PASSED |
| test_engine_and_networks | `test_garbage_is_rejected_not_crashed[broken3]` | PASSED |
| test_engine_and_networks | `test_garbage_is_rejected_not_crashed[broken4]` | PASSED |
| test_engine_and_networks | `test_bad_values_are_reported` | PASSED |
| test_engine_and_networks | `test_duplicate_ids_are_reported` | PASSED |
| test_engine_and_networks | `test_running_an_invalid_network_raises` | PASSED |
| test_engine_and_networks | `test_TC_Sim_02_same_seed_gives_the_same_result_and_a_new_seed_differs` | PASSED |
| test_engine_and_networks | `test_vehicles_are_conserved` | PASSED |
| test_engine_and_networks | `test_no_demand_means_no_vehicles` | PASSED |
| test_engine_and_networks | `test_more_demand_means_more_vehicles` | PASSED |
| test_engine_and_networks | `test_TC_Sim_03_metrics_are_complete_and_quick` | PASSED |
| test_engine_and_networks | `test_changing_the_green_time_changes_the_delay` | PASSED |
| test_engine_and_networks | `test_bad_parameters_are_rejected[params0]` | PASSED |
| test_engine_and_networks | `test_bad_parameters_are_rejected[params1]` | PASSED |
| test_engine_and_networks | `test_bad_parameters_are_rejected[params2]` | PASSED |
| test_engine_and_networks | `test_bad_parameters_are_rejected[params3]` | PASSED |
| test_engine_and_networks | `test_bad_parameters_are_rejected[params4]` | PASSED |
| test_engine_and_networks | `test_bad_parameters_are_rejected[params5]` | PASSED |
| test_engine_and_networks | `test_corridor_runs_and_every_signal_is_used` | PASSED |
| test_simulation_api | `test_roles` | PASSED |
| test_simulation_api | `test_validate_endpoint_reports_problems` | PASSED |
| test_simulation_api | `test_import_list_and_read_back` | PASSED |
| test_simulation_api | `test_import_rejects_unknown_and_tricky_names` | PASSED |
| test_simulation_api | `test_invalid_network_is_not_saved` | PASSED |
| test_simulation_api | `test_run_stores_metrics_and_trajectories` | PASSED |
| test_simulation_api | `test_run_errors` | PASSED |
| test_simulation_api | `test_operator_cannot_run` | PASSED |
| test_accessibility_wcag | `test_language_title_and_landmarks[/]` | PASSED |
| test_accessibility_wcag | `test_keyboard_users_can_skip_the_navigation[/]` | PASSED |
| test_accessibility_wcag | `test_every_field_has_a_label[/]` | PASSED |
| test_accessibility_wcag | `test_headings_do_not_skip_levels[/]` | PASSED |
| test_accessibility_wcag | `test_table_headers_say_whether_they_are_for_columns_or_rows[/]` | PASSED |
| test_accessibility_wcag | `test_no_other_structural_problems[/]` | PASSED |
| test_accessibility_wcag | `test_language_title_and_landmarks[/operator]` | PASSED |
| test_accessibility_wcag | `test_keyboard_users_can_skip_the_navigation[/operator]` | PASSED |
| test_accessibility_wcag | `test_every_field_has_a_label[/operator]` | PASSED |
| test_accessibility_wcag | `test_headings_do_not_skip_levels[/operator]` | PASSED |
| test_accessibility_wcag | `test_table_headers_say_whether_they_are_for_columns_or_rows[/operator]` | PASSED |
| test_accessibility_wcag | `test_no_other_structural_problems[/operator]` | PASSED |
| test_accessibility_wcag | `test_language_title_and_landmarks[/detection]` | PASSED |
| test_accessibility_wcag | `test_keyboard_users_can_skip_the_navigation[/detection]` | PASSED |
| test_accessibility_wcag | `test_every_field_has_a_label[/detection]` | PASSED |
| test_accessibility_wcag | `test_headings_do_not_skip_levels[/detection]` | PASSED |
| test_accessibility_wcag | `test_table_headers_say_whether_they_are_for_columns_or_rows[/detection]` | PASSED |
| test_accessibility_wcag | `test_no_other_structural_problems[/detection]` | PASSED |
| test_accessibility_wcag | `test_language_title_and_landmarks[/simulation]` | PASSED |
| test_accessibility_wcag | `test_keyboard_users_can_skip_the_navigation[/simulation]` | PASSED |
| test_accessibility_wcag | `test_every_field_has_a_label[/simulation]` | PASSED |
| test_accessibility_wcag | `test_headings_do_not_skip_levels[/simulation]` | PASSED |
| test_accessibility_wcag | `test_table_headers_say_whether_they_are_for_columns_or_rows[/simulation]` | PASSED |
| test_accessibility_wcag | `test_no_other_structural_problems[/simulation]` | PASSED |
| test_accessibility_wcag | `test_language_title_and_landmarks[/incidents]` | PASSED |
| test_accessibility_wcag | `test_keyboard_users_can_skip_the_navigation[/incidents]` | PASSED |
| test_accessibility_wcag | `test_every_field_has_a_label[/incidents]` | PASSED |
| test_accessibility_wcag | `test_headings_do_not_skip_levels[/incidents]` | PASSED |
| test_accessibility_wcag | `test_table_headers_say_whether_they_are_for_columns_or_rows[/incidents]` | PASSED |
| test_accessibility_wcag | `test_no_other_structural_problems[/incidents]` | PASSED |
| test_accessibility_wcag | `test_language_title_and_landmarks[/reports]` | PASSED |
| test_accessibility_wcag | `test_keyboard_users_can_skip_the_navigation[/reports]` | PASSED |
| test_accessibility_wcag | `test_every_field_has_a_label[/reports]` | PASSED |
| test_accessibility_wcag | `test_headings_do_not_skip_levels[/reports]` | PASSED |
| test_accessibility_wcag | `test_table_headers_say_whether_they_are_for_columns_or_rows[/reports]` | PASSED |
| test_accessibility_wcag | `test_no_other_structural_problems[/reports]` | PASSED |
| test_accessibility_wcag | `test_language_title_and_landmarks[/admin]` | PASSED |
| test_accessibility_wcag | `test_keyboard_users_can_skip_the_navigation[/admin]` | PASSED |
| test_accessibility_wcag | `test_every_field_has_a_label[/admin]` | PASSED |
| test_accessibility_wcag | `test_headings_do_not_skip_levels[/admin]` | PASSED |
| test_accessibility_wcag | `test_table_headers_say_whether_they_are_for_columns_or_rows[/admin]` | PASSED |
| test_accessibility_wcag | `test_no_other_structural_problems[/admin]` | PASSED |
| test_accessibility_wcag | `test_text_colours_meet_4_5_to_1[light]` | PASSED |
| test_accessibility_wcag | `test_text_colours_meet_4_5_to_1[dark]` | PASSED |
| test_accessibility_wcag | `test_borders_and_focus_ring_meet_3_to_1[light]` | PASSED |
| test_accessibility_wcag | `test_borders_and_focus_ring_meet_3_to_1[dark]` | PASSED |
