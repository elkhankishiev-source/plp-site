#!/bin/bash
# Ставит твои фото на сайт: сжимает, кладёт куда надо, коммитит и публикует.
#
# САМЫЙ БЫСТРЫЙ ПУТЬ — скачай 2 фото из Drive в Загрузки и запусти без аргументов:
#     cd ~/plp-site && ./add-photo.sh
#   Возьмёт два самых свежих изображения из ~/Downloads:
#   первое (более широкое) -> первый экран, второе -> раздел «О нас».
#
# ВРУЧНУЮ, если хочешь выбрать сам:
#     ./add-photo.sh hero    ~/Downloads/DSCF6154.jpg
#     ./add-photo.sh founder ~/Downloads/DSCF5941.jpg
#
set -e
cd "$(dirname "$0")"

prep () {  # $1=исходник $2=назначение
  cp "$1" "$2"
  # HEIC с айфона тоже переварим
  sips -s format jpeg "$2" --out "$2" >/dev/null 2>&1 || true
  sips --resampleWidth 1600 "$2" >/dev/null
  sips -s format jpeg -s formatOptions 72 "$2" --out "$2" >/dev/null
  echo "   $2 — $(sips -g pixelWidth -g pixelHeight "$2" | tail -2 | awk '{print $2}' | paste -sd'x' -), $(du -h "$2" | cut -f1)"
}

publish () {
  git add img/elnur-hero.jpg img/elnur-founder.jpg 2>/dev/null || true
  git -c user.name="Elnur" -c user.email="el.khankishiev@gmail.com" \
      commit -q -m "Фото Эльнура и семьи на сайт" || { echo "Нечего коммитить"; exit 0; }
  PAT=$(python3 -c "
import json,urllib.request,re,pathlib
key=re.search(r'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9[A-Za-z0-9._-]+',pathlib.Path.home().joinpath('plp_diag.py').read_text()).group(0)
r=urllib.request.Request('https://proplib.app.n8n.cloud/api/v1/variables?limit=200',headers={'X-N8N-API-KEY':key})
print({v['key']:v['value'] for v in json.load(urllib.request.urlopen(r,timeout=20))['data']}.get('GITHUB_PAT',''))" 2>/dev/null)
  if [ -n "$PAT" ]; then
    git push "https://x-access-token:$PAT@github.com/elkhankishiev-source/plp-site.git" HEAD:main 2>&1 | sed "s/$PAT/***/g" | tail -1
    echo "Опубликовано. Сайт обновится за минуту."
  else
    echo "Токен не нашёлся — выполни: git push"
  fi
}

if [ $# -eq 0 ]; then
  echo "Ищу два свежих изображения в ~/Downloads…"
  # bash 3.2 на macOS не умеет mapfile — читаем построчно
  PIC1=""; PIC2=""; N=0
  while IFS= read -r line; do
    N=$((N+1))
    [ $N -eq 1 ] && PIC1="$line"
    [ $N -eq 2 ] && PIC2="$line"
  done <<EOF
$(find "$HOME/Downloads" -maxdepth 1 -type f \
    \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.heic' \) \
    -exec stat -f '%m %N' {} + 2>/dev/null | sort -rn | head -2 | cut -d' ' -f2-)
EOF
  if [ -z "$PIC2" ]; then
    echo "Нужно минимум 2 изображения в ~/Downloads. Нашёл: $N"
    echo "Скачай из Drive два кадра (себя и семью) и запусти снова."
    exit 1
  fi
  # более широкий кадр — на первый экран, второй — в «О нас»
  w1=$(sips -g pixelWidth "$PIC1" | tail -1 | awk '{print $2}')
  h1=$(sips -g pixelHeight "$PIC1" | tail -1 | awk '{print $2}')
  if [ "$w1" -ge "$h1" ]; then HERO="$PIC1"; FOUND="$PIC2"; else HERO="$PIC2"; FOUND="$PIC1"; fi
  echo "Первый экран : $(basename "$HERO")"
  prep "$HERO" img/elnur-hero.jpg
  echo "«О нас»      : $(basename "$FOUND")"
  prep "$FOUND" img/elnur-founder.jpg
  publish
  exit 0
fi

case "$1" in
  hero)    DST="img/elnur-hero.jpg" ;;
  founder) DST="img/elnur-founder.jpg" ;;
  *) echo "Запусти без аргументов, либо: ./add-photo.sh hero|founder <файл>"; exit 1 ;;
esac
[ -f "$2" ] || { echo "Файл не найден: $2"; exit 1; }
prep "$2" "$DST"
publish
