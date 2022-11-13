from ._module import Module
from bs4 import BeautifulSoup
import re
from studentlink.util import normalize, sem_key, Semester
from studentlink.data.class_ import ClassView, Weekday, Event, Building
from datetime import datetime
from bs4.element import Tag


class AddPlanner(Module):
    MODULE_NAME = "reg/plan/add_planner.pl"

    async def add_to_planner(self, semester: Semester, year: int, reg_id: str):
        r1 = await self.client.session.get(
            Module.mod_url("reg/option/_start.pl"),
            params={"KeySem": sem_key(semester, year)},
        )
        
        page = await self.get_page(
            params={
                "SelectIt": reg_id,
                "KeySem": sem_key(semester, year),
            }
        )
        print(page)
        if (
            "You requested a registration option not available for the semester."
            in page
        ):
            return False
