from typing import Any, cast

import pandas as pd

from .config import config_list, config_table, positive_int
from .masters import skill_max_level
from .staff import department_code_prefix


def generate_staff_career(
    config: dict[str, Any],
    skills_per_staff: int,
    staffs: list[dict],
    titles: list[dict],
    skills: list[dict],
    departments: list[dict],
    role_skills: list[dict],
    fiscal_periods: list[dict],
    role_demand_rows: list[dict[str, Any]] | None = None,
) -> list[dict]:
    positive_int("staff_career_skills_per_staff", skills_per_staff)
    if skills_per_staff > len(skills):
        raise ValueError(
            "staff_career_skills_per_staff must be less than or equal to "
            f"the number of skills: {skills_per_staff} > {len(skills)}"
        )

    period_starts = [pd.Timestamp(period["start"]) for period in fiscal_periods]
    last_period_end = pd.Timestamp(fiscal_periods[-1]["end"])
    first_period_start = period_starts[0]
    career_windows = []
    year_index = 0
    while True:
        window_start = first_period_start + pd.DateOffset(years=year_index)
        window_end = first_period_start + pd.DateOffset(years=year_index + 1)
        if last_period_end < window_end - pd.Timedelta(days=1):
            break

        period_indexes = [
            index
            for index, period_start in enumerate(period_starts)
            if window_start <= period_start < window_end
        ]
        if period_indexes:
            career_windows.append(
                (
                    fiscal_periods[period_indexes[0]]["code"],
                    fiscal_periods[period_indexes[-1]]["code"],
                )
            )
        year_index += 1

    staff_titles = config_list(config, "staff_titles")
    title_ranks = {title: index for index, title in enumerate(staff_titles)}
    title_name_by_code = {str(title["code"]): str(title["name"]) for title in titles}
    max_level = skill_max_level(config)
    simulation = config_table(config, "career_simulation")
    yearly_events_min = int(simulation["yearly_skill_events_min"])
    yearly_events_max = int(simulation["yearly_skill_events_max"])
    target_events_min = int(simulation["target_growth_events_min"])
    target_events_max = int(simulation["target_growth_events_max"])
    career_years_by_title = cast(dict[str, int], simulation["career_years_by_title"])
    title_level_caps = cast(dict[str, int], simulation["title_level_caps"])
    role_coverage_by_title = cast(dict[str, int], simulation["role_coverage_by_title"])
    title_min_total_skill_level = cast(
        dict[str, int],
        simulation.get("title_min_total_skill_level", {}),
    )
    title_min_management_skill_level = cast(
        dict[str, int],
        simulation.get("title_min_management_skill_level", {}),
    )
    management = config_table(config, "management")
    management_threshold = str(management["staff_title_threshold"])
    management_threshold_rank = title_ranks[management_threshold]
    title_management_skills = cast(
        list[str],
        management["title_management_skills"],
    )
    skill_by_code = {str(skill["code"]): skill for skill in skills}
    department_prefix_by_code = {
        str(department["code"]): department_code_prefix(str(department["name"]))
        for department in departments
    }
    skill_codes_by_prefix: dict[str, list[str]] = {}
    for skill in skills:
        code = str(skill["code"])
        parts = code.split("-")
        if len(parts) >= 3:
            skill_codes_by_prefix.setdefault(parts[1], []).append(code)

    role_skills_by_prefix: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for role_skill in role_skills:
        role_code = str(role_skill["role_code"])
        parts = role_code.split("-")
        if len(parts) < 3:
            continue
        prefix = parts[1]
        role_skills_by_prefix.setdefault(prefix, {}).setdefault(role_code, []).append(
            role_skill
        )

    role_demand_weights: dict[str, float] = {}
    role_training_gap: dict[str, int] = {}
    for demand_row in role_demand_rows or []:
        role_code = str(demand_row.get("role_code", ""))
        if not role_code:
            continue
        headcount = float(demand_row.get("headcount", 1))
        allocation = float(demand_row.get("allocation_percentage", 100))
        start_month = int(demand_row.get("phase_start_month", 1))
        end_month = int(demand_row.get("phase_end_month", start_month))
        phase_months = max(1, end_month - start_month + 1)
        role_demand_weights[role_code] = role_demand_weights.get(
            role_code, 0.0
        ) + headcount * allocation * phase_months
        training_headcount = int(demand_row.get("training_headcount", 0))
        training_gap = int(demand_row.get("role_phase_training_max_skill_gap", 0))
        if training_headcount > 0 and training_gap > 0:
            role_training_gap[role_code] = max(
                role_training_gap.get(role_code, 0),
                training_gap,
            )

    def event_count(seed: int, minimum: int, maximum: int) -> int:
        if maximum < minimum:
            raise ValueError(f"event maximum must be >= minimum: {maximum} < {minimum}")
        return minimum + seed % (maximum - minimum + 1)

    def career_title_for_year(current_title: str, elapsed_year: int) -> str:
        reachable_titles = [
            title
            for title in staff_titles
            if title_ranks[title] <= title_ranks[current_title]
        ]
        for title in reachable_titles:
            if elapsed_year <= int(career_years_by_title[title]):
                return title
        return current_title

    def ordered_unique(values: list[str]) -> list[str]:
        seen = set()
        result = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def role_skill_pool(
        department_role_skills: dict[str, list[dict[str, Any]]],
        role_codes: list[str],
    ) -> tuple[list[str], dict[str, int]]:
        preferred_skills = []
        target_levels: dict[str, int] = {}
        for role_code in role_codes:
            role_skill_rows = department_role_skills.get(role_code, [])
            required_skills = [
                role_skill
                for role_skill in role_skill_rows
                if bool(role_skill["required"])
            ]
            optional_skills = [
                role_skill
                for role_skill in role_skill_rows
                if not bool(role_skill["required"])
            ]
            for role_skill in required_skills + optional_skills:
                skill_code = str(role_skill["skill_code"])
                preferred_skills.append(skill_code)
                if bool(role_skill["required"]):
                    target_levels[skill_code] = max(
                        target_levels.get(skill_code, 0),
                        int(role_skill["skill_level"]),
        )
        return ordered_unique(preferred_skills), target_levels

    def ordered_role_codes(
        department_role_skills: dict[str, list[dict[str, Any]]],
        staff_index: int,
    ) -> list[str]:
        role_codes = sorted(
            department_role_skills,
            key=lambda role_code: (
                -role_demand_weights.get(role_code, 0.0),
                role_code,
            ),
        )
        if not role_codes:
            return []

        # Keep high-demand roles in front while rotating staff through them so the
        # organization does not create identical careers for every person.
        focus_width = min(len(role_codes), max(3, len(role_codes) // 2))
        offset = staff_index % focus_width
        return role_codes[offset:] + role_codes[:offset]

    def role_skill_targets(
        department_role_skills: dict[str, list[dict[str, Any]]],
        role_code: str,
    ) -> tuple[dict[str, int], dict[str, int]]:
        required_targets: dict[str, int] = {}
        optional_targets: dict[str, int] = {}
        for role_skill in department_role_skills.get(role_code, []):
            skill_code = str(role_skill["skill_code"])
            level = int(role_skill["skill_level"])
            if bool(role_skill["required"]):
                required_targets[skill_code] = max(
                    required_targets.get(skill_code, 0), level
                )
            else:
                optional_targets[skill_code] = max(
                    optional_targets.get(skill_code, 0), level
                )
        return required_targets, optional_targets

    def apply_role_event(
        levels: dict[str, int],
        department_role_skills: dict[str, list[dict[str, Any]]],
        target_role_codes: list[str],
        fallback_skill_pool: list[str],
        level_cap: int,
        seed: int,
    ) -> None:
        if not target_role_codes and not fallback_skill_pool:
            return

        rotated_roles = (
            target_role_codes[seed % len(target_role_codes) :]
            + target_role_codes[: seed % len(target_role_codes)]
            if target_role_codes
            else []
        )
        for role_code in rotated_roles:
            required_targets, optional_targets = role_skill_targets(
                department_role_skills,
                role_code,
            )
            missing_or_low_required = [
                skill_code
                for skill_code, required_level in required_targets.items()
                if levels.get(skill_code, 0) < min(level_cap, required_level)
            ]
            if missing_or_low_required:
                skill_code = sorted(
                    missing_or_low_required,
                    key=lambda code: (
                        levels.get(code, 0),
                        -required_targets[code],
                        code,
                    ),
                )[seed % len(missing_or_low_required)]
                levels[skill_code] = min(
                    level_cap,
                    required_targets[skill_code],
                    levels.get(skill_code, 0) + 1,
                )
                return

            optional_growth = [
                skill_code
                for skill_code, optional_level in optional_targets.items()
                if levels.get(skill_code, 0) < min(level_cap, optional_level)
            ]
            if optional_growth:
                skill_code = sorted(optional_growth)[seed % len(optional_growth)]
                levels[skill_code] = min(
                    level_cap,
                    optional_targets[skill_code],
                    levels.get(skill_code, 0) + 1,
                )
                return

        fallback_growth = [
            skill_code
            for skill_code in fallback_skill_pool
            if levels.get(skill_code, 0) < level_cap
        ]
        if not fallback_growth:
            return
        skill_code = fallback_growth[seed % len(fallback_growth)]
        levels[skill_code] = min(level_cap, levels.get(skill_code, 0) + 1)

    def raise_total_skill_level(
        levels: dict[str, int],
        skill_pool: list[str],
        level_cap: int,
        minimum_total: int,
        seed: int,
    ) -> None:
        while sum(levels.values()) < minimum_total:
            candidates = [
                skill_code
                for skill_code in skill_pool
                if levels.get(skill_code, 0) < level_cap
            ]
            if not candidates:
                return
            skill_code = sorted(
                candidates,
                key=lambda code: (levels.get(code, 0), code),
            )[seed % len(candidates)]
            levels[skill_code] = min(level_cap, levels.get(skill_code, 0) + 1)

    rows = []
    for year_index, (period_start, period_end) in enumerate(career_windows):
        for staff_index, staff in enumerate(staffs):
            current_title = title_name_by_code[str(staff["title_code"])]
            title_rank = title_ranks[current_title]
            department_prefix = department_prefix_by_code[str(staff["department_code"])]
            department_skill_codes = skill_codes_by_prefix.get(department_prefix, [])
            department_role_skills = role_skills_by_prefix.get(department_prefix, {})
            role_codes = ordered_role_codes(department_role_skills, staff_index)
            career_years = int(career_years_by_title[current_title])
            levels: dict[str, int] = {}
            final_target_levels: dict[str, int] = {}
            final_target_roles: list[str] = []

            for elapsed_year in range(1, career_years + 1):
                career_title = career_title_for_year(current_title, elapsed_year)
                career_title_rank = title_ranks[career_title]
                role_coverage = int(role_coverage_by_title[career_title])
                selected_role_codes = role_codes[: min(role_coverage, len(role_codes))]
                final_target_roles = ordered_unique(
                    final_target_roles + selected_role_codes
                )
                skill_pool, target_levels = role_skill_pool(
                    department_role_skills,
                    selected_role_codes,
                )
                final_target_levels.update(target_levels)
                if career_title_rank >= management_threshold_rank:
                    management_level = int(
                        title_min_management_skill_level.get(career_title, 0)
                    )
                    for skill_code in title_management_skills:
                        if skill_code not in skill_pool:
                            skill_pool.append(skill_code)
                        if management_level > 0:
                            final_target_levels[skill_code] = max(
                                final_target_levels.get(skill_code, 0),
                                management_level,
                            )
                skill_pool = ordered_unique(skill_pool + department_skill_codes)

                level_cap = min(max_level, int(title_level_caps[career_title]))
                events = event_count(
                    staff_index + elapsed_year,
                    yearly_events_min,
                    yearly_events_max,
                )
                for event_index in range(events):
                    apply_role_event(
                        levels,
                        department_role_skills,
                        selected_role_codes,
                        skill_pool,
                        level_cap,
                        staff_index * 97 + elapsed_year * 11 + event_index,
                    )

            current_skill_pool = ordered_unique(
                list(final_target_levels)
                + department_skill_codes
                + (
                    title_management_skills
                    if title_rank >= management_threshold_rank
                    else []
                )
            )
            current_level_cap = min(max_level, int(title_level_caps[current_title]))
            management_min_level = int(
                title_min_management_skill_level.get(current_title, 0)
            )
            if title_rank >= management_threshold_rank and management_min_level > 0:
                for skill_code in title_management_skills:
                    levels[skill_code] = max(
                        levels.get(skill_code, 0),
                        min(current_level_cap, management_min_level),
                    )
                    if skill_code not in current_skill_pool:
                        current_skill_pool.append(skill_code)
            total_growth_skill_pool = (
                [
                    skill_code
                    for skill_code in current_skill_pool
                    if skill_code not in title_management_skills
                ]
                if management_min_level > 0
                else current_skill_pool
            )
            raise_total_skill_level(
                levels,
                total_growth_skill_pool,
                current_level_cap,
                int(title_min_total_skill_level.get(current_title, 0)),
                staff_index * 173 + year_index * 19,
            )
            if title_rank >= management_threshold_rank and management_min_level > 0:
                for skill_code in title_management_skills:
                    levels[skill_code] = min(current_level_cap, management_min_level)

            next_year_levels = dict(levels)
            target_events = event_count(
                staff_index + career_years + year_index,
                target_events_min,
                target_events_max,
            )
            for event_index in range(target_events):
                before_levels = dict(next_year_levels)
                apply_role_event(
                    next_year_levels,
                    department_role_skills,
                    final_target_roles,
                    current_skill_pool,
                    current_level_cap,
                    staff_index * 131 + year_index * 17 + event_index,
                )
                for skill_code, level in next_year_levels.items():
                    current_level = levels.get(skill_code, 0)
                    if (
                        before_levels.get(skill_code, 0) != level
                        and level > current_level + 1
                    ):
                        next_year_levels[skill_code] = current_level + 1

            selected_skill_codes = sorted(
                set(levels)
                | {
                    skill_code
                    for skill_code, level in next_year_levels.items()
                    if level > 0
                },
                key=lambda skill_code: (
                    -max(
                        levels.get(skill_code, 0), next_year_levels.get(skill_code, 0)
                    ),
                    skill_code,
                ),
            )[:skills_per_staff]
            selected_skills = [
                skill_by_code[skill_code]
                for skill_code in selected_skill_codes
                if skill_code in skill_by_code
            ]
            for skill in selected_skills:
                skill_code = str(skill["code"])
                rows.append(
                    {
                        "staff_code": staff["code"],
                        "skill_code": skill_code,
                        "start_period_code": period_start,
                        "end_period_code": period_end,
                        "skill_level_current": levels.get(skill_code, 0),
                        "skill_level_target": next_year_levels.get(
                            skill_code,
                            levels.get(skill_code, 0),
                        ),
                    }
                )

    coverage = cast(dict[str, Any] | None, config.get("staff_skill_coverage"))
    min_candidates_per_role = (
        int(coverage.get("min_candidates_per_role", 0)) if coverage is not None else 0
    )
    if min_candidates_per_role <= 0:
        return rows
    if coverage is None:
        return rows

    row_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {
        (
            str(row["staff_code"]),
            str(row["skill_code"]),
            str(row["start_period_code"]),
            str(row["end_period_code"]),
        ): row
        for row in rows
    }

    def skill_levels_by_staff() -> dict[str, dict[str, int]]:
        levels_by_staff: dict[str, dict[str, int]] = {}
        for row in rows:
            staff_code = str(row["staff_code"])
            skill_code = str(row["skill_code"])
            levels_by_staff.setdefault(staff_code, {})[skill_code] = max(
                levels_by_staff.setdefault(staff_code, {}).get(skill_code, 0),
                int(row["skill_level_current"]),
            )
        return levels_by_staff

    staff_by_prefix: dict[str, list[dict]] = {}
    for staff in staffs:
        department_prefix = department_prefix_by_code[str(staff["department_code"])]
        staff_by_prefix.setdefault(department_prefix, []).append(staff)
    for department_staffs in staff_by_prefix.values():
        department_staffs.sort(
            key=lambda staff: (
                -title_ranks[title_name_by_code[str(staff["title_code"])]],
                str(staff["code"]),
            )
        )

    role_required_skills: dict[str, list[dict[str, Any]]] = {}
    for role_skill in role_skills:
        if bool(role_skill["required"]):
            role_required_skills.setdefault(str(role_skill["role_code"]), []).append(
                role_skill
            )

    def qualifies(
        levels: dict[str, int], required_skills: list[dict[str, Any]]
    ) -> bool:
        return all(
            levels.get(str(required_skill["skill_code"]), 0)
            >= int(required_skill["skill_level"])
            for required_skill in required_skills
        )

    def required_skill_gap(
        levels: dict[str, int], required_skills: list[dict[str, Any]]
    ) -> int:
        return sum(
            max(
                0,
                int(required_skill["skill_level"])
                - levels.get(str(required_skill["skill_code"]), 0),
            )
            for required_skill in required_skills
        )

    def upsert_staff_skill(
        staff_code: str,
        skill_code: str,
        required_level: int,
    ) -> None:
        for period_start, period_end in career_windows:
            key = (staff_code, skill_code, period_start, period_end)
            existing = row_by_key.get(key)
            if existing is None:
                row = {
                    "staff_code": staff_code,
                    "skill_code": skill_code,
                    "start_period_code": period_start,
                    "end_period_code": period_end,
                    "skill_level_current": required_level,
                    "skill_level_target": required_level,
                }
                rows.append(row)
                row_by_key[key] = row
                continue
            existing["skill_level_current"] = max(
                int(existing["skill_level_current"]),
                required_level,
            )
            existing["skill_level_target"] = max(
                int(existing["skill_level_target"]),
                int(existing["skill_level_current"]),
            )

    for role_code, required_skills in sorted(role_required_skills.items()):
        parts = role_code.split("-")
        if len(parts) < 3:
            continue
        department_staffs = staff_by_prefix.get(parts[1], [])
        if not department_staffs:
            continue
        levels_by_staff = skill_levels_by_staff()
        qualified_staff_codes = [
            str(staff["code"])
            for staff in department_staffs
            if qualifies(levels_by_staff.get(str(staff["code"]), {}), required_skills)
        ]
        if len(qualified_staff_codes) >= min_candidates_per_role:
            continue

        role_offset = int(parts[2]) if parts[2].isdigit() else 0
        rotated_staffs = (
            department_staffs[role_offset % len(department_staffs) :]
            + department_staffs[: role_offset % len(department_staffs)]
        )
        for staff in rotated_staffs:
            staff_code = str(staff["code"])
            if staff_code in qualified_staff_codes:
                continue
            for required_skill in required_skills:
                upsert_staff_skill(
                    staff_code,
                    str(required_skill["skill_code"]),
                    int(required_skill["skill_level"]),
                )
            qualified_staff_codes.append(staff_code)
            if len(qualified_staff_codes) >= min_candidates_per_role:
                break

    min_training_candidates_per_role = int(
        coverage.get(
            "min_training_candidates_per_role",
            max(1, min_candidates_per_role),
        )
    )
    if min_training_candidates_per_role <= 0:
        return rows

    minimum_title_role_coverage = cast(
        dict[str, int],
        coverage.get("minimum_title_role_coverage", {"Associate": 1}),
    )

    for staff in staffs:
        staff_code = str(staff["code"])
        title_name = title_name_by_code[str(staff["title_code"])]
        required_role_count = int(minimum_title_role_coverage.get(title_name, 0))
        if required_role_count <= 0:
            continue
        department_prefix = department_prefix_by_code[str(staff["department_code"])]
        department_role_skills = role_skills_by_prefix.get(department_prefix, {})
        if not department_role_skills:
            continue
        levels_by_staff = skill_levels_by_staff()
        levels = levels_by_staff.get(staff_code, {})
        qualified_roles = [
            role_code
            for role_code, required_skills in role_required_skills.items()
            if role_code.startswith(f"ROLE-{department_prefix}-")
            and qualifies(levels, required_skills)
        ]
        if len(qualified_roles) >= required_role_count:
            continue
        role_codes = ordered_role_codes(department_role_skills, int(staff_code[-3:]))
        title_cap = min(max_level, int(title_level_caps[title_name]))
        for role_code in role_codes:
            if role_code in qualified_roles:
                continue
            required_skills = role_required_skills.get(role_code, [])
            if not required_skills:
                continue
            can_reach_role = all(
                int(required_skill["skill_level"]) <= title_cap
                for required_skill in required_skills
            )
            if not can_reach_role:
                continue
            for required_skill in required_skills:
                upsert_staff_skill(
                    staff_code,
                    str(required_skill["skill_code"]),
                    int(required_skill["skill_level"]),
                )
            qualified_roles.append(role_code)
            if len(qualified_roles) >= required_role_count:
                break

    for role_code, required_skills in sorted(role_required_skills.items()):
        training_gap = role_training_gap.get(role_code, 0)
        if training_gap <= 0:
            continue
        parts = role_code.split("-")
        if len(parts) < 3:
            continue
        department_staffs = staff_by_prefix.get(parts[1], [])
        if not department_staffs:
            continue
        levels_by_staff = skill_levels_by_staff()
        training_candidate_codes = [
            str(staff["code"])
            for staff in department_staffs
            if not qualifies(levels_by_staff.get(str(staff["code"]), {}), required_skills)
            and required_skill_gap(
                levels_by_staff.get(str(staff["code"]), {}),
                required_skills,
            )
            <= training_gap
        ]
        if len(training_candidate_codes) >= min_training_candidates_per_role:
            continue

        lower_title_staffs = sorted(
            department_staffs,
            key=lambda staff: (
                title_ranks[title_name_by_code[str(staff["title_code"])]],
                str(staff["code"]),
            ),
        )
        for staff in lower_title_staffs:
            staff_code = str(staff["code"])
            if staff_code in training_candidate_codes:
                continue
            title_name = title_name_by_code[str(staff["title_code"])]
            title_cap = min(max_level, int(title_level_caps[title_name]))
            capped_levels = {
                str(required_skill["skill_code"]): min(
                    int(required_skill["skill_level"]),
                    title_cap,
                )
                for required_skill in required_skills
            }
            capped_gap = sum(
                int(required_skill["skill_level"])
                - capped_levels[str(required_skill["skill_code"])]
                for required_skill in required_skills
            )
            if capped_gap > training_gap:
                continue
            if capped_gap <= 0:
                continue
            for skill_code, capped_level in capped_levels.items():
                upsert_staff_skill(staff_code, skill_code, capped_level)
            training_candidate_codes.append(staff_code)
            if len(training_candidate_codes) >= min_training_candidates_per_role:
                break

    return rows
