# -*- coding: utf-8 -*-
# Фирменные превью ссылок 1200×630 (09.10.2026, Эльнур: «превью ссылок страшное»). Фото проекта + название, район, цена, знак PLP.
import os, subprocess, tempfile, sys
SITE=os.path.expanduser('~/plp-site'); CH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
D=[ # slug, фото (1 или 2), надзаголовок, название, цена, плашка
 ('cg-capital',['andaz-clean.webp','purita-clean.webp'],'Central Group · Лаян и Банг Тао','Andaz и PURITA','от 7,xx млн ฿','старт продаж'),
 ('vibe2',['v1-cover-hd.webp'],'Карон · застройщик ESM','Vibe II Downtown','от 3,2 млн ฿','старт 28 октября'),
 ('zero-naiyang',['z-ext.webp'],'Най Янг · 350 м до пляжа','The ZERO Nai Yang','от 4,94 млн ฿','гарантия 10% на 3 года'),
 ('eden',['lake-cover.webp'],'Банг Тао · третья фаза','Gardens of Eden Lake','от 11,9 млн ฿','рассрочка на 5 лет'),
 ('kuartz',['k-pool2.webp'],'Карон · 400 м до пляжа','KUARTZ','≈140 тыс. ฿ за м²','закрытый старт'),
 ('fizz',['f-pool.webp'],'Ката · камерный дом','FIZZ','≈130 тыс. ฿ за м²','закрытый старт'),
 ('aileen',['hero.jpg'],'Лагуна · таунхаусы 159 м²','Aileen Residence Lagoon','от 11,85 млн ฿','предстарт'),
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
    out=os.path.join(d,'preview.jpg')
    subprocess.run(['ffmpeg','-loglevel','error','-y','-i',png,'-q:v','3',out]); print(slug,'→',out)
