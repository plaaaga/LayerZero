from random import randint, uniform, choice
from decimal import Decimal
from loguru import logger

from modules.stargate import Stargate
from modules.uniswap import Uniswap
from modules.jumper import Jumper
from modules.odos import Odos
from modules.utils import cround

from settings import BRIDGE_PARAMS, SLEEP_AFTER_TX, RETRY, SWAP_PARAMS
from modules.config import BRIDGE_TYPES
from modules.utils import sleeping
from modules.wallet import Wallet


class Bridger(Wallet):
    def __init__(self, wallet: Wallet):
        super().__init__(
            privatekey=wallet.privatekey,
            encoded_pk=wallet.encoded_pk,
            recipient=wallet.recipient,
            db=wallet.db,
            browser=wallet.browser
        )

    def run(self):
        last_bridge_chain, _ = self.withdraw_funds()

        bridges_amount = randint(*BRIDGE_PARAMS["bridges_amount"])
        bridges_path = self.build_path(first_chain=last_bridge_chain, bridges_amount=bridges_amount)

        for bridge_i, to_bridge_chain in enumerate(bridges_path):
            retry = 1
            while True:
                result, response = self.bridge_eth(
                    last_bridge_chain=last_bridge_chain,
                    to_bridge_chain=to_bridge_chain,
                    bridge_index=f"[{bridge_i + 1}/{len(bridges_path)}]",
                    to_raise=retry > RETRY
                )
                if result is True:
                    last_bridge_chain = response
                else:
                    logger.error(f'[-] Soft | {response} [{retry}/{RETRY}]')
                    retry += 1
                    continue

                self.swap_tokens(chain_name=last_bridge_chain)
                break

        native_value = self.get_balance(chain_name=last_bridge_chain)
        keep_value = int(uniform(*BRIDGE_PARAMS["keep_amounts"][last_bridge_chain]) * 1e18)
        send_amount = round((native_value - keep_value) / 1e18, randint(5, 8))
        self.send_native(chain_name=last_bridge_chain, amount=send_amount)

        return True


    def bridge_eth(
            self,
            last_bridge_chain: str,
            to_bridge_chain: str,
            bridge_index: str,
            to_raise: bool,
            force_bridge: str = None,
    ):
        if force_bridge:
            random_bridge = force_bridge
        else:
            random_bridge = choice(BRIDGE_PARAMS["available_bridges"])
        bridge_params = BRIDGE_TYPES[random_bridge]

        try:
            native_value = self.get_balance(chain_name=last_bridge_chain)
            keep_value = int(uniform(*BRIDGE_PARAMS["keep_amounts"][last_bridge_chain]) * 1e18)
            rounder = randint(10, 13)
            bridge_value = int((native_value - keep_value) // 10 ** rounder * 10 ** rounder)

            logger.info(
                f'[•] Bridges | {random_bridge} bridge from {last_bridge_chain.title()} '
                f'to {to_bridge_chain.title()} {bridge_index}'
            )
            bridge_status = MODULES_DATA[bridge_params["module"]](
                wallet=self,
                from_chain=last_bridge_chain,
                to_chain=to_bridge_chain,
                bridge_value=bridge_value,
                mode=bridge_params["mode"]
            ).bridge()
            if bridge_status is not True:
                if bridge_params["module"] != "stargate" and bridge_status == "timed_out":
                    force_bridge = [
                        bridge_type
                        for bridge_type in BRIDGE_TYPES
                        if (
                            BRIDGE_TYPES[bridge_type]["module"] == "stargate" and
                            BRIDGE_TYPES[bridge_type]["mode"] == bridge_params["mode"]
                        )
                    ][0]
                    return self.bridge_eth(
                        last_bridge_chain=last_bridge_chain,
                        to_bridge_chain=to_bridge_chain,
                        bridge_index=bridge_index,
                        to_raise=to_raise,
                        force_bridge=force_bridge,
                    )
                else:
                    raise Exception(str(bridge_status))

            sleeping(SLEEP_AFTER_TX)
            return True, to_bridge_chain

        except Exception as err:
            if to_raise:
                raise
            else:
                return False, f"{random_bridge} Bridge failed: {str(err)}"


    def swap_tokens(self, chain_name: str):
            swap_amount = randint(*SWAP_PARAMS["swap_amount"])
            if (
                    swap_amount and
                    SWAP_PARAMS["chains_swap"].get(chain_name)
            ):
                for swap_i in range(swap_amount):
                    random_dex = choice(SWAP_PARAMS["chains_swap"][chain_name])

                    try:
                        logger.info(f'[•] Swaps | {random_dex["swap_name"].title()} swap in {chain_name.title()} [{swap_i + 1}/{swap_amount}]')
                        swap_module = MODULES_DATA[random_dex["swap_name"]](
                            wallet=self,
                            from_chain=chain_name,
                        )

                        # ETH -> token
                        swap_amounts = {
                            "amounts": SWAP_PARAMS["amounts"],
                            "percents": SWAP_PARAMS["percents"],
                            "percent_back": SWAP_PARAMS["percent_back"]
                        }
                        token_to_swap = choice(random_dex["tokens_to_swap"])

                        eth_balance = self.get_balance(chain_name=chain_name, human=True)
                        if swap_amounts["amounts"] != [0, 0]:
                            if eth_balance < swap_amounts["amounts"][0]:
                                logger.error(
                                    f"[-] Web3 | No ETH balance ({round(eth_balance, 5)}) for swap ({swap_amounts['amounts'][0]})"
                                )
                                return
                            elif eth_balance < swap_amounts["amounts"][1]:
                                swap_amounts["amounts"][1] = eth_balance

                            amount = uniform(*swap_amounts["amounts"])
                        else:
                            percent = uniform(*swap_amounts["percents"]) / 100
                            amount = eth_balance * percent

                        amount_to_swap = str(round(Decimal(amount), randint(7, 9)))

                        to_token_info = self.get_token_info(chain_name, token_to_swap)
                        native_token_info = self.get_token_info(chain_name, "ETH")

                        swap_module.swap(
                            from_token_info=native_token_info,
                            to_token_info=to_token_info,
                            amount=amount_to_swap,
                            value=int(float(amount_to_swap) * 1e18),
                        )
                        sleeping(SLEEP_AFTER_TX)

                        # token -> ETH
                        if swap_amounts["percent_back"] != [0, 0]:
                            new_token_info = self.get_token_info(chain_name=chain_name, token_name=token_to_swap)
                            percent_back = uniform(*swap_amounts["percent_back"]) / 100

                            amount_back = str(round(Decimal(new_token_info["amount"] * percent_back), randint(7, 9)))
                            value_back = int(new_token_info["value"] * cround(percent_back, 5))

                            swap_module.swap(
                                from_token_info=new_token_info,
                                to_token_info=native_token_info,
                                amount=amount_back,
                                value=value_back,
                            )
                            sleeping(SLEEP_AFTER_TX)

                    except Exception as err:
                        logger.error(f'[-] Web3 | {random_dex["swap_name"].title()} swap error: {err}')
                        self.db.append_report(
                            privatekey=self.encoded_pk,
                            text=f"{random_dex['swap_name']} swap",
                            success=False,
                        )


    def build_path(self, first_chain: str, bridges_amount: int):
        all_chains = list(BRIDGE_PARAMS["keep_amounts"].keys())
        last_chains = BRIDGE_PARAMS["last_chains"]
        path = [first_chain]
        for bridge_i in range(bridges_amount):
            if bridge_i + 1 == bridges_amount:  # if last
                possible_chains = [chain for chain in last_chains if chain != path[-1]]
            else:
                if bridge_i + 2 == bridges_amount and len(last_chains) == 1:  # if pre-last
                    restricted_chains = last_chains
                else:
                    restricted_chains = []

                possible_rare_chains = [chain for chain in all_chains if chain not in path[-2:] + restricted_chains]
                if len(possible_rare_chains) > 1:
                    possible_chains = possible_rare_chains
                else:
                    possible_chains = [chain for chain in all_chains if chain not in [path[-1], *restricted_chains]]

            if not possible_chains:
                # logger.warning('[-] Soft | Skipping 1 bridge because you provided too few chains!')
                continue
            path.append(choice(possible_chains))

        return path[1:]


MODULES_DATA = {
    "stargate": Stargate,
    "jumper": Jumper,
    "uniswap": Uniswap,
    "odos": Odos,
}