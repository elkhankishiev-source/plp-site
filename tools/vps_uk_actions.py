#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Врезка в кабинет-сервер: договор, публикация, шаблон, новые виды заявок.

Эльнур 17.09.2026: «он может выбрать любой объект и поэтапно пройти путь к подписанию
контракта с УК, выгрузить объект в блок аренда… всё должно быть подвязано, единое».

Что добавляет в /opt/plp-api/ukowner.mjs:
  • виды заявок rent_start («хочу сдавать через вас») и uk_contract («договор с УК») —
    раньше их не было, и настоящая заявка «СДАТЬ В АРЕНДУ» легла видом «перепродажа»;
  • действие uk_contract — запись подписанного договора (штаб), шаг 1 лестницы;
  • действие uk_publish — публикация на витрине ТОЛЬКО через uk_ready;
  • действие uk_template — выдаёт образец договора из хранилища по временной ссылке.
    До этого кнопка «Взять шаблон и подписать» всегда отвечала «попросите в офисе»:
    переменная со ссылкой была объявлена пустой и нигде не заполнялась.

Запуск на сервере: python3 vps_uk_actions.py  (делает резервную копию рядом).
"""
import datetime, os, re, shutil, sys

SRC = '/opt/plp-api/ukowner.mjs'

KINDS_OLD = "  const allowed = ['cleaning', 'repair', 'block_dates', 'payout', 'resale', 'other'];"
KINDS_NEW = ("  /* 17.09: «хочу сдавать через вас» и «договор с УК» — отдельные виды.\n"
             "     Без них заявка с текстом «СДАТЬ В АРЕНДУ» легла видом «перепродажа». */\n"
             "  const allowed = ['cleaning', 'repair', 'block_dates', 'payout', 'resale',\n"
             "                   'rent_start', 'uk_contract', 'other'];")

RU_OLD = """    const KINDS_RU = { cleaning: 'Уборка', repair: 'Ремонт или поломка',
      block_dates: 'Блокировка дат', payout: 'Вопрос по выплате', other: 'Обращение' };"""
RU_NEW = """    const KINDS_RU = { cleaning: 'Уборка', repair: 'Ремонт или поломка',
      block_dates: 'Блокировка дат', payout: 'Вопрос по выплате',
      rent_start: 'Хочу сдавать через вас', uk_contract: 'Договор управления',
      resale: 'Перепродажа', other: 'Обращение' };"""

ANCHOR = """/* что мы поняли из документов объекта */
if (action === 'uk_doc_files') {"""

BLOCK = """/* Договор управления: запись подписанного в систему. Раньше строку в uk_contracts
   нельзя было создать ниоткуда — ни одной функции записи во всей системе, только
   чтение из восьми мест. Поэтому шаг 1 лестницы не зеленел ни у кого. */
if (action === 'uk_contract') {
  return [{ json: await rpc.call(this, 'uk_contract_set', {
    p_token: token, p_property: String(b.property_id || ''),
    p_owner_name: b.owner_name || null, p_owner_phone: b.owner_phone || null,
    p_owner_email: b.owner_email || null, p_rental_type: b.rental_type || 'mixed',
    p_short: b.commission_short == null ? null : Number(b.commission_short),
    p_long: b.commission_long == null ? null : Number(b.commission_long),
    p_start: b.start_date || null, p_end: b.end_date || null,
    p_status: b.status || 'active', p_payout: b.payout_details || null }) }];
}
/* Публикация на витрине спрашивает лестницу uk_ready, а не делается правкой базы.
   Эльнур: «я сверяю, апрувлю, объект уходит в блок аренда и его видно на сайте». */
if (action === 'uk_publish') {
  return [{ json: await rpc.call(this, 'uk_publish', {
    p_token: token, p_property: String(b.property_id || ''),
    p_on: b.on === false ? false : true }) }];
}
/* Образец договора управления — временная ссылка на файл в приватном хранилище.
   Ссылку не зашиваем в страницу: owner.html лежит в публичном репозитории. */
if (action === 'uk_template') {
  const s = await rpc.call(this, 'owner_session', { p_token: token });
  if (!s || !s.ok) return [{ json: { ok: false, error: 'no_session' } }];
  const want = String(b.format || 'pdf') === 'docx' ? 'docx' : 'pdf';
  const key = 'templates/plp-management-agreement.' + want;
  try {
    const r = await this.helpers.httpRequest({ timeout: 20000, method: 'POST',
      url: $vars.SUPABASE_URL + '/storage/v1/object/sign/client-docs/' + key,
      headers: HJ, body: { expiresIn: 60 * 60 * 24 * 7 }, json: true });
    const rel = (r && (r.signedURL || r.signedUrl)) || '';
    if (!rel) return [{ json: { ok: false, error: 'образец не найден' } }];
    return [{ json: { ok: true, url: $vars.SUPABASE_URL + '/storage/v1' + rel,
                      name: 'Договор управления PLP (' + want.toUpperCase() + ')' } }];
  } catch (e) { return [{ json: { ok: false, error: 'образец не отдался' } }]; }
}
""" + ANCHOR


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'uk_contract_set' in src:
        print('врезка уже стоит — ничего не меняю')
        return 0
    for old, new, what in ((KINDS_OLD, KINDS_NEW, 'виды заявок'),
                           (RU_OLD, RU_NEW, 'названия видов'),
                           (ANCHOR, BLOCK, 'действия договора, публикации и образца')):
        if old not in src:
            print('НЕ НАЙДЕНО: %s — врезка отменена' % what)
            return 1
        src = src.replace(old, new, 1)
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    open(SRC, 'w', encoding='utf-8').write(src)
    print('врезано; резервная копия: %s' % bak)
    return 0


if __name__ == '__main__':
    sys.exit(main())
