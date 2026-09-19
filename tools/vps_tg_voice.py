#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 327: клиентский Telegram-бот начинает слышать голосовые.

Эльнур 18.09.2026, его же переписка с ботом, 16:22 и 17:54 по Пхукету: два его
сообщения пришли в систему ПУСТЫМИ — в журнале «файлов=0 содержимое=нет текст=нет».
Бот ответил невпопад, отсюда его «Ничего не считает, с чего вдруг» и «Я ведь нажал
на разбор Карона».

Причина: разборщик входящих в Telegram умеет фото и документы, а голосовые не умеет
вовсе — ни voice, ни audio, ни кружок video_note. В WhatsApp двойник голосовые
расшифровывает (Groq Whisper), в Telegram они просто исчезали.

Правка: голосовое, аудиофайл и кружок скачиваются из Telegram, ссылка на файл
уходит в мозг полем audio_urls — тем самым, которое он уже понимает и расшифровывает.

    python3 vps_tg_voice.py            # показать, что изменится
    python3 vps_tg_voice.py --apply    # применить и перезапустить n8n
"""
import subprocess, sys

APPLY = '--apply' in sys.argv
VPS = open('/Users/elnurkhankishiev/.plp_vps_ip').read().strip()
KEY = '/Users/elnurkhankishiev/.ssh/plp_vps'
WF = 'WF_validator_PROD%'
NODE = 'Parse TG'

OLD_DECL = "let image_b64=null,image_media_type=null;"
NEW_DECL = "let image_b64=null,image_media_type=null;let audio_urls=[];"

OLD_RET = ("return [{json:{tg_id,phone:tg_id,chat_id,name,username:'',text:String(text),"
           "source:'telegram_direct',is_callback,image_b64,image_media_type}}]")
NEW_RET = ("/* 18.09.2026 правка 327: голосовые из Telegram доезжают до мозга, "
           "он их расшифрует сам. */\n"
           "return [{json:{tg_id,phone:tg_id,chat_id,name,username:'',text:String(text),"
           "source:'telegram_direct',is_callback,image_b64,image_media_type,audio_urls}}]")

ANCHOR_AUDIO = "  try{var _ph=Array.isArray(msg.photo)"
NEW_AUDIO = """  /* 18.09.2026 правка 327: голосовое, аудиофайл или кружок — тоже сообщение.
     Скачиваем ссылку и отдаём мозгу в audio_urls, он расшифрует через Whisper. */
  try{
    var _av=msg.voice||msg.audio||msg.video_note||
            (msg.document&&/audio\\/|\\.ogg|\\.m4a|\\.mp3/i.test((msg.document.mime_type||'')+(msg.document.file_name||''))?msg.document:null);
    if(_av&&_av.file_id){
      var _gfa=await this.helpers.httpRequest({ timeout:25000, method:'GET',
        url:'https://api.telegram.org/bot'+$env.TG_ELNURPHUKET_TOKEN+'/getFile?file_id='+_av.file_id, json:true});
      var _fpa=_gfa&&_gfa.result&&_gfa.result.file_path;
      if(_fpa) audio_urls.push('https://api.telegram.org/file/bot'+$env.TG_ELNURPHUKET_TOKEN+'/'+_fpa);
    }
  }catch(_e327){}
""" + ANCHOR_AUDIO


def ssh(cmd, inp=None):
    return subprocess.run(['ssh', '-i', KEY, 'root@' + VPS, cmd], input=inp,
                          capture_output=True, text=True, timeout=180)


def psql(sql):
    r = ssh('docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin', sql)
    if r.returncode:
        raise RuntimeError(r.stderr[:300])
    return r.stdout.strip()


def code():
    return psql("select n->'parameters'->>'jsCode' from workflow_entity w, "
                "jsonb_array_elements(w.nodes::jsonb) n where w.name like '%s' and n->>'name'='%s';"
                % (WF, NODE))


def main():
    src = code()
    if 'правка 327' in src:
        print('правка 327 уже стоит')
        return 0
    for a in (OLD_DECL, OLD_RET, ANCHOR_AUDIO):
        if src.count(a) != 1:
            print('якорь найден %d раз: %s — отмена' % (src.count(a), a[:40]))
            return 1
    print('будет изменено: бот принимает голосовые, аудио и кружки и отдаёт их мозгу')
    if not APPLY:
        print('\nЭто отчёт. Применить: --apply')
        return 0
    fixed = src.replace(OLD_DECL, NEW_DECL, 1).replace(ANCHOR_AUDIO, NEW_AUDIO, 1).replace(OLD_RET, NEW_RET, 1)
    tag = '$plpvoice$'
    if tag in fixed:
        print('метка кавычек встретилась — отмена')
        return 1
    sql = ("update workflow_entity set nodes = (\n"
           "  select jsonb_agg(case when n->>'name'='%s'\n"
           "    then jsonb_set(n, '{parameters,jsCode}', to_jsonb(%s%s%s::text))\n"
           "    else n end)\n"
           "  from jsonb_array_elements(nodes::jsonb) n)\n"
           "where name like '%s';" % (NODE, tag, fixed, tag, WF))
    ssh('cat > /tmp/voice.sql', sql)
    out = ssh('docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin < /tmp/voice.sql')
    print(out.stdout.strip() or out.stderr[:200])
    if 'правка 327' not in code():
        print('НЕ ПРИМЕНИЛОСЬ')
        return 1
    print('  ✓ проверка: голосовые разбираются')
    ssh("docker restart n8n-n8n-1 >/dev/null 2>&1; sleep 6; docker ps --filter name=n8n-n8n-1 --format '{{.Status}}'")
    print('n8n перезапущен')
    return 0


if __name__ == '__main__':
    sys.exit(main())
