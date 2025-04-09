from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode
from os import path, mkdir
from random import choice
from hashlib import md5
from time import sleep
import json

from modules.utils import logger, get_address, WindowName
from modules.retry import DataBaseError
from settings import (
    SHUFFLE_WALLETS,
    PROXY_TYPE
)

from cryptography.fernet import InvalidToken


class DataBase:
    def __init__(self):

        self.modules_db_name = 'databases/modules.json'
        self.report_db_name = 'databases/report.json'
        self.personal_key = None
        self.window_name = None

        # create db's if not exists
        if not path.isdir(self.modules_db_name.split('/')[0]):
            mkdir(self.modules_db_name.split('/')[0])

        for db_params in [
            {"name": self.modules_db_name, "value": "[]"},
            {"name": self.report_db_name, "value": "{}"},
        ]:
            if not path.isfile(db_params["name"]):
                with open(db_params["name"], 'w') as f: f.write(db_params["value"])

        amounts = self.get_amounts()
        logger.info(f'Loaded {amounts["modules_amount"]} modules for {amounts["accs_amount"]} accounts\n')


    def set_password(self):
        if self.personal_key is not None: return

        logger.debug(f'Enter password to encrypt privatekeys (empty for default):')
        raw_password = input("")

        if not raw_password:
            raw_password = "@karamelniy dumb shit encrypting"
            logger.success(f'[+] Soft | You set empty password for Database\n')
        else:
            print(f'')
        sleep(0.2)

        password = md5(raw_password.encode()).hexdigest().encode()
        self.personal_key = Fernet(urlsafe_b64encode(password))


    def get_password(self):
        if self.personal_key is not None: return

        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)
        if not modules_db: return

        try:
            temp_key = Fernet(urlsafe_b64encode(md5("@karamelniy dumb shit encrypting".encode()).hexdigest().encode()))
            self.decode_pk(pk=list(modules_db.keys())[0], key=temp_key)
            self.personal_key = temp_key
            return
        except InvalidToken: pass

        while True:
            try:
                logger.debug(f'Enter password to decrypt your privatekeys (empty for default):')
                raw_password = input("")
                password = md5(raw_password.encode()).hexdigest().encode()

                temp_key = Fernet(urlsafe_b64encode(password))
                self.decode_pk(pk=list(modules_db.keys())[0], key=temp_key)
                self.personal_key = temp_key
                logger.success(f'[+] Soft | Access granted!\n')
                return

            except InvalidToken:
                logger.error(f'[-] Soft | Invalid password\n')


    def encode_pk(self, pk: str, key: None | Fernet = None):
        if key is None:
            return self.personal_key.encrypt(pk.encode()).decode()
        return key.encrypt(pk.encode()).decode()


    def decode_pk(self, pk: str, key: None | Fernet = None):
        if key is None:
            return self.personal_key.decrypt(pk).decode()
        return key.decrypt(pk).decode()

    def create_modules(self):
        self.set_password()

        with open('input_data/privatekeys.txt') as f: private_keys = f.read().splitlines()
        with open('input_data/recipients.txt') as f: recipients = f.read().splitlines()

        if len(recipients) != len(private_keys):
            raise DataBaseError(f'Amount of privatekeys ({len(private_keys)}) must be same as amount of recipients ({len(recipients)})')

        if PROXY_TYPE == "file":
            with open('input_data/proxies.txt') as f:
                proxies = f.read().splitlines()
            if len(proxies) == 0 or proxies == [""] or proxies == ["http://login:password@ip:port"]:
                logger.error('You will not use proxy')
                proxies = [None for _ in range(len(private_keys))]
            else:
                proxies = list(proxies * (len(private_keys) // len(proxies) + 1))[:len(private_keys)]
        elif PROXY_TYPE == "mobile":
            proxies = ["mobile" for _ in range(len(private_keys))]

        with open(self.report_db_name, 'w') as f: f.write('{}')  # clear report db

        new_modules = {
            self.encode_pk(pk): {
                "address": get_address(pk),
                "modules": [{"module_name": "bridges", "status": "to_run"}],
                "proxy": proxy,
                "recipient": recip,
            }
            for pk, proxy, recip in zip(private_keys, proxies, recipients)
        }

        with open(self.modules_db_name, 'w', encoding="utf-8") as f: json.dump(new_modules, f)

        amounts = self.get_amounts()
        logger.critical(f'Dont Forget To Remove Private Keys from privatekeys.txt!')
        logger.info(f'Created Database for {amounts["accs_amount"]} accounts with {amounts["modules_amount"]} modules!\n')

    def get_amounts(self):
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)
        modules_len = sum([len(modules_db[acc]["modules"]) for acc in modules_db])

        for acc in modules_db:
            for index, module in enumerate(modules_db[acc]["modules"]):
                if module["status"] in ["failed", "cloudflare"]: modules_db[acc]["modules"][index]["status"] = "to_run"

        with open(self.modules_db_name, 'w', encoding="utf-8") as f: json.dump(modules_db, f)

        if self.window_name == None: self.window_name = WindowName(accs_amount=len(modules_db))
        else: self.window_name.accs_amount = len(modules_db)
        self.window_name.set_modules(modules_amount=modules_len)

        return {'accs_amount': len(modules_db), 'modules_amount': modules_len}

    def get_random_module(self):
        self.get_password()

        last = False
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)

        if (
                not modules_db or
                (
                        [module["status"] for acc in modules_db for module in modules_db[acc]["modules"]].count('to_run') == 0 and
                        [module["status"] for acc in modules_db for module in modules_db[acc]["modules"]].count('cloudflare') == 0
                )
        ):
                return 'No more accounts left'

        index = 0
        while True:
            if index == len(modules_db.keys()) - 1: index = 0
            if SHUFFLE_WALLETS: privatekey = choice(list(modules_db.keys()))
            else: privatekey = list(modules_db.keys())[index]
            module_info = choice(modules_db[privatekey]["modules"])
            if module_info["status"] not in ["to_run", "cloudflare"]:
                index += 1
                continue

            # simulate db
            for module in modules_db[privatekey]["modules"]:
                if module["module_name"] == module_info["module_name"] and module["status"] == module_info["status"]:
                    modules_db[privatekey]["modules"].remove(module)
                    break

            if [module["status"] for module in modules_db[privatekey]["modules"]].count('to_run') == 0: # if no modules left for this account
                last = True

            return {
                'privatekey': self.decode_pk(pk=privatekey),
                'encoded_privatekey': privatekey,
                'recipient': modules_db[privatekey].get("recipient"),
                'proxy': modules_db[privatekey].get("proxy"),
                'module_info': module_info,
                'last': last
            }

    def remove_module(self, module_data: dict):
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)

        for index, module in enumerate(modules_db[module_data["encoded_privatekey"]]["modules"]):
            if module["module_name"] == module_data["module_info"]["module_name"] and module["status"] in ["to_run", "cloudflare"]:
                self.window_name.add_module()

                if module_data["module_info"]["status"] in [True, "completed"]:
                    modules_db[module_data["encoded_privatekey"]]["modules"].remove(module)
                elif module_data["module_info"]["status"] == "cloudflare":
                    modules_db[module_data["encoded_privatekey"]]["modules"][index]["status"] = "cloudflare"
                else:
                    modules_db[module_data["encoded_privatekey"]]["modules"][index]["status"] = "failed"
                break

        if [module["status"] for module in modules_db[module_data["encoded_privatekey"]]["modules"]].count('to_run') == 0 and \
                [module["status"] for module in modules_db[module_data["encoded_privatekey"]]["modules"]].count('cloudflare') == 0:
            self.window_name.add_acc()
        if not modules_db[module_data["encoded_privatekey"]]["modules"]:
            del modules_db[module_data["encoded_privatekey"]]

        with open(self.modules_db_name, 'w', encoding="utf-8") as f: json.dump(modules_db, f)

    def remove_account(self, module_data: dict):
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)

        if module_data["module_info"]["status"] in [True, "completed"]:
            del modules_db[module_data["encoded_privatekey"]]
            self.window_name.add_acc()

            with open(self.modules_db_name, 'w', encoding="utf-8") as f: json.dump(modules_db, f)

    def add_bridge_data(self, encoded_pk: str, chain: str, amount: float):
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)

        if not modules_db[encoded_pk].get('bridge_data'):
            modules_db[encoded_pk]['bridge_data'] = {}

        if not modules_db[encoded_pk]['bridge_data'].get(chain):
            modules_db[encoded_pk]['bridge_data'][chain] = 0
        modules_db[encoded_pk]['bridge_data'][chain] += amount

        with open(self.modules_db_name, 'w', encoding="utf-8") as f: json.dump(modules_db, f)

    def get_bridge_data(self, encoded_pk: str):
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)
        return modules_db[encoded_pk]['bridge_data']

    def append_report(self, privatekey: str, text: str, success: bool = None):
        status_smiles = {True: '✅ ', False: "❌ ", None: ""}

        with open(self.report_db_name, encoding="utf-8") as f: report_db = json.load(f)

        if not report_db.get(privatekey): report_db[privatekey] = {'texts': [], 'success_rate': [0, 0]}

        report_db[privatekey]["texts"].append(status_smiles[success] + text)
        if success != None:
            report_db[privatekey]["success_rate"][1] += 1
            if success == True: report_db[privatekey]["success_rate"][0] += 1

        with open(self.report_db_name, 'w') as f: json.dump(report_db, f)

    def get_account_reports(self, privatekey: str, get_rate: bool = False):
        with open(self.report_db_name, encoding="utf-8") as f: report_db = json.load(f)

        decoded_privatekey = self.decode_pk(pk=privatekey)
        account_index = f"[{self.window_name.accs_done}/{self.window_name.accs_amount}]"
        if report_db.get(privatekey):
            account_reports = report_db[privatekey]
            if get_rate: return f'{account_reports["success_rate"][0]}/{account_reports["success_rate"][1]}'
            del report_db[privatekey]

            with open(self.report_db_name, 'w', encoding="utf-8") as f: json.dump(report_db, f)

            logs_text = '\n'.join(account_reports['texts'])
            tg_text = f'{account_index} <b>{get_address(pk=decoded_privatekey)}</b>\n\n{logs_text}'
            if account_reports["success_rate"][1]:
                tg_text += f'\n\nSuccess rate {account_reports["success_rate"][0]}/{account_reports["success_rate"][1]}'

            return tg_text

        else:
            return f'{account_index} <b>{get_address(pk=decoded_privatekey)}</b>\n\nNo actions'
