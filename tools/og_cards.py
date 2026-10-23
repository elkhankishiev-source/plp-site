# -*- coding: utf-8 -*-
# Фирменные превью ссылок 1200×630 (09.10.2026, Эльнур: «превью ссылок страшное»). Фото проекта + название, район, цена, знак PLP.
import os, subprocess, tempfile, sys
SITE=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); CH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
D=[ # slug, фото (1 или 2), надзаголовок, название, цена, плашка
 ('cg-capital',['andaz-hd.webp'],'Central Group · Лаян и Банг Тао','Andaz и PURITA','от 7,29 млн ฿','старт продаж'),
 ('vibe2',['v2-hero.webp'],'Карон · застройщик ESM','Vibe II Downtown','от 2 968 000 ฿','старт 28 октября'),  # 16.10 №303: цена входа, не за м²; студия 28 м² (kviz, горячие_офферы)
 ('zero-naiyang',['z-ext.webp'],'Най Янг · 350 м до пляжа','The ZERO Nai Yang','от 4,94 млн ฿','гарантия 10% на 3 года'),
 ('eden',['lake-cover.webp'],'Банг Тао · третья фаза','Gardens of Eden Lake','от 11,9 млн ฿','рассрочка на 5 лет'),
 ('kuartz',['k-pool2.webp'],'Карон · 400 м до пляжа','KUARTZ','от 5 767 967 ฿','закрытый старт'),
 ('fizz',['f-pool.webp'],'Ката · 135 квартир','FIZZ','от 5 154 707 ฿','закрытый старт'),  # 17.10: 1-спальная от 5 154 707, Fizz_Price_List_3 (прайс застройщика), точная сумма без округления (Эльнур 17.10)
 ('aileen',['hero.jpg'],'Лагуна · таунхаусы 159 м²','Aileen Residence Lagoon','от 11,85 млн ฿','предстарт'),
 ('top15',['p10-ayana.webp','p02-intercontinental.webp'],'Пхукет · подборка для клиентов','Топ-15 кондо','от 2,97 млн ฿','15 проектов'),  # 22.10.2026: цена = самый низкий вход в подборке (Vibe II, список ~/plp-ops/tools/top15/sheet.json)
 ('purita',['r-og.webp'],'Банг Тао · Central Group','PURITA','от 7,29 млн ฿','новый старт'),  # 23.10.2026: старт «от 7,29 млн» из презентации застройщика 22.10 (Agent Night); лист offers/purita
 ('millennium',['hero.webp'],'Банг Тао · 750 м до пляжа','Millennium','от 3,42 млн ฿','старт 14 октября'),  # 14.10.2026: цена и дата с листа offers/millennium (прайс застройщика 13.10)
]
T='''<!doctype html><html><head><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&display=swap" rel="stylesheet">
<style>*{margin:0;box-sizing:border-box}body{width:1200px;height:630px;background:#EFECE2;font-family:Manrope,Arial,sans-serif;display:flex;overflow:hidden}
.ph{width:690px;height:630px;display:flex;flex-direction:column;gap:6px}.ph img{width:100%;flex:1;object-fit:cover;min-height:0}
.tx{flex:1;padding:46px 44px 40px;display:flex;flex-direction:column}.logo{height:46px;width:auto;align-self:flex-start}
.ey{margin-top:auto;font-size:19px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#5E6B35}
h1{font-size:{{fs}}px;line-height:1.02;font-weight:800;color:#1F1F1A;margin:12px 0 22px}
.pr{font-size:38px;font-weight:800;color:#1F1F1A}.tag{margin-top:16px;align-self:flex-start;background:#5E6B35;color:#fff;font-size:20px;font-weight:700;padding:9px 16px;border-radius:8px}
.ft{margin-top:26px;font-size:16px;color:#6B6A60;font-weight:500}</style></head><body>
<div class="ph">{{imgs}}</div><div class="tx"><img class="logo" src="plp-logo-ink.webp"><div class="ey">{{ey}}</div><h1>{{t}}</h1><div class="pr">{{p}}</div><div class="tag">{{tag}}</div><div class="ft">Property Library Phuket · для наших клиентов</div></div></body></html>'''
for slug,ph,ey,t,p,tag in D:
    if len(sys.argv)>1 and slug not in sys.argv[1:]: continue
    d=os.path.join(SITE,'offers',slug,'img')
    if not os.path.exists(os.path.join(d,'plp-logo-ink.webp')): subprocess.run(['cp',os.path.join(SITE,'offers/vibe2/img/plp-logo-ink.webp'),d])
    fs=72 if len(t)<=10 else (60 if len(t)<=18 else 50)
    html=T
    for k,v in {'fs':str(fs),'imgs':''.join('<img src="%s">'%x for x in ph),'ey':ey,'t':t,'p':p,'tag':tag}.items(): html=html.replace('{{'+k+'}}',v)
    # 10.10.2026 Эльнур: «пурита тоже фотка обрезана, сделай нормальный вид». Кадры Andaz и PURITA — широкие полосы
    # (~3:1); в колонке 690 их резало по бокам. Для двух кадров колонка фото шире, чтобы оба были видны целиком.
    if len(ph)==2: html=html.replace('</style>','.ph{width:880px}.tx{padding:38px 26px 32px}.logo{height:38px}.ey{font-size:13px;white-space:nowrap}h1{font-size:40px;margin:10px 0 16px}.pr{font-size:28px}.tag{font-size:16px;padding:7px 12px}.ft{font-size:12px;margin-top:18px}</style>')
    # 10.10.2026 Эльнур (превью Eden в Telegram): «так, как тут, ток её думаешь можно сделать чуть уже» — бежевая панель уже, фото шире.
    if slug=='cg-capital': html=html.replace('</style>','.ph{width:770px}.tx{padding:44px 36px 38px}.ey{font-size:16px;white-space:nowrap}</style>')
    f=os.path.join(d,'_og.htm'); open(f,'w',encoding='utf-8').write(html)
    png=os.path.join(tempfile.gettempdir(),'og_%s.png'%slug)
    import time
    if os.path.exists(png): os.remove(png)
    prof=tempfile.mkdtemp(); pr=subprocess.Popen([CH,'--headless=new','--disable-gpu','--hide-scrollbars','--user-data-dir='+prof,'--window-size=1200,630','--virtual-time-budget=6000','--screenshot='+png,'file://'+f],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for _ in range(60):
        time.sleep(1)
        if os.path.exists(png) and os.path.getsize(png)>10000: time.sleep(1); break
    pr.kill(); import shutil; shutil.rmtree(prof, ignore_errors=True)
    os.remove(f)
    out=os.path.join(d,'preview-v2.jpg' if slug=='top15' else 'preview-v12.jpg' if slug in ('fizz','vibe2') else ('preview-v12.jpg' if slug=='vibe2' else 'preview-v11.jpg' if slug=='kuartz' else 'preview-v10.jpg'))  # 14.10.2026: новое имя файла против кэша мессенджеров
    subprocess.run(['ffmpeg','-loglevel','error','-y','-i',png,'-q:v','3',out]); print(slug,'→',out)
