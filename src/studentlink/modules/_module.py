from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from yarl import URL

if TYPE_CHECKING:
    from studentlink import StudentLink


class Module(ABC):
    @property
    @abstractmethod
    def MODULE_NAME(self):
        pass

    def __init__(self, client: StudentLink):
        self.client = client

    @staticmethod
    def mod_url(module: str):
        return URL("https://www.bu.edu/link/bin/uiscgi_studentlink.pl").with_query(
            ModuleName=module
        )

    async def get_page(self, *, params: dict[str, str] = None) -> str:
        r = await self.client.session.get(Module.mod_url(self.MODULE_NAME), params=params)
        return await r.text()


class PublicModule(Module, ABC):
    ...
