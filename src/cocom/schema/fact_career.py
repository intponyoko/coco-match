from cocom.schema.axis import BaseModel


class StaffCareer(BaseModel):
    staff_code: str
    skill_code: str
    start_period_code: str
    end_period_code: str

    skill_level_current: int
    skill_level_target: int

    class Config:  # pyright: ignore[reportIncompatibleVariableOverride]
        unique = [
            "staff_code",
            "skill_code",
            "start_period_code",
            "end_period_code",
        ]
