from studentlink.modules.reg._reg_module import RegModule
from studentlink.util import normalize, Semester, Abbr, PageParseError
from studentlink.util import async_ttl_cache

import re


class Add(RegModule):
    MODULE_NAME = "reg/add/_start.pl"
    
    get_page_cached = async_ttl_cache(60)(RegModule.get_page)

    async def get_college_codes(self, semester: Semester) -> list[str]:
        page = await self.get_page_cached(semester)
        college_select, = re.findall(r'<SELECT NAME=College onChange="ClearCollege\(\);">[\S\s]*?<\/SELECT>', page)
        return re.findall(r'(?<=<OPTION>)([A-Z]{3})', college_select)
    
    async def check_reg_open(self, semester: Semester) -> bool:
        page = await self.get_page(semester)
        return not "You requested a registration option not available for the semester." in page