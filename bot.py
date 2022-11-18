import asyncio
from dotenv import load_dotenv
import logging
import os
import contextlib
from io import StringIO
import json
import sys

from aiohttp import ClientSession, CookieJar

from studentlink import StudentLinkAuth, LoginError
from studentlink.util import Semester, Abbr
from studentlink.data.class_ import ClassView
from studentlink.modules.browse_schedule import BrowseSchedule
from studentlink.modules.reg import ConfirmClasses, Drop, ConfirmDrop

load_dotenv()

fh = logging.FileHandler("bot.log", mode="a")
formatter = logging.Formatter(
    "%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s"
)
fh.setFormatter(formatter)
fh.setLevel(logging.WARNING)

sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
sh.setLevel(logging.INFO)

sh2 = logging.StreamHandler(sys.stderr)
sh2.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
sh2.setLevel(logging.ERROR)

logging.basicConfig(handlers=[fh, sh, sh2], level=logging.DEBUG)

USERNAME, PASSWORD, DISC_URL = (
    os.environ["USERNAME"],
    os.environ["PASSWORD"],
    os.environ["DISC_URL"],
)

SEMESTER = Semester.from_str("Spring 2023")


class CannotReplace(Exception):
    pass


class RegisterFail(Exception):
    pass


class CriticalError(Exception):
    pass


async def get_class_reg(sl: StudentLinkAuth, abbr: Abbr):
    res = await sl.module(BrowseSchedule).search_class(SEMESTER, *abbr)
    for cv in res:
        if abbr == cv.abbr:
            return cv


async def get_class_drop(sl: StudentLinkAuth, abbr: Abbr):
    res = await sl.module(Drop).get_drop_list(SEMESTER)
    for cv in res:
        if abbr == cv.abbr:
            return cv


async def attempt_register(
    sl: StudentLinkAuth, abbr: Abbr, logger: logging.Logger = logging.getLogger()
):
    cv = await get_class_reg(sl, abbr)
    if cv is not None and cv.reg_id:
        async with disc_log(sl.session, abbr) as logger:
            logger.info(f"Can register for {cv.abbr}")
            res = await sl.module(ConfirmClasses).confirm_class(SEMESTER, cv.reg_id)
            if res[cv.abbr][0]:
                logger.info(f"Successfully registered for {cv.abbr}")
            else:
                logger.info(f"Failed to register for {cv.abbr}: {res[cv.abbr][1]}")
                raise RegisterFail(f"Failed to register for {cv.abbr}: {res[cv.abbr][1]}")
    else:
        logger.info(f"Cannot register for {abbr}")


async def attempt_replace(
    sl: StudentLinkAuth,
    *,
    add: Abbr,
    replace: Abbr,
    logger: logging.Logger = logging.getLogger(),
):
    logger.info(f"Attempting to replace {replace} with {add}")
    cv1 = await get_class_reg(sl, add)
    if cv1 is not None and cv1.reg_id:
        async with disc_log(sl.session, add) as logger:
            logger.info(f"Can register for {cv1.abbr}")
            try:
                async with replace_class(sl, replace, logger) as cv2:
                    logger.info(f"Replacing {cv2.abbr} with {cv1.abbr}")
                    res = await sl.module(ConfirmClasses).confirm_class(
                        SEMESTER, cv1.reg_id
                    )
                    if res[cv1.abbr][0]:
                        logger.info(f"Successfully registered for {cv1.abbr}")
                    else:
                        logger.info(
                            f"Failed to register for {cv1.abbr}: {res[cv1.abbr][1]}"
                        )
                        raise RegisterFail(f"Failed to register for {cv1.abbr}: {res[cv1.abbr][1]}")
            except CannotReplace as e:
                logger.warning(e)
    else:
        logger.info(f"Cannot register for {add}")


@contextlib.asynccontextmanager
async def disc_log(session: ClientSession, name: str):
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    logger = logging.getLogger(name)
    logger.addHandler(handler)
    try:
        yield logger
    finally:
        await session.post(
            DISC_URL, data={"content": stream.getvalue(), "username": name}
        )
        logger.removeHandler(handler)


@contextlib.asynccontextmanager
async def replace_class(
    sl: StudentLinkAuth, abbr: Abbr, logger: logging.Logger = logging.getLogger()
):
    """context manager to drop a class to make room for another."""
    cv_r, cv_d = await asyncio.gather(get_class_reg(sl, abbr), get_class_drop(sl, abbr))
    if cv_d is None or not cv_d.drop_id:
        raise CannotReplace(f"Cannot drop {abbr}")
    if cv_r is None or not cv_r.reg_id:
        raise CannotReplace(
            f"Cannot register for {abbr}. Try manually dropping if you want to risk it."
        )
    try:
        res = await sl.module(ConfirmDrop).confirm_drop(SEMESTER, cv_d.drop_id)
        if res[cv_d.abbr][0]:
            logger.info(f"Successfully dropped {cv_d.abbr}")
            yield cv_d
        else:
            raise CannotReplace(f"Failed to drop {cv_d.abbr}: {res[cv_d.abbr][1]}")
    except Exception as e:  # replace class back if something goes wrong
        logger.warning(f"Something went wrong, re-registering {cv_d.abbr}\n{e}")
        try:
            res = await sl.module(ConfirmClasses).confirm_class(SEMESTER, cv_r.reg_id)
        except Exception as e:
            raise CriticalError(f"Failed to re-register {cv_d.abbr}\n{e}")
        if res[cv_r.abbr][0]:
            logger.info(f"Successfully re-registered for {cv_r.abbr}")
        else:
            logger.info(f"Failed to re-register for {cv_r.abbr}: {res[cv_r.abbr][1]}")
            raise CriticalError(
                f"Failed to re-register for {cv_r.abbr}: {res[cv_r.abbr][1]}"
            )
    finally:
        pass


@contextlib.asynccontextmanager
async def shift_section(
    sl: StudentLinkAuth,
    *,
    add: Abbr,
    logger: logging.Logger = logging.getLogger(),
):
    pass


async def test_replace(sl: StudentLinkAuth, abbr: Abbr):
    try:
        async with replace_class(sl, abbr) as cv:
            logging.info(f"sleeping")
            await asyncio.sleep(5)
            logging.info(f"done sleeping")
    except CannotReplace as e:
        logging.warning(e)


async def refresh_spec(
    sl: StudentLinkAuth,
    old_spec: list[dict[str, str]],
    logger: logging.Logger = logging.getLogger(),
):
    with open("spec.json", "r") as f:
        spec: list[dict[str, str]] = json.load(f)
        if spec == old_spec:
            return old_spec

        res = await sl.module(Drop).get_drop_list(SEMESTER)
        can_drop = [cv.abbr for cv in res]
        if cannot_drop := [
            s["replace"]
            for s in spec
            if "replace" in s and s["replace"] not in can_drop
        ]:
            logger.warning(f"These can't be dropped: {cannot_drop}")
            return old_spec

        reg_cvs = await asyncio.gather(
            *(get_class_reg(sl, Abbr(s["add"])) for s in spec)
        )
        if not_found := [s["add"] for s, cv in zip(spec, reg_cvs) if cv is None]:
            logger.warning(f"These aren't found: {not_found}")
            return old_spec

        return spec


async def poll():
    cookie_jar = CookieJar()
    try:
        cookie_jar.load("cookies.pickle")
    except FileNotFoundError:
        pass
    session = ClientSession(cookie_jar=cookie_jar)
    logger = logging.getLogger()
    try:
        async with StudentLinkAuth(
            USERNAME,
            PASSWORD,
            session=session,
            logger=logger,
        ) as sl:
            spec = await refresh_spec(sl, [])
            async with disc_log(session, "Start") as logger:
                logger.info("Successfully logged in, starting...")
            while True:
                spec = await refresh_spec(sl, spec)
                schedule = [
                    cv.abbr for cv in await sl.module(Drop).get_drop_list(SEMESTER)
                ]
                tasks = [
                    attempt_replace(sl, add=Abbr(s["add"]), replace=Abbr(s["replace"]))
                    if "replace" in s
                    else attempt_register(sl, Abbr(s["add"]))
                    for s in spec
                    if s.get("add") not in schedule
                ]
                try:
                    await asyncio.gather(*tasks)
                except AttributeError as e:
                    logger.info(e)
                except RegisterFail as e:
                    async with disc_log(session, "Register Fail") as logger:
                        logger.warning(e)
                except CriticalError as e:
                    async with disc_log(session, "Critical Error") as logger:
                        logger.critical(e)
                await asyncio.sleep(5)
    except LoginError as e:
        async with disc_log(session, "Login Error") as logger:
            logger.error(e)
    except Exception as e:
        logger.error(e)
    finally:
        async with disc_log(session, "Stopped") as logger:
            logger.info("Stopped")
        cookie_jar.save("cookies.pickle")
        await session.close()


if __name__ == "__main__":
    asyncio.run(poll())
