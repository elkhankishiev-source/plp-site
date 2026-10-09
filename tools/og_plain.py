# -*- coding: utf-8 -*-
# Превью ссылок объектов = чистое фото 1200×630, настоящий JPEG (10.10.2026).
# Эльнур: «убери вообще всякие оттуда картинки» — без надписей и знака. Проверяльщик: 53 из 152 файлов img/<код>.jpg
# на деле WebP, размеры в og:image врали, WhatsApp такие не рисует. Делаем img/og/photo-<код>.jpg из кадра объекта:
# только недостающие или если кадр новее. Ничего не удаляем.
import os, glob, subprocess
SITE = os.path.expanduser('~/plp-site'); OUT = os.path.join(SITE, 'img', 'og'); os.makedirs(OUT, exist_ok=True)
n = 0
for src in sorted(glob.glob(os.path.join(SITE, 'img', 'PLP-*.jpg'))):
    dst = os.path.join(OUT, 'photo-' + os.path.basename(src))
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        continue
    r = subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', src, '-vf',
                        'scale=1200:630:force_original_aspect_ratio=increase,crop=1200:630', '-q:v', '3', dst])
    if r.returncode == 0: n += 1
print('превью объектов: новых', n)
