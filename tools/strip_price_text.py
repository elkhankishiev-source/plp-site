# -*- coding: utf-8 -*-
"""Цена живёт в одном месте — в поле карточки. Из описаний её убираем:
прайс меняется каждую неделю, а текст остаётся и начинает врать."""
import json, os, re, sys, urllib.request
env={}
for l in open(os.path.expanduser('~/.plp_site_supabase.env')):
    if '=' in l and not l.strip().startswith('#'):
        k,v=l.strip().split('=',1); env[k]=v.strip().strip('"').strip("'")
KEY=env['SUPABASE_SERVICE_KEY']; URL=env['SUPABASE_URL'].rstrip('/')
APPLY='--apply' in sys.argv
PRICE = re.compile(r'(цен\w*|стоимост\w*|price[sd]?|from|start\w*)[^.;,]{0,25}?\d[\d\s.,]{2,}\s*(млн|миллион\w*|m\b|thb|бат\w*|฿)', re.I)
BARE  = re.compile(r'^\s*(from|prices? from|от)\s+[\d.,\s]+(m|млн|миллион\w*|thb|бат\w*|฿)\.?\s*$', re.I)

def clean(text):
    if not text: return text
    out=[]
    for sent in re.split(r'(?<=[.;])\s+', text):
        if not sent.strip(): continue
        if BARE.match(sent):
            continue                      # предложение целиком про цену — убираем
        if PRICE.search(sent):
            # режем только кусок про цену: «Старт цен — от X, завершение в 2028» →
            # «Завершение в 2028». Остальное предложение живёт дальше.
            parts=[c for c in re.split(r',\s*', sent) if not PRICE.search(c)]
            parts=[c for c in parts if len(re.sub(r'\W','',c))>8]
            sent=', '.join(parts).strip().rstrip('.;') 
            if not sent: continue
            sent=sent[0].upper()+sent[1:]+'.'
        out.append(sent.strip())
    return ' '.join(out)

req=urllib.request.Request(URL+"/rest/v1/objects?select=plp_property_id,usp,usp_en&on_site=eq.true",
    headers={'apikey':KEY,'Authorization':'Bearer '+KEY})
rows=json.loads(urllib.request.urlopen(req,timeout=90).read())
n=0
for o in rows:
    body={}
    for f in ('usp','usp_en'):
        t=o.get(f) or ''
        c=clean(t)
        if c!=t:
            body[f]=c
            old=[s for s in re.split(r'(?<=[.;])\s+',t) if PRICE.search(s) or BARE.match(s)]
            print('%-20s [%s] убрано: %s'%(o['plp_property_id'],f,' | '.join(x.strip()[:110] for x in old)))
    if body and APPLY:
        r=urllib.request.Request(URL+'/rest/v1/objects?plp_property_id=eq.'+o['plp_property_id'],
            data=json.dumps(body,ensure_ascii=False).encode(),method='PATCH',
            headers={'apikey':KEY,'Authorization':'Bearer '+KEY,'Content-Type':'application/json','Prefer':'return=minimal'})
        urllib.request.urlopen(r,timeout=60)
    n+=1 if body else 0
print('\nкарточек с ценой в тексте: %d%s'%(n,' — записано' if APPLY else ' (черновик, без --apply)'))
