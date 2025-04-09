from eth_account.messages import (
    encode_defunct,
    encode_typed_data,
    _hash_eip191_message
)
from web3.middleware import geth_poa_middleware
from random import choice, uniform, randint
from ccxt import binance, bybit, bitget
from datetime import datetime, timezone
from typing import Union, Optional
from requests import get, post
from time import sleep, time
from base64 import b64encode
from decimal import Decimal
from web3 import Web3
import hmac

from modules.utils import logger, sleeping
from modules.database import DataBase
import modules.config as config
import settings

from requests.exceptions import HTTPError
from web3.exceptions import ContractLogicError, BadFunctionCallOutput


class Wallet:
    def __init__(
            self,
            privatekey: str,
            encoded_pk: str,
            db: DataBase,
            browser=None,
            recipient: str = None,
    ):
        self.privatekey = privatekey
        self.encoded_pk = encoded_pk

        self.account = Web3().eth.account.from_key(privatekey)
        self.address = self.account.address
        self.recipient = Web3().to_checksum_address(recipient) if recipient else None
        self.browser = browser
        self.db = db


    def get_web3(self, chain_name: str):
        web3 = Web3(Web3.HTTPProvider(settings.RPCS[chain_name]))
        web3.middleware_onion.inject(geth_poa_middleware, layer=0)
        return web3


    def wait_for_gwei(self):
        for chain_data in [
            {'chain_name': 'ethereum', 'max_gwei': settings.ETH_MAX_GWEI},
        ]:
            first_check = True
            while True:
                try:
                    new_gwei = round(self.get_web3(chain_name=chain_data['chain_name']).eth.gas_price / 10 ** 9, 2)
                    if new_gwei < chain_data["max_gwei"]:
                        if not first_check: logger.debug(f'[•] Web3 | New {chain_data["chain_name"].title()} GWEI is {new_gwei}')
                        break
                    sleep(5)
                    if first_check:
                        first_check = False
                        logger.debug(f'[•] Web3 | Waiting for GWEI in {chain_data["chain_name"].title()} at least {chain_data["max_gwei"]}. Now it is {new_gwei}')
                except Exception as err:
                    logger.warning(f'[•] Web3 | {chain_data["chain_name"].title()} gwei waiting error: {err}')
                    sleeping(10)


    def get_gas(self, chain_name, increasing_gwei: float = 0):
        web3 = self.get_web3(chain_name=chain_name)
        max_priority = int(web3.eth.max_priority_fee)
        last_block = web3.eth.get_block('latest')
        if chain_name == 'scroll':
            base_fee = max(
                web3.eth.gas_price,
                int(web3.eth.fee_history(1, 'latest')["baseFeePerGas"][1])
            ) * (settings.GWEI_MULTIPLIER + increasing_gwei)
        else:
            base_fee = int(max(last_block['baseFeePerGas'], web3.eth.gas_price) * (settings.GWEI_MULTIPLIER + increasing_gwei))
        block_filled = last_block['gasUsed'] / last_block['gasLimit'] * 100
        if block_filled > 50: base_fee = int(base_fee * 1.127)

        max_fee = int(base_fee + max_priority)
        return {'maxPriorityFeePerGas': max_priority, 'maxFeePerGas': max_fee}


    def sent_tx(self, chain_name: str, tx, tx_label, tx_raw=False, value=0, increasing_gwei: float = 0):
        try:
            web3 = self.get_web3(chain_name=chain_name)
            if not tx_raw:
                tx_completed = tx.build_transaction({
                    'from': self.address,
                    'chainId': web3.eth.chain_id,
                    'nonce': web3.eth.get_transaction_count(self.address),
                    'value': value,
                    **self.get_gas(chain_name=chain_name, increasing_gwei=increasing_gwei),
                })
            else:
                tx_completed = {
                    **tx,
                    **self.get_gas(chain_name=chain_name, increasing_gwei=increasing_gwei),
                }
                tx_completed["gas"] = web3.eth.estimate_gas(tx_completed)

            signed_tx = web3.eth.account.sign_transaction(tx_completed, self.privatekey)

            raw_tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash = web3.to_hex(raw_tx_hash)
            return self.wait_for_tx(
                chain_name=chain_name,
                tx_hash=tx_hash,
                tx_label=tx_label
            )

        except Exception as err:
            if 'already known' in str(err):
                try: raw_tx_hash
                except: raw_tx_hash = ''
                logger.warning(f'{tx_label} | Couldnt get tx hash, thinking tx is success ({raw_tx_hash})')
                sleeping(15)
                return tx_hash

            elif (
                    "replacement transaction underpriced" in str(err) or
                    "not in the chain after" in str(err) or
                    "max fee per gas less than block base fee" in str(err)
                ):
                new_multiplier = round((increasing_gwei + 0.05 + settings.GWEI_MULTIPLIER - 1) * 100)
                logger.warning(f'[-] Web3 | {tx_label} | couldnt send tx, increasing gwei to {new_multiplier}%')
                return self.sent_tx(
                    chain_name=chain_name,
                    tx=tx,
                    tx_label=tx_label,
                    tx_raw=tx_raw,
                    value=value,
                    increasing_gwei=increasing_gwei+0.05
                )

            elif "gas required exceeds allowance" in str(err):
                logger.warning(f'[-] Web3 | {chain_name.title()} RPC error, trying again...')
                sleep(5)
                return self.sent_tx(
                    chain_name=chain_name,
                    tx=tx,
                    tx_label=tx_label,
                    tx_raw=tx_raw,
                    value=value,
                    increasing_gwei=increasing_gwei
                )

            try: encoded_tx = f'\nencoded tx: {tx_completed._encode_transaction_data()}'
            except: encoded_tx = ''
            raise ValueError(f'tx failed error: {err}{encoded_tx}')


    def wait_for_tx(self, chain_name: str, tx_hash: str, tx_label: str):
        tx_link = f'{config.CHAINS_DATA[chain_name]["explorer"]}{tx_hash}'
        logger.debug(f'[•] Web3 | {tx_label} tx sent: {tx_link}')

        web3 = self.get_web3(chain_name)
        first_try = True
        while True:
            try:
                status = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=int(settings.TO_WAIT_TX * 60)).status
                break
            except HTTPError as err:
                if first_try:
                    first_try = False
                    sleep(5)
                else:
                    logger.error(f'[-] Web3 | Coudlnt get TX, probably you need to change RPC: {err}')
                    sleeping(5)

        if status == 1:
            logger.info(f'[+] Web3 | {tx_label} tx confirmed\n')
            self.db.append_report(privatekey=self.encoded_pk, text=tx_label, success=True)
            return tx_hash
        else:
            self.db.append_report(
                privatekey=self.encoded_pk,
                text=f'{tx_label} | tx is failed | <a href="{tx_link}">link 👈</a>', success=False
            )
            raise ValueError(f'tx failed: {tx_link}')

    def approve(
            self,
            chain_name: str,
            token_address: str,
            spender: str,
            amount: float = None,
            value: int = None,
            decimals: int = 18,
    ):
        web3 = self.get_web3(chain_name)
        contract = web3.eth.contract(
            address=web3.to_checksum_address(token_address),
            abi='[{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"}]',
        )
        token_name = contract.functions.symbol().call()

        if amount:
            value = int(amount * 10 ** decimals)
        elif value:
            amount = round(value / 10 ** decimals, 5)

        if value == 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:
            min_allowance = 0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
            amount = "infinity"
        else:
            min_allowance = value

        if contract.functions.allowance(
            self.address,
            spender,
        ).call() < min_allowance:
            module_str = f"approve {amount} {token_name}"
            contract_tx = contract.functions.approve(
                spender,
                value
            )
            self.sent_tx(
                chain_name=chain_name,
                tx=contract_tx,
                tx_label=module_str
            )
            sleeping(settings.SLEEP_AFTER_TX)
            return True
        else:
            return False

    def get_balance(self, chain_name: str, token_name=False, token_address=False, human=False, tokenId=None):
        web3 = self.get_web3(chain_name=chain_name)
        if token_name: token_address = config.TOKEN_ADDRESSES[chain_name][token_name]
        if token_address:
            contract = web3.eth.contract(
                address=web3.to_checksum_address(token_address),
                abi='[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"","type":"address"},{"internalType":"uint256","name":"","type":"uint256"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]'
            )

        while True:
            try:
                if token_address:
                    if tokenId is not None:
                        if type(tokenId) != list:
                            params = [self.address, tokenId]
                        else:
                            param = tokenId[0]
                            if param is None:
                                params = [self.address]
                            else:
                                params = [self.address, param]
                    else:
                        params = [self.address]
                    balance = contract.functions.balanceOf(*params).call()
                else: balance = web3.eth.get_balance(self.address)

                if not human: return balance

                decimals = contract.functions.decimals().call() if token_address else 18
                return balance / 10 ** decimals

            except ContractLogicError:
                if type(tokenId) == list and len(tokenId) != 0:
                    tokenId.pop(0)

                elif tokenId is not None:
                    tokenId = None
                    continue

                if (
                        type(tokenId) == list and len(tokenId) == 0
                        or
                        type(tokenId) is not list
                ):
                    raise

            except BadFunctionCallOutput:
                logger.warning(f'[-] Web3 | Bad address to get balance: {token_address}')
                return None

            except Exception as err:
                logger.warning(f'[•] Web3 | Get {token_address} balance error ({tokenId}): {err}')
                sleep(5)

    def get_token_info(self, chain_name: str, token_name=False, token_address=False):
        web3 = self.get_web3(chain_name=chain_name)
        if token_name and token_name != "ETH": token_address = config.TOKEN_ADDRESSES[chain_name][token_name]
        if token_address:
            token_address = web3.to_checksum_address(token_address)
            contract = web3.eth.contract(
                address=token_address,
                abi='[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"","type":"address"},{"internalType":"uint256","name":"","type":"uint256"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"}]'
            )

        while True:
            try:
                if token_address:
                    balance = contract.functions.balanceOf(self.address).call()
                    decimals = contract.functions.decimals().call()
                    symbol = contract.functions.symbol().call()
                else:
                    balance = web3.eth.get_balance(self.address)
                    decimals = 18
                    symbol = "ETH"
                    token_address = "0x0000000000000000000000000000000000000000"

                return {
                    "value": balance,
                    "amount": balance / 10 ** decimals,
                    "decimals": decimals,
                    "symbol": symbol,
                    "address": token_address,
                }

            except BadFunctionCallOutput:
                logger.warning(f'[-] Web3 | Bad address to get balance: {token_address}')
                return None

            except Exception as err:
                logger.warning(f'[•] Web3 | Get {token_address} balance error: {err}')
                sleep(5)


    def wait_balance(
            self,
            chain_name: str,
            needed_balance: Union[int, float],
            only_more: bool = False,
            token_name: Optional[str] = False,
            token_address: Optional[str] = False,
            human: bool = True,
            timeout: int = 0
    ):
        " needed_balance: human digit "
        if token_name:
            token_address = config.TOKEN_ADDRESSES[chain_name][token_name]

        if token_address:
            contract = self.get_web3(chain_name=chain_name).eth.contract(address=Web3().to_checksum_address(token_address),
                                         abi='[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"}]')
            token_name = contract.functions.name().call()
        else:
            token_name = 'ETH'

        if only_more: logger.debug(f'[•] Web3 | Waiting for balance more than {round(needed_balance, 6)} {token_name} in {chain_name.upper()}')
        else: logger.debug(f'[•] Web3 | Waiting for {round(needed_balance, 6)} {token_name} balance in {chain_name.upper()}')
        start_time = time()

        while True:
            try:
                new_balance = self.get_balance(chain_name=chain_name, human=human, token_address=token_address)

                if only_more: status = new_balance > needed_balance
                else: status = new_balance >= needed_balance
                if status:
                    logger.debug(f'[•] Web3 | New balance: {round(new_balance, 6)} {token_name}\n')
                    return new_balance
                if timeout and time() - start_time > timeout:
                    logger.error(f'[-] Web3 | No token found in {timeout} seconds')
                    return 0
                sleep(5)
            except Exception as err:
                logger.warning(f'[•] Web3 | Wait balance error: {err}')
                sleep(10)



    def okx_withdraw(self, chain: str, amount: float = 0, multiplier=0.6, retry=0):
        def okx_data(api_key, secret_key, passphras, request_path="/api/v5/account/balance?ccy=ETH", body='', meth="GET"):
            base_url = "https://www.okex.com"
            dt_now = datetime.now(timezone.utc)
            ms = str(dt_now.microsecond).zfill(6)[:3]
            timestamp = f"{dt_now:%Y-%m-%dT%H:%M:%S}.{ms}Z"
            mac = hmac.new(
                bytes(secret_key, encoding="utf-8"),
                bytes(timestamp + meth.upper() + request_path + body, encoding="utf-8"),
                digestmod="sha256",
            )
            signature = b64encode(mac.digest()).decode("utf-8")

            headers = {
                "Content-Type": "application/json",
                "OK-ACCESS-KEY": api_key,
                "OK-ACCESS-SIGN": signature,
                "OK-ACCESS-TIMESTAMP": timestamp,
                "OK-ACCESS-PASSPHRASE": passphras,
                'x-simulated-trading': '0'
            }
            return base_url, request_path, headers

        SYMBOL = config.OKX_CHAINS[chain]["token_name"]
        CHAIN = config.OKX_CHAINS[chain]["chain_name"]

        self.wait_for_gwei()

        if amount:
            AMOUNT = amount
        else:
            AMOUNT = round(uniform(*settings.WITHDRAW_PARAMS["withdraw_range"]), randint(4, 7))
        wallet = self.address
        SUB_ACC = True

        old_balance = self.get_balance(chain_name=chain, human=True)

        api_key = settings.OKX_API_KEY
        secret_key = settings.OKX_API_SECRET
        passphras = settings.OKX_API_PASSWORD

        # take FEE for withdraw
        _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/asset/currencies?ccy={SYMBOL}", meth="GET")
        response = get(f"https://www.okx.cab/api/v5/asset/currencies?ccy={SYMBOL}", timeout=10, headers=headers)

        if not response.json().get("data"): raise Exception(f'Bad OKX API keys: {response.json()}')
        raw_fee = None
        for lst in response.json()["data"]:
            if lst['chain'] == f'{SYMBOL}-{CHAIN}':
                raw_fee = float(lst['minFee'])

        if raw_fee is None:
            raise Exception(f'no chain {CHAIN} with symbol {SYMBOL}')

        try:
            while True:
                if SUB_ACC == True:
                    _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/users/subaccount/list", meth="GET")
                    list_sub = get("https://www.okx.cab/api/v5/users/subaccount/list", timeout=10, headers=headers)
                    list_sub = list_sub.json()

                    if not list_sub.get("data"):
                        raise Exception(f'Bad SubAccounts: {list_sub}')
                    for sub_data in list_sub["data"]:
                        while True:
                            name_sub = sub_data['subAcct']

                            _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/asset/subaccount/balances?subAcct={name_sub}&ccy={SYMBOL}", meth="GET")
                            sub_balance = get(f"https://www.okx.cab/api/v5/asset/subaccount/balances?subAcct={name_sub}&ccy={SYMBOL}", timeout=10, headers=headers)
                            sub_balance = sub_balance.json()
                            if sub_balance.get('msg') == f'Sub-account {name_sub} doesn\'t exist':
                                logger.warning(f'[-] OKX | Error: {sub_balance["msg"]}')
                                continue

                            if not sub_balance.get("data"):
                                raise Exception(f'Bad Sub Account Balance: {sub_balance}')
                            sub_balance = sub_balance["data"][0]['bal']

                            logger.info(f'[•] OKX | {name_sub} | {sub_balance} {SYMBOL}')

                            if float(sub_balance) > 0:
                                body = {"ccy": f"{SYMBOL}", "amt": str(sub_balance), "from": 6, "to": 6, "type": "2", "subAcct": name_sub}
                                _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/asset/transfer", body=str(body), meth="POST")
                                a = post("https://www.okx.cab/api/v5/asset/transfer", data=str(body), timeout=10, headers=headers)
                            break

                try:
                    _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/account/balance?ccy={SYMBOL}")
                    balance = get(f'https://www.okx.cab/api/v5/account/balance?ccy={SYMBOL}', timeout=10, headers=headers)
                    balance = balance.json()
                    if not balance.get("data"):
                        raise Exception(f'Bad Trading Account Balance: {balance}')
                    balance = balance["data"][0]["details"][0]["cashBal"]

                    if balance != 0:
                        body = {"ccy": f"{SYMBOL}", "amt": float(balance), "from": 18, "to": 6, "type": "0", "subAcct": "", "clientId": "", "loanTrans": "", "omitPosRisk": ""}
                        _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/asset/transfer", body=str(body), meth="POST")
                        a = post("https://www.okx.cab/api/v5/asset/transfer", data=str(body), timeout=10, headers=headers)
                except Exception as ex:
                    pass

                # CHECK MAIN BALANCE
                _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/asset/balances?ccy={SYMBOL}", meth="GET")
                main_balance = get(f'https://www.okx.cab/api/v5/asset/balances?ccy={SYMBOL}', timeout=10, headers=headers)
                main_balance = main_balance.json()
                if not main_balance.get("data"):
                    raise Exception(f'Bad Main Account Balance: {main_balance}')
                main_balance = float(main_balance["data"][0]['availBal'])
                logger.info(f'[•] OKX | Total balance: {main_balance} {SYMBOL}')

                if AMOUNT > main_balance:
                    logger.warning(f'[•] OKX | Not enough balance ({main_balance} < {AMOUNT}), waiting 10 secs...')
                    sleep(10)
                    continue

                break

            while True:
                body = {"ccy": SYMBOL, "amt": AMOUNT, "fee": round(raw_fee * multiplier, 6), "dest": "4", "chain": f"{SYMBOL}-{CHAIN}", "toAddr": wallet}
                _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/asset/withdrawal", meth="POST", body=str(body))
                a = post("https://www.okx.cab/api/v5/asset/withdrawal", data=str(body), timeout=10, headers=headers)
                result = a.json()

                if result['code'] == '0':
                    logger.success(f"[+] OKX | Success withdraw {AMOUNT} {SYMBOL} in {CHAIN}")
                    self.db.append_report(privatekey=self.encoded_pk, text=f"OKX withdraw {AMOUNT} {SYMBOL} in {CHAIN}",
                                          success=True)
                    new_balance = self.wait_balance(chain_name=chain, needed_balance=old_balance, only_more=True)
                    return chain, new_balance - old_balance
                else:
                    if 'Withdrawal fee is lower than the lower limit' in result['msg'] and multiplier < 1:
                        # logger.warning(f"[-] OKX | Withdraw failed to {wallet} | error : {result['msg']} | New fee multiplier {round((multiplier + 0.05) * 100)}%")
                        multiplier += 0.05
                    else:
                        raise ValueError(result['msg'])

        except Exception as error:
            if retry < settings.RETRY:
                if 'Insufficient balance' in str(error):
                    logger.warning(f"[-] OKX | Withdraw failed to {chain} | error : {error}")
                    sleep(10)
                    return self.okx_withdraw(chain=chain, amount=amount, multiplier=multiplier, retry=retry)
                else:
                    logger.error(f"[-] OKX | Withdraw failed to {chain} | error : {error}")
                    sleep(10)
                    return self.okx_withdraw(chain=chain, amount=amount, multiplier=multiplier, retry=retry + 1)

            else:
                self.db.append_report(privatekey=self.encoded_pk, text=f'OKX withdraw error: {error}', success=False)
                raise Exception(f'OKX withdraw error: {error}')

    def bybit_withdraw(self, chain: str, amount: float = 0, retry=0):
        try:
            self.wait_for_gwei()
            old_balance = self.get_balance(chain_name=chain, human=True)

            CHAIN = config.BYBIT_CHAINS[chain]["chain_name"]
            SYMBOL = config.BYBIT_CHAINS[chain]["token_name"]
            if amount:
                AMOUNT = amount
            else:
                AMOUNT = round(uniform(*settings.WITHDRAW_PARAMS["withdraw_range"]), randint(4, 6))

            account_bybit = bybit({
                'apiKey': settings.BYBIT_KEY,
                'secret': settings.BYBIT_SECRET,
                'enableRateLimit': True,
            })

            try:
                old_coins_balances = account_bybit.privateGetAssetV3PrivateTransferAccountCoinsBalanceQuery(
                    {'accountType': 'UNIFIED', 'coin': SYMBOL}
                )['result']['balance']
                old_trading_eth_balance = float(old_coins_balances[0]['transferBalance'])
            except Exception as err:
                if 'Too many visits.' in str(err):
                    logger.warning(f'[•] Bybit | API Rate Limit (fetch old {SYMBOL} balance)')
                    sleeping(60)
                    return self.bybit_withdraw(chain=chain, amount=amount, retry=retry)
                else:
                    logger.error(f'[-] Bybit | Couldnt get {SYMBOL} UNIFIED balance: {err}')
                    raise Exception(str(err))

            if old_trading_eth_balance:
                try:
                    r = account_bybit.transfer(code=SYMBOL, amount=old_trading_eth_balance, fromAccount='UNIFIED', toAccount='FUND')
                except Exception as err:
                    if 'Too many visits.' in str(err):
                        logger.warning(f'[•] Bybit | API Rate Limit (transfer)')
                        sleeping(60)
                        return self.bybit_withdraw(chain=chain, amount=amount, retry=retry)
                    else: raise Exception(str(err))

                if r.get('status') == 'ok':
                    logger.info(f'[+] Bybit | Transfered {old_trading_eth_balance} {SYMBOL} from SPOT to FUND')
                else:
                    logger.warning(f'[-] Bybit | Couldnt transfer {old_trading_eth_balance} {SYMBOL} from SPOT to FUND: {r}')

            try:
                coins_balances = account_bybit.privateGetAssetV3PrivateTransferAccountCoinsBalanceQuery(
                    {'accountType': 'FUND', 'coin': SYMBOL}
                )['result']['balance']
                fund_eth_balance = float(coins_balances[0]['transferBalance'])
            except Exception as err:
                if 'Too many visits.' in str(err):
                    logger.warning(f'[•] Bybit | API Rate Limit (get coins balance)')
                    sleeping(60)
                    return self.bybit_withdraw(chain=chain, amount=amount, retry=retry)
                else:
                    logger.error(f'[-] Bybit | Couldnt get {SYMBOL} FUND balance')
                    raise Exception(str(err))

            if fund_eth_balance < AMOUNT:
                logger.warning(f'[-] Bybit | No funds to withdraw. Balance: {fund_eth_balance} but need at least {AMOUNT}')
                sleeping(10)
                return self.bybit_withdraw(chain=chain, amount=amount, retry=retry)

            try:
                result = account_bybit.withdraw(
                    code=SYMBOL,
                    amount=AMOUNT,
                    address=self.address,
                    params={
                        'chain': CHAIN,
                        'timestamp': int(time() * 1000),
                        'accountType': 'FUND'}
                )
            except Exception as err:
                if 'Withdraw address chain or destination tag are not equal' in str(err):
                    try:
                        sleep(15)
                        result = account_bybit.withdraw(
                            code=SYMBOL,
                            amount=AMOUNT,
                            address=self.address.lower(),
                            params={
                                'chain': CHAIN,
                                'timestamp': int(time() * 1000),
                                'accountType': 'FUND'}
                        )
                    except Exception as err:
                        if 'Too many visits.' in str(err):
                            logger.warning(f'[•] Bybit | API Rate Limit (withdraw x2)')
                            sleeping(60)
                            return self.bybit_withdraw(chain=chain, amount=amount, retry=retry)
                        else:
                            raise Exception(str(err))
                elif 'Too many visits.' in str(err):
                    logger.warning(f'[•] Bybit | API Rate Limit (withdraw)')
                    sleeping(60)
                    return self.bybit_withdraw(chain=chain, amount=amount, retry=retry)
                else:
                    raise Exception(str(err))

            if result.get('id'):
                logger.success(f'[+] Bybit | Success withdraw {AMOUNT} {SYMBOL} to {self.address}')
                self.db.append_report(privatekey=self.encoded_pk, text=f'Bybit withdraw {AMOUNT} {SYMBOL} in {chain.title()}', success=True)

                new_balance = self.wait_balance(chain_name=chain, needed_balance=old_balance, only_more=True)
                return chain, round(new_balance - old_balance, 6)

        except Exception as err:
            logger.error(f'[-] Bybit | Withdraw error to {self.address}: {err}')

            if retry < settings.RETRY:
                sleeping(10)
                if 'Withdrawal amount is greater than your available balance' in str(err) or 'Please wait at least 10 seconds between withdrawals' in str(err):
                    return self.bybit_withdraw(chain=chain, amount=amount, retry=retry)
                return self.bybit_withdraw(chain=chain, amount=amount, retry=retry+1)
            else:
                raise ValueError(f'Bybit withdraw error to {self.address}: {err}')


    def bitget_withdraw(self, chain: str, amount: float = None, lowercase: bool = False, retry: int = 0):
        def find_subacc_balance(subacc_id: str):
            subaccounts_balances_ = account_bitget.private_spot_get_v2_spot_account_subaccount_assets()["data"]
            for subacc_balances_ in subaccounts_balances_:
                if subacc_balances_['userId'] == subacc_id:
                    for token_data in subacc_balances_["assetsList"]:
                        if token_data["coin"] == SYMBOL:
                            return token_data

        self.wait_for_gwei()

        SYMBOL = config.BITGET_CHAINS[chain]["token_name"]
        NETWORK = config.BITGET_CHAINS[chain]["chain_name"]
        if amount:
            AMOUNT = amount
        else:
            AMOUNT = round(uniform(*settings.WITHDRAW_PARAMS["withdraw_range"]), randint(4, 7))

        old_balance = self.get_balance(chain_name=chain, human=True)
        account_bitget = bitget({
            'apiKey': settings.BITGET_KEY,
            'secret': settings.BITGET_SECRET,
            'password': settings.BITGET_PASSWORD,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })

        if lowercase: address = self.address.lower()
        else: address = self.address

        main_account_balance = account_bitget.fetch_balance({"coin": SYMBOL})["free"].get(SYMBOL, 0)
        if main_account_balance < AMOUNT:
            subaccounts_balances = account_bitget.private_spot_get_v2_spot_account_subaccount_assets()["data"]
            user_id = None
            for subacc_balances in subaccounts_balances:
                sub_acc_id = f'#{subacc_balances["userId"]}'
                for token_data in subacc_balances["assetsList"]:
                    if token_data["coin"] == SYMBOL:
                        frozen_notified = False
                        frozen_error_notified = False
                        while True:
                            while True:
                                sub_balance = float(token_data["available"])
                                if float(token_data["frozen"]) == 0:
                                    break
                                else:
                                    if not frozen_notified:
                                        frozen_notified = True
                                        logger.warning(f'[•] Bitget | {sub_acc_id} | {sub_balance} {SYMBOL} - frozen {token_data["frozen"]} {SYMBOL}')
                                    sleep(5)
                                    token_data = find_subacc_balance(subacc_id=subacc_balances["userId"])

                            if float(token_data["locked"]):
                                locked_adv = f"({token_data['locked']} locked)"
                            else:
                                locked_adv = ""

                            if not frozen_error_notified:
                                logger.info(f'[•] Bitget | {sub_acc_id} | {sub_balance} {SYMBOL} {locked_adv}')

                            if float(sub_balance) > 0:
                                if user_id is None:
                                    user_id = account_bitget.private_spot_get_v2_spot_account_info()["data"]["userId"]
                                try:
                                    account_bitget.private_spot_post_v2_spot_wallet_subaccount_transfer(
                                        {
                                            "fromType": "spot",
                                            "toType": "spot",
                                            "amount": str(sub_balance),
                                            "coin": SYMBOL,
                                            "fromUserId": str(subacc_balances["userId"]),
                                            "toUserId": user_id,
                                        }
                                    )
                                    break
                                except Exception as err:
                                    if "is temporarily frozen" in str(err):
                                        if frozen_error_notified is False:
                                            frozen_error_notified = True
                                            logger.warning(f'[-] Bitget | Couldnt transfer {sub_balance} {SYMBOL} from sub account, trying again...')
                                        sleep(5)

                            else:
                                break

        try:
            account_bitget.withdraw(
                code=SYMBOL,
                amount=AMOUNT,
                address=address,
                params={"chain": NETWORK}
            )
            logger.success(f"[+] Bitget | Success withdraw {AMOUNT} {SYMBOL} in {chain.title()}")
            self.db.append_report(privatekey=self.encoded_pk, text=f'Bitget Withdraw {AMOUNT} {SYMBOL} in {chain.title()}', success=True)
            new_balance = self.wait_balance(chain_name=chain, needed_balance=old_balance, only_more=True)
            return chain, new_balance-old_balance

        except Exception as error:
            if retry < settings.RETRY:
                if 'Withdraw address is not in addressBook' in str(error): return self.bitget_withdraw(chain=chain, amount=amount, lowercase=True, retry=retry+1)

                logger.error(f'[-] Bitget | Withdraw to {chain.title()} error: {error}')
                sleeping(10)
                if 'Insufficient balance' in str(error): return self.bitget_withdraw(chain=chain, amount=amount, lowercase=lowercase, retry=retry)
                else: return self.bitget_withdraw(chain=chain, amount=amount, lowercase=lowercase, retry=retry+1)

            else:
                self.db.append_report(privatekey=self.encoded_pk, text=f'Bitget Withdraw {AMOUNT} {SYMBOL}: {error}', success=False)
                raise ValueError(f'Bitget withdraw error: {error}')


    def binance_withdraw(self, chain: str, amount: float = None, retry = 0):
        self.wait_for_gwei()
        old_balance = self.get_balance(chain_name=chain, human=True)

        SYMBOL = config.BINANCE_CHAINS[chain]["token_name"]
        NETWORK = config.BINANCE_CHAINS[chain]["chain_name"]
        if amount:
            AMOUNT = amount
        else:
            AMOUNT = round(uniform(*settings.WITHDRAW_PARAMS["withdraw_range"]), randint(4, 6))

        account_binance = binance({
            'apiKey': settings.BINANCE_KEY,
            'secret': settings.BINANCE_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'
            }
        })

        try:
            account_binance.withdraw(
                code=SYMBOL,
                amount=AMOUNT,
                address=self.address,
                params={
                    "network": NETWORK
                }
            )
            logger.success(f"[+] Binance | Success withdraw {AMOUNT} {SYMBOL} in {chain.title()}")
            self.db.append_report(privatekey=self.encoded_pk, text=f'Binance Withdraw {AMOUNT} {SYMBOL} in {chain.title()}', success=True)
            new_balance = self.wait_balance(chain_name=chain, needed_balance=old_balance, only_more=True)
            return chain, new_balance-old_balance

        except Exception as error:
            if retry < settings.RETRY:
                logger.error(f'[-] Binance | Withdraw to {chain.title()} error: {error}')
                sleeping(10)
                return self.binance_withdraw(chain=chain, amount=amount, retry=retry + 1)

            else:
                self.db.append_report(privatekey=self.encoded_pk, text=f'Binance Withdraw {AMOUNT} {SYMBOL}: {error}', success=False)
                raise ValueError(f'Binance withdraw error: {error}')


    def withdraw_funds(self, **kwargs):
        cex_list = {
            'bybit': self.bybit_withdraw,
            'okx': self.okx_withdraw,
            'bitget': self.bitget_withdraw,
            'binance': self.binance_withdraw,
        }

        if kwargs.get("chain") is None:
            kwargs["chain"] = choice(settings.WITHDRAW_PARAMS["chains"])
        random_cex = choice(settings.WITHDRAW_PARAMS["exchange"]).lower()

        return cex_list[random_cex](**kwargs)


    def sign_message(
            self,
            text: str = None,
            typed_data: dict = None,
            hash: bool = False
    ):
        if text:
            message = encode_defunct(text=text)
        elif typed_data:
            message = encode_typed_data(full_message=typed_data)
            if hash:
                message = encode_defunct(hexstr=_hash_eip191_message(message).hex())

        signed_message = self.account.sign_message(message)
        signature = signed_message.signature.hex()
        if not signature.startswith('0x'): signature = '0x' + signature
        return signature


    def send_native(self, chain_name: str, amount: float):
        web3 = self.get_web3(chain_name=chain_name)
        contract_tx = {
            'from': self.address,
            'to': self.recipient,
            'chainId': web3.eth.chain_id,
            'nonce': web3.eth.get_transaction_count(self.address),
            'value': int(amount * 1e18),
        }

        module_str = f"send {str(round(Decimal(amount), 8))} ETH in {chain_name}"
        try:
            self.sent_tx(
                chain_name=chain_name,
                tx=contract_tx,
                tx_label=module_str,
                tx_raw=True
            )
            return True

        except Exception as err:
            logger.error(f'[-] Web3 | Failed to send {amount} ETH in {chain_name}: {err}')
            self.db.append_report(
                privatekey=self.encoded_pk,
                text=f"failed to send {amount} ETH in {chain_name}",
                success=False,
            )
            return False
