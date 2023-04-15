from __future__ import annotations
from typing import TYPE_CHECKING
from abc import ABC
from studentlink.modules._module import Module
from studentlink.util import Semester
from studentlink.util import async_ttl_cache

if TYPE_CHECKING:
    from studentlink import StudentLink


class RegOptions(Module):
    MODULE_NAME = "reg/option/_start.pl"
    REFRESH_EVERY_SECONDS = 60 * 60 * 2
    cache = {}

    def __init__(self, client: StudentLink):
        super().__init__(client)

    @async_ttl_cache(REFRESH_EVERY_SECONDS, cache=cache)
    async def load_semester(self, semester: Semester):
        page = await self.get_page(params={"KeySem": semester})
        return page

class RegModule(Module, ABC):
    MODULE_NAME = None

    def __init__(self, client: StudentLink):
        super().__init__(client)

    async def get_page(
        self, semester: Semester, *, params: dict[str, str] = None
    ) -> str:
        ro: RegOptions = self.client.module(RegOptions)
        await ro.load_semester(semester)
        # TODO refresh cache if fails
        return await super().get_page(params={"KeySem": semester} | (params or {}))


class UnavailableOptionError(Exception):
    pass
