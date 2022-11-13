import asyncio
import aiohttp
import re
import html
from dotenv import load_dotenv
import os
import studentlink
from studentlink.modules.allsched import AllSched
from studentlink.modules.regsched import RegSched
from studentlink.modules.browse_schedule import BrowseSchedule
from studentlink.modules.add_planner import AddPlanner
from studentlink.util import Semester
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)

USERNAME, PASSWORD = os.environ["USERNAME"], os.environ["PASSWORD"]


async def main():
    async with studentlink.StudentLinkAuth(USERNAME, PASSWORD) as sl:
        mod = sl.module(AddPlanner)
        while True:
            s = await mod.add_to_planner(Semester.SPRING, 2023, "0001129029")
            print(s)
            break
        # mod2 = sl.module(BrowseSchedule)
        # s2 = await mod2.search_class(Semester.SPRING, 2023, "CAS", "PO", 396)
        # print(s2)


async def mainn():
    async with aiohttp.ClientSession() as session:
        r1 = await session.get(
            "https://www.bu.edu/link/bin/uiscgi_studentlink.pl/1665505032?ModuleName=allsched.pl"
        )
        execution = r1.url.query["execution"]
        r2 = await session.post(
            f"https://shib.bu.edu/idp/profile/SAML2/Redirect/SSO?execution={execution}",
            data={
                "j_username": USERNAME,
                "j_password": PASSWORD,
                "_eventId_proceed": "",
            },
        )
        tx, app = re.findall(r"'sig_request': '(TX.+?):(APP.+?)'", await r2.text())[0]
        r3 = await session.post(
            f"https://api-c6b0c057.duosecurity.com/frame/web/v1/auth?tx={tx}&parent=https://shib.bu.edu/idp/profile/SAML2/Redirect/SSO?execution={execution}"
        )
        sid = r3.url.query["sid"]
        r4 = await session.post(
            "https://api-c6b0c057.duosecurity.com/frame/prompt",
            data={
                "sid": sid,
                "device": "phone1",
                "factor": "Duo Push",
                "out_of_date": "",
                "days_out_of_date": "",
                "days_to_block": "None",
            },
        )
        txid = (await r4.json())["response"]["txid"]
        r5 = await session.post(
            f"https://api-c6b0c057.duosecurity.com/frame/status",
            data={"sid": sid, "txid": txid},
        )
        r6 = await session.post(
            f"https://api-c6b0c057.duosecurity.com/frame/status",
            data={"sid": sid, "txid": txid},
        )
        result_url = (await r6.json())["response"]["result_url"]
        r7 = await session.post(
            f"https://api-c6b0c057.duosecurity.com{result_url}", data={"sid": sid}
        )
        parent = (await r7.json())["response"]["parent"][:-1] + "2"
        duo_sig = (await r7.json())["response"]["cookie"]
        r8 = await session.post(
            parent,
            data={"_eventId": "proceed", "signedDuoResponse": f"{duo_sig}:{app}"},
        )
        (_, relay_state), (_, SAMLResponse) = re.findall(
            r'input type="hidden" name="(.+?)" value="(.+?)"', await r8.text()
        )
        r9 = await session.post(
            "https://linklogin.bu.edu/Shibboleth.sso/SAML2/POST",
            data={
                "RelayState": html.unescape(relay_state),
                "SAMLResponse": html.unescape(SAMLResponse),
            },
        )
        print(await r9.text())
        print(r9.url)


if __name__ == "__main__":
    asyncio.run(main())
