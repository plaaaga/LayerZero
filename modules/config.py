
CHAINS_DATA = {
    'ethereum': {'explorer': 'https://etherscan.io/tx/'},
    'base': {'explorer': 'https://basescan.org/tx/'},
    'arbitrum': {'explorer': 'https://arbiscan.io/tx/'},
    'zksync': {'explorer': 'https://era.zksync.network/tx/'},
    'optimism': {'explorer': 'https://optimistic.etherscan.io/tx/'},
    'scroll': {'explorer': 'https://scrollscan.com/tx/'},
    'nova': {'explorer': 'https://nova-explorer.arbitrum.io/tx/'},
    'linea': {'explorer': 'https://lineascan.build/tx/'},
    'bsc': {'explorer': 'https://bscscan.com/tx/'},
    'polygon': {'explorer': 'https://polygonscan.com/tx/'},
    'celo': {'explorer': 'https://celoscan.io/tx/'},
    'moonbeam': {'explorer': 'https://moonscan.io/tx/'},
    'fantom': {'explorer': 'https://ftmscan.com/tx/'},
    'avax': {'explorer': 'https://snowtrace.io/tx/'},
    'zora': {'explorer': 'https://zorascan.xyz/tx/'},
    'taiko': {'explorer': 'https://taikoscan.io/tx/'},
    'blast': {'explorer': 'https://blastscan.io/tx/'},
    'zkevm': {'explorer': 'https://zkevm.polygonscan.com/tx/'},
    'unichain': {'explorer': 'https://uniscan.xyz/tx/'},
}

TOKEN_ADDRESSES = {
    'ethereum': {
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "AAVE": "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
        "UNI": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
    },
    'arbitrum': {
        "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
        "ARB": "0x912CE59144191C1204E64559FE8253a0e49E6548",
        "ZRO": "0x6985884C4392D348587B19cb9eAAf157F13271cd",
    },
    'optimism': {
        "USDC": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
        "USDT": "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",
        "OP": "0x4200000000000000000000000000000000000042",
        "ZRO": "0x6985884C4392D348587B19cb9eAAf157F13271cd",
    },
    'base': {
        "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "TOSHI": "0xAC1Bd2486aAf3B5C0fc3Fd868558b082a531B2B4",
        "ZRO": "0x6985884C4392D348587B19cb9eAAf157F13271cd",
    },
    'linea': {
        "USDC": "0x176211869cA2b568f2A7D4EE941E073a821EE1ff",
        "USDT": "0xA219439258ca9da29E9Cc4cE5596924745e12B93",
        "DAI": "0x4AF15ec2A0BD43Db75dd04E62FAA3B8EF36b00d5",
        "LINK": "0x5B16228B94b68C7cE33AF2ACc5663eBdE4dCFA2d",
        "SHIB": "0x99AD925C1Dc14Ac7cc6ca1244eeF8043C74E99d5",
        "UNI": "0x636B22bC471c955A8DB60f28D4795066a8201fa3",
    },
    'scroll': {
        "USDC": "0x06eFdBFf2a14a7c8E15944D1F4A48F9F95F663A4",
        "USDT": "0xf55BEC9cafDbE8730f096Aa55dad6D22d44099Df",
        "DAI": "0xcA77eB3fEFe3725Dc33bccB54eDEFc3D9f764f97",
        "UNI": "0x434cdA25E8a2CA5D9c1C449a8Cb6bCbF719233E8",
        "AAVE": "0x79379C0E09a41d7978f883a56246290eE9a8c4d3",
        "SCR": "0xd29687c813D741E2F938F4aC377128810E217b1b",
    },
    'unichain': {
        "USDC": "0x078D782b760474a361dDA0AF3839290b0EF57AD6",
        "UNI": "0x8f187aA05619a017077f5308904739877ce9eA21",
        "DAI": "0x20CAb320A855b39F724131C69424240519573f81",
    },
}

OKX_CHAINS = {
    "ethereum": {"chain_name": "ERC20", "token_name": "ETH"},
    "arbitrum": {"chain_name": "Arbitrum One", "token_name": "ETH"},
    "optimism": {"chain_name": "Optimism", "token_name": "ETH"},
    "base": {"chain_name": "Base", "token_name": "ETH"},
    "zksync": {"chain_name": "zkSync Era", "token_name": "ETH"},
    "linea": {"chain_name": "Linea", "token_name": "ETH"},
}

BITGET_CHAINS = {
    "ethereum": {"chain_name": "ERC20", "token_name": "ETH"},
    "arbitrum": {"chain_name": "ArbitrumOne", "token_name": "ETH"},
    "optimism": {"chain_name": "Optimism", "token_name": "ETH"},
    "base": {"chain_name": "BASE", "token_name": "ETH"},
    "zksync": {"chain_name": "zkSyncEra", "token_name": "ETH"},
    "linea": {"chain_name": "NO_WITHDRAW", "token_name": "NO_WITHDRAW"},
}

BINANCE_CHAINS = {
    "ethereum": {"chain_name": "ERC20", "token_name": "ETH"},
    "arbitrum": {"chain_name": "ARBITRUM", "token_name": "ETH"},
    "optimism": {"chain_name": "OPTIMISM", "token_name": "ETH"},
    "base": {"chain_name": "BASE", "token_name": "ETH"},
    "zksync": {"chain_name": "ZKSYNCERA", "token_name": "ETH"},
    "linea": {"chain_name": "NO_WITHDRAW", "token_name": "NO_WITHDRAW"},
}

BYBIT_CHAINS = {
    "arbitrum": {"chain_name": "ARBI", "token_name": "ETH"},
    "optimism": {"chain_name": "OP", "token_name": "ETH"},
    "base": {"chain_name": "BASE", "token_name": "ETH"},
    "zksync": {"chain_name": "ZKV2", "token_name": "ETH"},
    "linea": {"chain_name": "LINEA", "token_name": "ETH"},
    "bsc": {"chain_name": "BSC", "token_name": "BNB"},
    "celo": {"chain_name": "CELO", "token_name": "CELO"},
    "moonbeam": {"chain_name": "GLMR", "token_name": "GLMR"},
    "polygon": {"chain_name": "MATIC", "token_name": "POL"},
}

BRIDGE_TYPES = {
    "Stargate Fast": {
        "module": "stargate",
        "mode": "fast",
    },
    "Stargate Cheap": {
        "module": "stargate",
        "mode": "cheap",
    },
    "Jumper Fast": {
        "module": "jumper",
        "mode": "fast",
    },
    "Jumper Cheap": {
        "module": "jumper",
        "mode": "cheap",
    },
}

LAYERZERO_CHAINS = {
    'ethereum': {'id': 30101, 'address': '0x77b2043768d28E9C9aB44E1aBfC95944bcE57931'},
    'arbitrum': {'id': 30110, 'address': '0xA45B5130f36CDcA45667738e2a258AB09f4A5f7F'},
    'optimism': {'id': 30111, 'address': '0xe8CDF27AcD73a434D661C84887215F7598e7d0d3'},
    'base': {'id': 30184, 'address': '0xdc181Bd607330aeeBEF6ea62e03e5e1Fb4B6F7C7'},
    'scroll': {'id': 30214, 'address': '0xC2b638Cb5042c1B3c5d5C969361fB50569840583'},
    'linea': {'id': 30183, 'address': '0x81F6138153d473E8c5EcebD3DC8Cd4903506B075'},
    # 'zksync': {'id': 30165, 'address': ''},
    'unichain': {'id': 30320, 'address': '0xe9aBA835f813ca05E50A6C0ce65D0D74390F7dE7'},
}
