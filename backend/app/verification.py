"""Independent verifier: do not trust candidate-supplied scores or constraints."""


class InvalidSchedule(ValueError):
    pass


def verify_schedule(durations: list[int], assignments: list[int], machines: int) -> int:
    if not isinstance(assignments, list) or len(assignments) != len(durations):
        raise InvalidSchedule("each job must have exactly one assignment")
    if not isinstance(machines, int) or machines < 1:
        raise InvalidSchedule("machine count must be positive")
    if not durations or any(type(duration) is not int or duration <= 0 for duration in durations):
        raise InvalidSchedule("job durations must be positive integers")

    loads = [0] * machines
    for index, machine in enumerate(assignments):
        if type(machine) is not int or not 0 <= machine < machines:
            raise InvalidSchedule(f"job {index} has an out-of-range machine")
        loads[machine] += durations[index]
    return max(loads)
