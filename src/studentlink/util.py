import unicodedata
from functools import partial
from enum import IntEnum
from dataclasses import dataclass


class Sem(IntEnum):
    SUMMER1 = 1
    SUMMER2 = 2
    FALL = 3
    SPRING = 4


class Semester(int):
    # summer 1 2022 -> 20231
    # summer 2 2022 -> 20232
    # fall 2022 -> 20233
    # spring 2023 -> 20234
    def __new__(cls, sem: Sem, year: int):
        return super().__new__(cls, (year + int(sem < 4)) * 10 + sem)

    @classmethod
    def from_str(cls, str: str):
        semester, year = str.split(" ")
        semester = Sem[semester.upper()]
        year = int(year)
        return cls(semester, year)

    @classmethod
    def from_key(cls, key: int):
        return super().__new__(cls, key)

    @property
    def year(self) -> int:
        return self // 10 - int(self % 10 < 4)

    @property
    def semester(self) -> Sem:
        return Sem(self % 10)


def normalize(text: str) -> str:
    if not isinstance(text, str):
        return None
    return unicodedata.normalize("NFKD", text).strip()
