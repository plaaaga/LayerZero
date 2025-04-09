from random import uniform, randint
from time import sleep

from modules.config import LAYERZERO_CHAINS
from modules.utils import sleeping, logger
from modules.wallet import Wallet
from modules.retry import retry
from settings import BRIDGE_PARAMS


class Stargate(Wallet):
    def __init__(self, wallet: Wallet, from_chain: str, to_chain: str, bridge_value: int, mode: str):
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

        self.bridge_contract = self.web3.eth.contract(
            address=LAYERZERO_CHAINS[self.from_chain]["address"],
            abi='[{"inputs":[{"components":[{"internalType":"uint32","name":"dstEid","type":"uint32"},{"internalType":"bytes32","name":"to","type":"bytes32"},{"internalType":"uint256","name":"amountLD","type":"uint256"},{"internalType":"uint256","name":"minAmountLD","type":"uint256"},{"internalType":"bytes","name":"extraOptions","type":"bytes"},{"internalType":"bytes","name":"composeMsg","type":"bytes"},{"internalType":"bytes","name":"oftCmd","type":"bytes"}],"internalType":"structSendParam","name":"_sendParam","type":"tuple"},{"internalType":"bool","name":"_payInLzToken","type":"bool"}],"name":"quoteSend","outputs":[{"components":[{"internalType":"uint256","name":"nativeFee","type":"uint256"},{"internalType":"uint256","name":"lzTokenFee","type":"uint256"}],"internalType":"structMessagingFee","name":"fee","type":"tuple"}],"stateMutability":"view","type":"function"},{"inputs":[{"components":[{"internalType":"uint32","name":"dstEid","type":"uint32"},{"internalType":"bytes32","name":"to","type":"bytes32"},{"internalType":"uint256","name":"amountLD","type":"uint256"},{"internalType":"uint256","name":"minAmountLD","type":"uint256"},{"internalType":"bytes","name":"extraOptions","type":"bytes"},{"internalType":"bytes","name":"composeMsg","type":"bytes"},{"internalType":"bytes","name":"oftCmd","type":"bytes"}],"internalType":"structSendParam","name":"_sendParam","type":"tuple"},{"components":[{"internalType":"uint256","name":"nativeFee","type":"uint256"},{"internalType":"uint256","name":"lzTokenFee","type":"uint256"}],"internalType":"structMessagingFee","name":"_fee","type":"tuple"},{"internalType":"address","name":"_refundAddress","type":"address"}],"name":"send","outputs":[{"components":[{"internalType":"bytes32","name":"guid","type":"bytes32"},{"internalType":"uint64","name":"nonce","type":"uint64"},{"components":[{"internalType":"uint256","name":"nativeFee","type":"uint256"},{"internalType":"uint256","name":"lzTokenFee","type":"uint256"}],"internalType":"structMessagingFee","name":"fee","type":"tuple"}],"internalType":"structMessagingReceipt","name":"msgReceipt","type":"tuple"},{"components":[{"internalType":"uint256","name":"amountSentLD","type":"uint256"},{"internalType":"uint256","name":"amountReceivedLD","type":"uint256"}],"internalType":"structOFTReceipt","name":"oftReceipt","type":"tuple"}],"stateMutability":"payable","type":"function"},{"inputs":[{"components":[{"internalType":"uint32","name":"dstEid","type":"uint32"},{"internalType":"bytes32","name":"to","type":"bytes32"},{"internalType":"uint256","name":"amountLD","type":"uint256"},{"internalType":"uint256","name":"minAmountLD","type":"uint256"},{"internalType":"bytes","name":"extraOptions","type":"bytes"},{"internalType":"bytes","name":"composeMsg","type":"bytes"},{"internalType":"bytes","name":"oftCmd","type":"bytes"}],"internalType":"structSendParam","name":"_sendParam","type":"tuple"}],"name":"quoteOFT","outputs":[{"components":[{"internalType":"uint256","name":"minAmountLD","type":"uint256"},{"internalType":"uint256","name":"maxAmountLD","type":"uint256"}],"internalType":"structOFTLimit","name":"limit","type":"tuple"},{"components":[{"internalType":"int256","name":"feeAmountLD","type":"int256"},{"internalType":"string","name":"description","type":"string"}],"internalType":"structOFTFeeDetail[]","name":"oftFeeDetails","type":"tuple[]"},{"components":[{"internalType":"uint256","name":"amountSentLD","type":"uint256"},{"internalType":"uint256","name":"amountReceivedLD","type":"uint256"}],"internalType":"structOFTReceipt","name":"receipt","type":"tuple"}],"stateMutability":"view","type":"function"}]'
        )

        self.wait_for_gwei()

    def get_bridge_type(self):
        if self.mode == "cheap":
            return "0x01"  # cheap mode

        bus_data = self.browser.get_bus_queue(from_chain=self.from_chain, to_chain=self.to_chain)
        if bus_data["capacity"] == bus_data["passengers"] + 1:
            return "0x01"  # cheap mode
        else:
            return "0x"    # fast mode

    @retry(source="Stargate", module_str="Bridge", exceptions=Exception)
    def bridge(self, fee_notified: bool = False):
        amount = round(self.value / 1e18, 8)
        module_str = f'*stargate {self.mode} bridge {amount} ETH {self.from_chain} -> {self.to_chain}'
        try:
            send_params = [
                LAYERZERO_CHAINS[self.to_chain]["id"],
                f"0x000000000000000000000000{self.address[2:]}",
                self.value,
                int(self.value * 0.995),
                "0x",
                "0x",
                self.get_bridge_type()
            ]

            protocol_fee = (self.value - self.bridge_contract.functions.quoteOFT(send_params).call()[2][1]) / 1e18
            if protocol_fee > BRIDGE_PARAMS["max_stargate_fee"]:
                if not fee_notified:
                    logger.error(
                        f'[-] Web3 | Stargate fee {protocol_fee} ETH more than {BRIDGE_PARAMS["max_stargate_fee"]} ETH '
                        f'for bridge {amount} ETH in {self.from_chain.title()}. Waiting for lowest fee...'
                    )
                sleep(10)
                return self.bridge(fee_notified=True)

            fee = self.bridge_contract.functions.quoteSend(send_params, False).call()[0]

            rounder = randint(11, 14)
            value = int((self.value - fee) // 10 ** rounder * 10 ** rounder)

            module_str = f'stargate {self.mode} bridge {round(value / 1e18, 4)} ETH {self.from_chain} -> {self.to_chain}'
            send_params[2], send_params[3] = value, int(value * 0.995)
            fee = self.bridge_contract.functions.quoteSend(send_params, False).call()[0]

            contract_txn = self.bridge_contract.functions.send(
                send_params,
                [fee, 0],
                self.address,
            )

            old_balance = self.get_balance(chain_name=self.to_chain, human=True)
            tx_hash = self.sent_tx(chain_name=self.from_chain, tx=contract_txn, tx_label=module_str, value=int(value+fee))
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
