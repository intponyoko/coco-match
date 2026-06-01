from typing import Any, cast

from .config import config_list, config_table


def department_code_prefix(department_name: str) -> str:
    return department_name[:3].upper()


def japanese_staff_name(
    index: int,
    family_names: list[str],
    given_names: list[str],
) -> str:
    family = family_names[index % len(family_names)]
    given = given_names[(index // len(family_names) + index) % len(given_names)]
    cycle = index // (len(family_names) * len(given_names))
    if cycle == 0:
        return f"{family} {given}"
    return f"{family} {given}{cycle + 1}"


def weighted_sequence(
    values: list[str],
    weights: dict[str, Any],
    count: int,
) -> list[str]:
    total_weight = sum(float(weights[value]) for value in values)
    raw_counts = [
        (value, count * float(weights[value]) / total_weight) for value in values
    ]
    floors = {value: int(raw_count) for value, raw_count in raw_counts}
    remainder = count - sum(floors.values())
    fractions = sorted(
        raw_counts,
        key=lambda item: item[1] - int(item[1]),
        reverse=True,
    )
    for value, _ in fractions[:remainder]:
        floors[value] += 1

    sequence = []
    for value in values:
        sequence.extend([value] * floors[value])
    return [
        value
        for _, value in sorted(
            enumerate(sequence),
            key=lambda item: (item[0] * 37) % max(count, 1),
        )
    ]


def generate_staffs(
    config: dict[str, Any],
    count: int,
    departments: list[dict],
    titles: list[dict],
) -> list[dict]:
    staff_names = config_table(config, "staff_names")
    staff_distribution = config_table(config, "staff_distribution")
    family_names = cast(list[str], staff_names["family"])
    given_names = cast(list[str], staff_names["given"])
    staff_titles = config_list(config, "staff_titles")
    title_code_by_name = {str(title["name"]): str(title["code"]) for title in titles}
    department_names = [str(department["name"]) for department in departments]
    department_by_name = {
        str(department["name"]): str(department["code"]) for department in departments
    }
    department_sequence = weighted_sequence(
        department_names,
        config_table(staff_distribution, "departments"),
        count,
    )
    title_weights = config_table(staff_distribution, "titles")
    department_counts = {
        department_name: department_sequence.count(department_name)
        for department_name in department_names
    }
    title_sequences_by_department = {
        department_name: weighted_sequence(
            staff_titles,
            title_weights,
            department_count,
        )
        for department_name, department_count in department_counts.items()
    }
    title_offsets = {department_name: 0 for department_name in department_names}
    rows = []
    for index in range(count):
        department_name = department_sequence[index]
        title_offset = title_offsets[department_name]
        title_offsets[department_name] += 1
        rows.append(
            {
                "code": f"STF-{index + 1:03d}",
                "name": japanese_staff_name(index, family_names, given_names),
                "department_code": department_by_name[department_name],
                "title_code": title_code_by_name[
                    title_sequences_by_department[department_name][title_offset]
                ],
            }
        )
    return [
        row
        for _, row in sorted(
            enumerate(rows),
            key=lambda item: (item[0] * 29) % max(count, 1),
        )
    ]
