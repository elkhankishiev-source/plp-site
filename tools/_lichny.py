# 20.10.2026: личный номер Эльнура в публичный репозиторий не пишем (го Эльнура 20.10).
# Он лежит вне репозитория: переменная PLP_LICHNY или файл ~/plp-ops/свои_номера_личный.txt (закрытый репозиторий, первая строка).
import os


def _прочитать():
    v = os.environ.get('PLP_LICHNY', '').strip()
    if not v:
        try:
            v = open(os.path.expanduser('~/plp-ops/свои_номера_личный.txt'), encoding='utf-8').readline().strip()
        except OSError:
            v = ''
    return v


ЛИЧНЫЙ = _прочитать()            # 11 цифр с кодом страны
ЛИЧНЫЙ9 = ЛИЧНЫЙ[-9:] if ЛИЧНЫЙ else ''   # без кода страны
