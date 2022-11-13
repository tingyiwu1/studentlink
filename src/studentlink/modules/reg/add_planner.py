from studentlink.modules.reg._reg_module import RegModule
from studentlink.util import Semester


class AddPlanner(RegModule):
    MODULE_NAME = "reg/plan/add_planner.pl"

    async def add_to_planner(self, semester: Semester, reg_id: str):
        page = await self.get_page(
            semester,
            params={"SelectIt": reg_id},
        )
        if (
            "You requested a registration option not available for the semester."
            in page
        ):
            return False
        return True
