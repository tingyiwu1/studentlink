from studentlink.modules.reg._reg_module import RegModule, UnavailableOptionError
from studentlink.util import Semester
from bs4 import BeautifulSoup
import re
from studentlink.util import normalize, Semester
from studentlink.data.class_ import ClassView, Weekday, Event, Building
from datetime import datetime
from bs4.element import Tag


class ConfirmDrop(RegModule):
    MODULE_NAME = "reg/drop/confirm_drop.pl"

    async def confirm_drop(self, semester: Semester, drop_id: str):
        page = await self.get_page(
            semester,
            params={"DropIt": drop_id},
        )
        if (
            "You requested a registration option not available for the semester."
            in page
        ):
            raise UnavailableOptionError()

        soup = BeautifulSoup(page, "html5lib")
        data_rows: list[Tag]
        _, *data_rows = (
            soup.find("b", text="Semester:")
            .find_next("table")
            .tbody.find_all("tr", recursive=False)
        )
        result: dict[str, tuple(bool, str)] = {}
        for tr in data_rows:
            match tr.find_all("td", recursive=False):
                case [
                    Tag(text=abbreviation),
                    Tag(text=status),
                    *_,
                    Tag(text=message)
                ]:
                    result[abbreviation] = (True if status == "DRP-ST" else False, message)
        return result
