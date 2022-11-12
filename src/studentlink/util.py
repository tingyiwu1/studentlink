import unicodedata
from functools import partial
from enum import IntEnum


class Semester(IntEnum):
    SUMMER1 = 1
    SUMMER2 = 2
    FALL = 3
    SPRING = 4

def normalize(text: str) -> str:
    if not isinstance(text, str):
        return None
    return unicodedata.normalize("NFKD", text).strip()

# summer 1 2022 -> 20231
# summer 2 2022 -> 20232
# fall 2022 -> 20233
# spring 2023 -> 20234
def sem_key(semester: Semester, year: int) -> int:
    return (year + int(semester < 4)) * 10 + semester