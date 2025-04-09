from tls_client import Session
from requests import get
from time import sleep

from modules.config import LAYERZERO_CHAINS
from modules.retry import retry, have_json, CustomError
from modules.database import DataBase
from modules.utils import logger
import settings


class Browser:
    def __init__(self, db: DataBase, encoded_pk: str, proxy: str):
        self.max_retries = 5
        self.db = db
        self.encoded_pk = encoded_pk

        if proxy == "mobile":
            if settings.PROXY not in ['https://log:pass@ip:port', 'http://log:pass@ip:port', 'log:pass@ip:port', '', None]:
                self.proxy = settings.PROXY
            else:
                self.proxy = None
        else:
            if proxy not in ['https://log:pass@ip:port', 'http://log:pass@ip:port', 'log:pass@ip:port', '', None]:
                self.proxy = "http://" + proxy.removeprefix("https://").removeprefix("http://")
                logger.debug(f'[•] Soft | Got proxy {self.proxy}')
            else:
                self.proxy = None

        if self.proxy:
            if proxy == "mobile": self.change_ip()
        else:
            logger.warning(f'[-] Soft | You dont use proxies!')

        self.session = self.get_new_session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        })
        self.address = None


    def get_new_session(self):
        session = Session(
            client_identifier="safari_16_0",
            random_tls_extension_order=True
        )

        if self.proxy:
            session.proxies.update({'http': self.proxy, 'https': self.proxy})

        return session


    @have_json
    def send_request(self, **kwargs):
        if kwargs.get("method"): kwargs["method"] = kwargs["method"].upper()
        return self.session.execute_request(**kwargs)


    def change_ip(self):
        if settings.CHANGE_IP_LINK not in ['https://changeip.mobileproxy.space/?proxy_key=...&format=json', '']:
            print('')
            while True:
                try:
                    r = get(settings.CHANGE_IP_LINK)
                    if 'mobileproxy' in settings.CHANGE_IP_LINK and r.json().get('status') == 'OK':
                        logger.debug(f'[+] Proxy | Successfully changed ip: {r.json()["new_ip"]}')
                        return True
                    elif not 'mobileproxy' in settings.CHANGE_IP_LINK and r.status_code == 200:
                        logger.debug(f'[+] Proxy | Successfully changed ip: {r.text}')
                        return True
                    logger.error(f'[-] Proxy | Change IP error: {r.text} | {r.status_code}')
                    sleep(10)

                except Exception as err:
                    logger.error(f'[-] Browser | Cannot get proxy: {err}')

    @retry(source="Browser", module_str="Get Stargate Bus Queue", exceptions=Exception)
    def get_bus_queue(self, from_chain: str, to_chain: str):
        headers = {
            "Origin": "https://stargate.finance",
            "Referer": "https://stargate.finance/"
        }
        r = self.send_request(
            method="GET",
            url=f'https://mainnet.stargate-api.com/v1/buses/queue/{LAYERZERO_CHAINS[from_chain]["id"]}/{LAYERZERO_CHAINS[to_chain]["id"]}',
            headers=headers
        )
        return {
           "capacity": r.json()["queue"]["currentBusParams"]["capacity"],
           "passengers": len(r.json()["queue"]["passengers"]),
        }

    @retry(source="Browser", module_str="Get Jumper Routes", exceptions=Exception)
    def get_jumper_routes(self, from_chain_id: int, to_chain_id: int, value: int):
        headers = {
            "Origin": "https://jumper.exchange",
            "Referer": "https://jumper.exchange/",
            "X-Lifi-Integrator": "jumper.exchange",
            "X-Lifi-Sdk": "3.5.4",
            "X-Lifi-Widget": "3.17.1",
        }
        payload = {
            "fromAddress": self.address,
            "fromAmount": str(value),
            "fromChainId": from_chain_id,
            "fromTokenAddress": "0x0000000000000000000000000000000000000000",
            "toChainId": to_chain_id,
            "toTokenAddress": "0x0000000000000000000000000000000000000000",
            "options": {
                "integrator": "jumper.exchange",
                "order": "CHEAPEST",
                "maxPriceImpact": 0.4,
                "allowSwitchChain": True
            }
        }
        r = self.send_request(
            method="POST",
            url='https://api.jumper.exchange/p/lifi/advanced/routes',
            json=payload,
            headers=headers
        )
        return r.json()["routes"]

    @retry(source="Browser", module_str="Get Jumper Routes", exceptions=Exception)
    def get_jumper_tx(self, swap_step: dict):
        headers = {
            "Origin": "https://jumper.exchange",
            "Referer": "https://jumper.exchange/",
            "X-Lifi-Integrator": "jumper.exchange",
            "X-Lifi-Sdk": "3.5.4",
            "X-Lifi-Widget": "3.17.1",
        }
        r = self.send_request(
            method="POST",
            url='https://api.jumper.exchange/p/lifi/advanced/stepTransaction',
            json=swap_step,
            headers=headers
        )
        return {
            **r.json()["transactionRequest"],
            "out_value": int(r.json()["estimate"]["toAmountMin"]),
        }


    @retry(source="Browser", module_str="Get Uniswap quote", exceptions=Exception)
    def get_uniswap_quote(
            self,
            input_address: str,
            output_address: str,
            value: int,
            chain_id: int,
            tried: int = 0
    ):
        payload = {
            "amount": str(value),
            "gasStrategies": [{
                "limitInflationFactor": 1.15, "displayLimitInflationFactor": 1.15, "priceInflationFactor": 1.5,
                "percentileThresholdFor1559Fee": 75, "minPriorityFeeGwei": 2, "maxPriorityFeeGwei": 9
            }],
            "swapper": self.address,
            "tokenIn": input_address,
            "tokenInChainId": chain_id,
            "tokenOut": output_address,
            "tokenOutChainId": chain_id,
            "type": "EXACT_INPUT",
            "urgency": "normal",
            "protocols": ["V4", "V3", "V2"],
            "slippageTolerance": 2.5
        }

        r = self.send_request(
            method="POST",
            url="https://trading-api-labs.interface.gateway.uniswap.org/v1/quote",
            json=payload,
            headers={
                "Origin": "https://app.uniswap.org",
                "Referer": "https://app.uniswap.org/",
                "X-Request-Source": "uniswap-web",
                "X-Universal-Router-Version": "2.0",
                "X-Api-Key": "JoyCGj29tT4pymvhaGciK4r1aIPvqW6W53xT1fwo"
            }
        )

        if r.json().get('quote'):
            return r.json()

        elif r.json().get("errorCode") == "ResourceNotFound" and r.json().get("detail"):
            if tried > 6:
                raise CustomError('Uniswap dont found routes for long time')
            logger.warning(f'[-] Uniswap | Error "{r.json()["detail"]}". Trying again in 5 seconds')
            sleep(5)
            return self.get_uniswap_quote(input_address, output_address, value, chain_id, tried+1)

        raise Exception(f'Unexpected response: {r.json()}')


    @retry(source="Browser", module_str="Get Uniswap get swap tx", exceptions=Exception)
    def get_uniswap_swap_tx(self, swap_quote: dict, permit_headers: dict):
        payload = {
            "quote": swap_quote,
            "simulateTransaction": True,
            "refreshGasPrice": True,
            "gasStrategies": [{
                "limitInflationFactor": 1.15, "displayLimitInflationFactor": 1.15, "priceInflationFactor": 1.5,
                "percentileThresholdFor1559Fee": 75, "minPriorityFeeGwei": 2, "maxPriorityFeeGwei": 9
            }],
            "urgency": "normal",
            **permit_headers
        }
        r = self.send_request(
            method="POST",
            url="https://trading-api-labs.interface.gateway.uniswap.org/v1/swap",
            json=payload,
            headers={
                "Origin": "https://app.uniswap.org",
                "Referer": "https://app.uniswap.org/",
                "X-Request-Source": "uniswap-web",
                "X-Universal-Router-Version": "2.0",
                "X-Api-Key": "JoyCGj29tT4pymvhaGciK4r1aIPvqW6W53xT1fwo"
            }
        )

        if r.json().get('swap'):
            return r.json()["swap"]

        elif r.json().get("errorCode") == "ResourceNotFound" and r.json().get("detail"):
            return {"soft_error": True, "reason": r.json()["detail"]}

        raise Exception(f'Unexpected response: {r.json()}')


    def odos_get_contract(self, chain_id: int, retry=0):
        try:
            r = self.send_request(
                method="GET",
                url=f'https://api.odos.xyz/info/contract-info/v2/{chain_id}',
                headers={
                "Origin": "https://app.odos.xyz",
                "Referer": "https://app.odos.xyz/",
            }
            )
            if r.json().get('message') == "Geolocation Block":
                raise Exception('Geolocation block')
            return r.json()["routerAddress"]

        except Exception as err:
            if "!DOCTYPE HTML" in str(err): err = "work only with proxy"
            if retry < settings.RETRY and not str(err) != "work only with proxy":
                logger.error(f"[-] Browser | Coudlnt get odos contract: {err} [{retry + 1}/{settings.RETRY}]")
                sleep(10)
                return self.odos_get_contract(chain_id=chain_id, retry=retry+1)
            else:
                raise Exception(f"Coudlnt get odos contract: {err}")


    @retry(source="Browser", module_str="Get Odos quote", exceptions=Exception)
    def odos_quote(
            self,
            from_token_address: str,
            to_token_address: str,
            to_token_decimals: int,
            value: int,
            chain_id: int,
    ):
        payload = {
            "chainId": chain_id,
            "compact": True,
            "disableRFQs": False,
            "likeAsset": True,
            "inputTokens": [{
                    "tokenAddress": from_token_address,
                    "amount": str(value)
            }],
            "outputTokens": [{
                    "tokenAddress": to_token_address,
                    "proportion": 1
            }],
            "pathViz": False,
            "referralCode": 1,
            "slippageLimitPercent": 5,
            "sourceBlacklist": [],
            "userAddr": self.address,
        }
        r = self.send_request(
            method="POST",
            url='https://api.odos.xyz/sor/quote/v2',
            json=payload,
            headers={
            "Origin": "https://app.odos.xyz",
            "Referer": "https://app.odos.xyz/"
            }
        )
        if r.status_code != 200: raise ValueError(f'sor: {r.json()}')

        return {
            "path_id": r.json()['pathId'],
            "amount_out": int(r.json()["outAmounts"][0]) / 10 ** to_token_decimals,
            "usd_out": r.json()["outValues"][0],
        }

    @retry(source="Browser", module_str="Odos assemble", exceptions=Exception)
    def odos_assemble(self, path_id: str):
        payload = {
            "userAddr": self.address,
            "pathId": path_id,
            "simulate": True
        }
        r = self.send_request(
            method="POST",
            url='https://api.odos.xyz/sor/assemble',
            json=payload,
            headers={
                "Origin": "https://app.odos.xyz",
                "Referer": "https://app.odos.xyz/"
            }
        )

        if r.json().get("simulation") is None:
            raise Exception(f'bad assemble response {r.json()}')

        elif r.json()['simulation']['isSuccess'] != True:
            if r.json()['simulation']['simulationError']['type'] == "other":
                text_error = r.json()["simulation"]["simulationError"]["errorMessage"]
            else:
                text_error = r.json()["simulation"]["simulationError"]

            raise Exception(f'simulation failed {text_error}')

        return {
            "data": r.json()['transaction']['data'],
            "to": r.json()['transaction']['to'],
        }
