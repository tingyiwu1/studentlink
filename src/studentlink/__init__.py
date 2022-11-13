from __future__ import annotations
from typing import Callable, TypeVar
import aiohttp
import logging
import html
import re
from yarl import URL

from .modules._module import Module, PublicModule

M = TypeVar("M", bound=Module)
PM = TypeVar("PM", bound=PublicModule)

class StudentLink:
    def __init__(
        self, session: aiohttp.ClientSession = None, logger: logging.Logger = None
    ):
        self.session = session or aiohttp.ClientSession()
        self.logger = logger or logging.getLogger(__name__)
        self.modules: dict[type, Module] = {}

    async def __aenter__(self):
        await self.session.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self.session.__aexit__(*args)
        self.session = None

    def module(self, module: Callable[[], PM]) -> PM:
        if not issubclass(module, PublicModule):
            raise TypeError(
                f"{module} requires authentication; use StudentLinkAuth instead"
            )
        if module not in self.modules:
            self.modules[module] = module(self)
        return self.modules[module]

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
        r1 = await self.session.get(Module.mod_url("allsched.pl"))
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
                "device": "phone1",  # TODO: make this more robust
                "factor": "Duo Push",
                "dampen_choice": "true",
                "out_of_date": "",
                "days_out_of_date": "",
                "days_to_block": "None",
            },
        )
        txid = (await r4.json())["response"]["txid"]
        await self.session.post(
            "https://api-c6b0c057.duosecurity.com/frame/status",
            data={"sid": sid, "txid": txid},
        )
        r6 = await self.session.post(
            "https://api-c6b0c057.duosecurity.com/frame/status",
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
        await self.session.post(
            "https://linklogin.bu.edu/Shibboleth.sso/SAML2/POST",
            data={
                "RelayState": html.unescape(relay_state),
                "SAMLResponse": html.unescape(SAMLResponse),
            },
        )
        logging.info("logged in")
        return self

    def module(self, module: Callable[..., M]) -> M:
        if module not in self.modules:
            self.modules[module] = module(self)
        return self.modules[module]


# f5_cspm=1234
# f5avraaaaaaaaaaaaaaaa_session_=MHHIJFHAKDFEFLBHPHGJPLJAGIFALCLLCPBFMLOEGDKDEGEJBCHKJDAIAFLNBAFMMACDINODIGGGAANCOGKALCHCOCFAKPGHIOGEJFIPIDCNJHLFAILKMMCMBOKCOPPM
# f5_cspm=1234
# apt.uid=AP-PQQY5YJEHTTA-2-1665715175793-61755484.0.2.7b898736-1246-467f-8f47-980d7da7bb53
# uiscgi_prod=4448694e9ea88bbf9c349d45e392080f:prod
# BIGipServerist-uiscgi-app-prod-443-pool=1237697920.47873.0000
# BIGipServerist-uiscgi-content-prod-443-pool=2332485386.47873.0000
# _ga=GA1.1.945435981.1665715180
# _ga_L4SD8HKLDR=GS1.1.1668186144.5.0.1668186144.0.0.0
# BIGipServerist-uiscgi-app-prod-80-pool=1254475136.20480.0000
# BIGipServerist-web-legacy-prod-80-pool=1662710026.31745.0000
# BIGipServerist-wp-app-prod-443-pool=1860301066.47873.0000
# BIGipServerist-wp-app-prod-80-pool=1843523850.20480.0000
# BIGipServerist-web-phpbin-aws-prod-443-pool=1529494026.47873.0000
# BIGipServerwww-prod-crc-443-pool=893985549.47873.0000
# BIGipServerwww-prod-crc-80-pool=893985549.20480.0000
# BIGipServerist-web-legacy-prod-443-pool=1662710026.31745.0000
# AWSALB=3YyfEn1jbxLfI5v5e3v7XVHvay4E0b7hjzVyqJ8KenMP/YNH0qL+4MT4XZkpEMmQjBi1F0u4RAatvPLGdHnwRlkUPExhYyl+PeOQJcoKTdy/jBlzwySQoP7gyQuj
# AWSALBCORS=3YyfEn1jbxLfI5v5e3v7XVHvay4E0b7hjzVyqJ8KenMP/YNH0qL+4MT4XZkpEMmQjBi1F0u4RAatvPLGdHnwRlkUPExhYyl+PeOQJcoKTdy/jBlzwySQoP7gyQuj