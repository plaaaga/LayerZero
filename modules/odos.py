from modules.wallet import Wallet
from modules.retry import retry


class Odos(Wallet):

    def __init__(self, wallet: Wallet, from_chain: str):
        super().__init__(
            privatekey=wallet.privatekey,
            encoded_pk=wallet.encoded_pk,
            recipient=wallet.recipient,
            db=wallet.db,
            browser=wallet.browser
        )

        self.from_chain = from_chain
        self.web3 = self.get_web3(self.from_chain)
        self.chain_id = self.web3.eth.chain_id


    @retry(source="Odos", module_str="Swap", exceptions=Exception)
    def swap(
            self,
            from_token_info: dict,
            to_token_info: dict,
            amount: str,
            value: int
    ):
        self.wait_for_gwei()

        odos_address = self.web3.to_checksum_address(self.browser.odos_get_contract(chain_id=self.chain_id))

        if from_token_info["address"] != "0x0000000000000000000000000000000000000000":
            self.approve(
                chain_name=self.from_chain,
                token_address=from_token_info["address"],
                spender=self.web3.to_checksum_address(odos_address),
                value=0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff,
                decimals=from_token_info["decimals"],
            )
            tx_value = 0
        else:
            tx_value = value

        odos_quote = self.browser.odos_quote(
            from_token_address=from_token_info["address"],
            to_token_address=to_token_info["address"],
            to_token_decimals=to_token_info["decimals"],
            value=value,
            chain_id=self.chain_id,
        )
        odos_tx = self.browser.odos_assemble(
            path_id=odos_quote["path_id"]
        )
        tx_label = f"odos {self.from_chain} swap {round(float(amount), 4)} {from_token_info['symbol']} -> {round(odos_quote['amount_out'], 4)} {to_token_info['symbol']}"

        contract_tx = {
            'from': self.address,
            'to': odos_tx["to"],
            'data': odos_tx["data"],
            'chainId': self.web3.eth.chain_id,
            'nonce': self.web3.eth.get_transaction_count(self.address),
            'value': tx_value
        }

        self.sent_tx(
            chain_name=self.from_chain,
            tx=contract_tx,
            tx_label=tx_label,
            tx_raw=True
        )
        return True
