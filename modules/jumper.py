from time import sleep, time

from modules.utils import logger
from modules.wallet import Wallet
from modules.retry import retry
from settings import BRIDGE_PARAMS


class Jumper(Wallet):

    tools: dict = {
        "cheap": "stargateV2Bus",
        "fast": "stargateV2",
    }

    def __init__(self, wallet: Wallet, from_chain: str, to_chain: str, bridge_value: float, mode: str):
        super().__init__(
            privatekey=wallet.privatekey,
            encoded_pk=wallet.encoded_pk,
            recipient=wallet.recipient,
            db=wallet.db,
            browser=wallet.browser
        )

        self.bridged_amount = None
        self.value = bridge_value
        self.from_chain = from_chain
        self.to_chain = to_chain
        self.mode = mode

        self.web3 = self.get_web3(chain_name=self.from_chain)
        self.from_chain_id = self.web3.eth.chain_id
        self.to_chain_id = self.get_web3(self.to_chain).eth.chain_id

        self.wait_for_gwei()


    @retry(source="Jumper", module_str="Bridge", exceptions=Exception)
    def bridge(self):
        amount = round(self.value / 1e18, 8)
        module_str = f'*jumper {self.mode} bridge {amount} ETH {self.from_chain} -> {self.to_chain}'
        try:
            tx_status, tx_data = self.build_swap_tx()
            if not tx_status:
                return tx_data

            contract_tx = {
                'from': self.address,
                'to': self.web3.to_checksum_address(tx_data["to"]),
                'data': tx_data["data"],
                'chainId': self.from_chain_id,
                'nonce': self.web3.eth.get_transaction_count(self.address),
                'value': int(tx_data["value"], 16),
            }
            module_str = f'jumper {self.mode} bridge {round(contract_tx["value"] / 1e18, 4)} ETH {self.from_chain} -> {self.to_chain}'

            old_balance = self.get_balance(chain_name=self.to_chain, human=True)
            tx_hash = self.sent_tx(
                chain_name=self.from_chain,
                tx=contract_tx,
                tx_label=module_str,
                tx_raw=True
            )
            new_balance = self.wait_balance(chain_name=self.to_chain, needed_balance=old_balance, only_more=True)
            self.bridged_amount = round(new_balance - old_balance, 6)

            return True

        except Exception as error:
            if "insufficient funds for transfer" in str(error):
                logger.warning(f'[-] Web3 | {module_str} | insufficient funds for transfer, recalculating')
                self.value = int(self.value - 0.00004 * 1e18)
                return self.bridge()
            else:
                raise

    def build_swap_tx(self):
        notified = False
        limit_time = time() + 120
        while True:
            if time() >= limit_time:
                logger.error(f'[-] Jumper | Failed to find routes in 2 minutes')
                return False, "timed_out"

            routes = self.browser.get_jumper_routes(
                from_chain_id=self.from_chain_id,
                to_chain_id=self.to_chain_id,
                value=self.value
            )
            for route in routes:
                if route["steps"][0]["tool"] == self.tools[self.mode]:
                    tx_result = self.browser.get_jumper_tx(route["steps"][0])
                    protocol_fee = (self.value - tx_result["out_value"]) / 1e18
                    if protocol_fee > BRIDGE_PARAMS["max_stargate_fee"]:
                        amount = round(self.value / 1e18, 8)
                        logger.error(
                            f'[-] Web3 | Jumper (stargate) fee {round(protocol_fee, 6)} ETH more than '
                            f'{BRIDGE_PARAMS["max_stargate_fee"]} ETH for bridge '
                            f'{amount} ETH from {self.from_chain.title()}'
                        )
                    else:
                        return True, tx_result

            if not notified:
                notified = True
                logger.warning(f'[-] Jumper | No {self.mode} routes found, waiting for new...')

            sleep(10)
