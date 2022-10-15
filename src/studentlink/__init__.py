import aiohttp
import logging
import html
import re
from yarl import URL


class StudentLink:
    def __init__(
        self, session: aiohttp.ClientSession = None, logger: logging.Logger = None
    ):
        self.session = session or aiohttp.ClientSession()
        self.logger = logger or logging.getLogger(__name__)

    async def __aenter__(self):
        await self.session.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self.session.__aexit__(*args)
        self.session = None

    @staticmethod
    def mod_url(module: str):
        return URL("https://www.bu.edu/link/bin/uiscgi_studentlink.pl").with_query(
            ModuleName=module
        )


class StudentLinkAuth(StudentLink):
    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession = None,
        logger: logging.Logger = None,
    ):
        super().__init__(session, logger)
        self.username = username
        self.password = password

    async def __aenter__(self):
        await super().__aenter__()
        r1 = await self.session.get(StudentLink.mod_url("allsched.pl"))
        execution = r1.url.query["execution"]
        self.logger.info("logging in")
        r2 = await self.session.post(
            URL("https://shib.bu.edu/idp/profile/SAML2/Redirect/SSO").with_query(
                execution=execution
            ),
            data={
                "j_username": self.username,
                "j_password": self.password,
                "_eventId_proceed": "",
            },
        )
        tx, app = re.findall(r"'sig_request': '(TX.+?):(APP.+?)'", await r2.text())[0]
        # r3 = await self.session.post(
        #     f"https://api-c6b0c057.duosecurity.com/frame/web/v1/auth?tx={tx}&parent=https://shib.bu.edu/idp/profile/SAML2/Redirect/SSO?execution={execution}"
        # )
        r3 = await self.session.post(
            URL("https://api-c6b0c057.duosecurity.com/frame/web/v1/auth").with_query(
                tx=tx,
                parent=str(
                    URL(
                        "https://shib.bu.edu/idp/profile/SAML2/Redirect/SSO"
                    ).with_query(execution=execution)
                ),
            )
        )
        sid = r3.url.query["sid"]
        logging.info("sending duo push")
        r4 = await self.session.post(
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
        r5 = await self.session.post(
            f"https://api-c6b0c057.duosecurity.com/frame/status",
            data={"sid": sid, "txid": txid},
        )
        r6 = await self.session.post(
            f"https://api-c6b0c057.duosecurity.com/frame/status",
            data={"sid": sid, "txid": txid},
        )
        result_url = (await r6.json())["response"]["result_url"]
        r7 = await self.session.post(
            f"https://api-c6b0c057.duosecurity.com{result_url}", data={"sid": sid}
        )
        parent = (await r7.json())["response"]["parent"][:-1] + "2"
        duo_sig = (await r7.json())["response"]["cookie"]
        r8 = await self.session.post(
            parent,
            data={"_eventId": "proceed", "signedDuoResponse": f"{duo_sig}:{app}"},
        )
        (_, relay_state), (_, SAMLResponse) = re.findall(
            r'input type="hidden" name="(.+?)" value="(.+?)"', await r8.text()
        )
        r9 = await self.session.post(
            "https://linklogin.bu.edu/Shibboleth.sso/SAML2/POST",
            data={
                "RelayState": html.unescape(relay_state),
                "SAMLResponse": html.unescape(SAMLResponse),
            },
        )
        logging.info("logged in")
        return self

    async def get_cur_schedule(self):
        r = await self.session.get(StudentLink.mod_url("allsched.pl"))
        return await r.text()
