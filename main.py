from modules.utils import sleeping, logger, sleep, choose_mode
from modules.retry import DataBaseError, SoftError
from modules.config import BRIDGE_TYPES
from modules import *
import settings


def check_for_settings():
    for bridge_type in settings.BRIDGE_PARAMS["available_bridges"]:
        if bridge_type not in BRIDGE_TYPES:
            raise SoftError(f'Unsupported bridge type `{bridge_type}`')


def run_modules():
    while True:
        print('')
        try:
            module_data = db.get_random_module()
            if module_data == 'No more accounts left':
                logger.success(f'All accounts done.')
                return 'Ended'

            browser = Browser(db=db, encoded_pk=module_data["encoded_privatekey"], proxy=module_data["proxy"])
            wallet = Wallet(
                privatekey=module_data["privatekey"],
                encoded_pk=module_data["encoded_privatekey"],
                browser=browser,
                db=db,
                recipient=module_data["recipient"],
            )
            browser.address = wallet.address
            logger.info(f'[•] Web3 | {wallet.address}')

            bridger = Bridger(wallet=wallet)

            module_data["module_info"]["status"] = bridger.run()

        except Exception as err:
            logger.error(f'[-] Web3 | Account error: {err}')
            db.append_report(privatekey=wallet.encoded_pk, text=str(err), success=False)

        finally:
            if type(module_data) == dict:
                db.remove_module(module_data=module_data)

                if module_data['last']:
                    reports = db.get_account_reports(privatekey=wallet.encoded_pk)
                    TgReport().send_log(logs=reports)

                if module_data["module_info"]["status"] is True: sleeping(settings.SLEEP_AFTER_ACC)
                else: sleeping(10)


if __name__ == '__main__':
    try:
        db = DataBase()

        while True:
            mode = choose_mode()

            match mode:
                case None: break

                case 'Delete and create new':
                    db.create_modules()

                case 1:
                    check_for_settings()
                    if run_modules() == 'Ended': break
                    print('')

        sleep(0.1)
        input('\n > Exit\n')

    except DataBaseError as e:
        logger.error(f'[-] Database | {e}')

    except SoftError as e:
        logger.error(f'[-] Soft | {e}')

    except KeyboardInterrupt:
        pass

    finally:
        logger.info('[•] Soft | Closed')
