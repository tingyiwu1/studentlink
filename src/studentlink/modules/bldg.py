from ._module import PublicModule
from studentlink.data.class_ import Building
from studentlink.util import async_ttl_cache
import re


class Bldg(PublicModule):
    MODULE_NAME = "bldg.pl"
    REFRESH_EVERY_SECONDS = 3600
    
    @async_ttl_cache(REFRESH_EVERY_SECONDS)
    async def get_building(self, abbr: str) -> Building:
        page = await self.get_page(params={"BldgCd": abbr})
        abbr, desc, addr = re.findall(
            r"(?:Abbreviation|Description|Address):\n.+<TD ALIGN=left>(.+)\n", page
        )
        return Building(
            abbreviation=abbr,
            description=desc,
            address=addr,
        )