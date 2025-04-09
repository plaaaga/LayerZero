
SHUFFLE_WALLETS     = True                  # True | False - перемешивать ли кошельки
RETRY               = 3                     # кол-во попыток при ошибках / фейлах

ETH_MAX_GWEI        = 20
GWEI_MULTIPLIER     = 1.05                  # умножать текущий гвей при отправке транз на 5%
TO_WAIT_TX          = 1                     # сколько минут ожидать транзакцию. если транза будет находится в пендинге после указанного времени то будет считатся зафейленной

RPCS                = {
    'ethereum'  : 'https://eth.drpc.org',
    'arbitrum'  : 'https://arbitrum.drpc.org',
    'optimism'  : 'https://optimism.drpc.org',
    'base'      : 'https://base.drpc.org',
    'linea'     : 'https://rpc.linea.build',
    'scroll'    : 'https://rpc.scroll.io',
    'unichain'  : 'https://unichain.drpc.org',
}


# --- ONCHAIN SETTINGS ---
SLEEP_AFTER_TX      = [10, 20]              # задержка после каждой транзы 10-20 секунд
SLEEP_AFTER_ACC     = [20, 40]              # задержка после каждого аккаунта 20-40 секунд


WITHDRAW_PARAMS     = {
    "exchange"              : ["Binance", "OKX"],    # с какой биржи выводить ETH (Bybit | OKX | Bitget | Binance)
    "withdraw_range"        : [0.01, 0.02], # выводить от 0.01 ETH до 0.02 ETH
    "chains"                : [             # в какие сети можно выводить с бирж (то есть какая сеть будет первой для бриджа)
        'arbitrum',
        'optimism',
        'base',
    ]
}

BRIDGE_PARAMS       = {
    "bridges_amount"        : [3, 5],       # от скольки до скольки бриджей нужно делать за раз
    "keep_amounts"          : {             # сети в которые не хотите бриджить - закомментите
        'arbitrum'          : [0.0001, 0.00016], # сколько ETH оставлять в этой сети
        'optimism'          : [0.0001, 0.00016],
        'base'              : [0.0001, 0.00016],
        'linea'             : [0.0001, 0.00016],
        'scroll'            : [0.0001, 0.00016],
        'unichain'          : [0.0001, 0.00016],
    },
    "last_chains"           : [             # какие сети могут быть последними, в которые бриджить (то есть из какой сети можно депать обратно на биржу)
        'arbitrum',
        'optimism',
        'base',
    ],
    "available_bridges"     : [             # какие бриджи может делать софт
        "Stargate Fast",                    # Fast - быстрый режим (дороже)
        "Stargate Cheap",                   # Cheap - дешевый режим (медленнее)
        "Jumper Fast",
        "Jumper Cheap",
    ],
    "max_stargate_fee"      : 0.0002        # максимальная комиссия протокола 0.0002. если выше - скипает
}

SWAP_PARAMS         = {                     # настройки свапов (после бриджа в рандомную сеть)
    "swap_amount"           : [0, 2],       # делать от 0 до 2 свапов после бриджа (0 - не делать свап)

    "amounts"               : [0.0001, 0.001], # свапать от 0.0001 до 0.001 ETH в рандомный токен | укажите [0, 0] что бы использовать проценты
    "percents"              : [20, 50],     # свапать от 20% до 50% баланса ETH в рандомный токен
    "percent_back"          : [100, 100],   # свапать обратно из токена в ETH от 100% до 100% баланса этого токена  | [0, 0] что бы не свапать обратно

    "chains_swap"           : {
        'arbitrum'          : [
            {
                "swap_name"     : "uniswap",
                "tokens_to_swap": ["USDC", "USDT", "ARB", "ZRO"],
            },
        ],
        'optimism'          : [
            {
                "swap_name"     : "uniswap",
                "tokens_to_swap": ["USDC", "USDT", "OP", "ZRO"],
            },
        ],
        'base'              : [
            {
                "swap_name"     : "uniswap",
                "tokens_to_swap": ["USDC", "TOSHI", "ZRO"],
            },
        ],
        'linea'             : [
            {
                "swap_name"     : "odos",
                "tokens_to_swap": ["USDC", "USDT", "DAI", "SHIB", "UNI"],
            },
        ],
        'scroll'            : [
            {
                "swap_name"     : "odos",
                "tokens_to_swap": ["USDC", "USDT", "DAI", "SCR"],
            },
        ],
        'unichain'          : [
            {
                "swap_name"     : "uniswap",
                "tokens_to_swap": ["USDC", "UNI", "DAI"],
            },
        ],
    }
}


# --- PERSONAL SETTINGS ---

OKX_API_KEY         = ''
OKX_API_SECRET      = ''
OKX_API_PASSWORD    = ''

BYBIT_KEY           = ''
BYBIT_SECRET        = ''

BITGET_KEY          = ''
BITGET_SECRET       = ''
BITGET_PASSWORD     = ''

BINANCE_KEY         = ''
BINANCE_SECRET      = ''

PROXY_TYPE          = "mobile"              # "mobile" - для мобильных/резидентских прокси, указанных ниже | "file" - для статичных прокси из файла `proxies.txt`
PROXY               = 'http://log:pass@ip:port' # что бы не использовать прокси - оставьте как есть
CHANGE_IP_LINK      = 'https://changeip.mobileproxy.space/?proxy_key=...&format=json'

TG_BOT_TOKEN        = ''                    # токен от тг бота (`12345:Abcde`) для уведомлений. если не нужно - оставляй пустым
TG_USER_ID          = []                    # тг айди куда должны приходить уведомления.