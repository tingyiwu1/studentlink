from studentlink.modules.reg._reg_module import RegModule, UnavailableOptionError
from studentlink.util import Semester
from bs4 import BeautifulSoup
import re
from studentlink.util import normalize, Semester, PageParseError
from studentlink.data.class_ import ClassView, Weekday, Event, Building
from datetime import datetime
from bs4.element import Tag


class ConfirmClasses(RegModule):
    MODULE_NAME = "reg/add/confirm_classes.pl"

    async def confirm_class(self, semester: Semester, reg_id: str):
        page = await self.get_page(
            semester,
            params={"SelectIt": reg_id},
        )
        if (
            "You requested a registration option not available for the semester."
            in page
        ):
            raise UnavailableOptionError()

        soup = BeautifulSoup(page, "html5lib")
        data_rows: list[Tag]
        try:
            _, *data_rows = (
                soup.find("b", text="Semester: ")
                .find_next("table")
                .tbody.find_all("tr", recursive=False)
            )
        except AttributeError:
            raise PageParseError(f"Failed to parse register confirmation: {page}")
        result: dict[str, tuple[bool, str]] = {}
        for tr in data_rows:
            match tr.find_all("td", recursive=False):
                case [
                    Tag(
                        contents=[
                            Tag(
                                name="img",
                                attrs={
                                    "src": "https://www.bu.edu/link/student/images/xmark.gif"
                                    | "https://www.bu.edu/link/student/images/checkmark.gif" as status
                                },
                            )
                        ]
                    ),
                    Tag(text=abbreviation),
                    *_,
                    Tag(text=message),
                ]:
                    result[abbreviation] = (
                        True if "checkmark" in status else False,
                        message,
                    )

        return result
