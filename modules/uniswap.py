from decimal import Decimal

from .wallet import Wallet
from .retry import retry


class Uniswap(Wallet):

    approve_data: dict = {
      "types": {"EIP712Domain": [{"name": "name", "type": "string"}, {"name": "chainId", "type": "uint256"}, {"name": "verifyingContract", "type": "address"}]},
      "primaryType": "PermitSingle",
    }

    def __init__(self, wallet: Wallet, from_chain: str):
        super().__init__(
            privatekey=wallet.privatekey,
            encoded_pk=wallet.encoded_pk,
            db=wallet.db,
            browser=wallet.browser,
            recipient=wallet.recipient
        )

        self.from_chain = from_chain
        self.web3 = self.get_web3(self.from_chain)
        self.chain_id = self.web3.eth.chain_id


    @retry(source="Uniswap", module_str="Swap", exceptions=Exception)
    def swap(
            self,
            from_token_info: dict,
            to_token_info: dict,
            amount: str,
            value: int,
    ):
        swap_quote = self.browser.get_uniswap_quote(
            input_address=from_token_info["address"],
            output_address=to_token_info["address"],
            value=value,
            chain_id=self.chain_id
        )
        if (
                from_token_info["address"] != "0x0000000000000000000000000000000000000000" and
                swap_quote["permitData"]
        ):
            if self.approve(
                chain_name=self.from_chain,
                token_address=from_token_info["address"],
                spender=self.web3.to_checksum_address(swap_quote["permitData"]["domain"]["verifyingContract"]),
                value=0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff,
                decimals=from_token_info["decimals"],
            ):
                return self.swap(from_token_info, to_token_info, amount, value)

            else:
                typed_data = {
                    "domain": {key: str(value) for key, value in swap_quote["permitData"]["domain"].items()},
                    "types": {
                        **self.approve_data["types"],
                        **swap_quote["permitData"]["types"],
                    },
                    "message": swap_quote["permitData"]["values"],
                    "primaryType": self.approve_data["primaryType"]
                }
                permit_headers = {
                    "signature": self.sign_message(typed_data=typed_data),
                    "permitData": swap_quote["permitData"]
                }
        else:
            permit_headers = {}

        min_out = str(round(Decimal(
            int(swap_quote["quote"]["aggregatedOutputs"][0]["minAmount"]) / 10 ** to_token_info["decimals"]
        ), 4))
        swap_data = self.browser.get_uniswap_swap_tx(swap_quote=swap_quote["quote"], permit_headers=permit_headers)
        if swap_data.get("soft_error"):
            raise Exception(swap_data["reason"])

        swap_tx = {
            "from": self.address,
            "to": self.web3.to_checksum_address(swap_data["to"]),
            "data": swap_data["data"],
            "value": int(swap_data["value"], 16),
            'chainId': self.web3.eth.chain_id,
            'nonce': self.web3.eth.get_transaction_count(self.address),
        }
        tx_label = f"uniswap {self.from_chain} swap {round(float(amount), 4)} {from_token_info['symbol']} -> {min_out} {to_token_info['symbol']}"

        self.sent_tx(
            chain_name=self.from_chain,
            tx=swap_tx,
            tx_label=tx_label,
            tx_raw=True
        )
        return True
