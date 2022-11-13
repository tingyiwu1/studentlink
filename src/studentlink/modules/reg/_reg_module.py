from __future__ import annotations
from typing import TYPE_CHECKING
from abc import ABC
from studentlink.modules._module import Module
from studentlink.util import Semester

if TYPE_CHECKING:
    from studentlink import StudentLink


class RegOptions(Module):
    MODULE_NAME = "reg/option/_start.pl"

    def __init__(self, client: StudentLink):
        super().__init__(client)
        self.loaded_sems = set()

    async def load_semester(self, semester: Semester):
        await self.get_page(params={"KeySem": semester})


class RegModule(Module, ABC):
    MODULE_NAME = None

    def __init__(self, client: StudentLink):
        super().__init__(client)
        client.module(RegOptions)

    async def get_page(
        self, semester: Semester, *, params: dict[str, str] = None
    ) -> str:
        ro: RegOptions = self.client.module(RegOptions)
        if not semester in ro.loaded_sems:
            await ro.load_semester(semester)
        return await super().get_page(params={"KeySem": semester} | (params or {}))
