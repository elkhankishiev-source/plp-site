#!/bin/bash
# Ставит фото человека на сайт: сжимает до 1600px, кладёт под нужным именем,
# коммитит и публикует. Градиентная заглушка исчезает сама, как только файл появился.
#
#   ./add-photo.sh hero    ~/Downloads/DSCF6154.jpg     # большое фото справа на первом экране
#   ./add-photo.sh founder ~/Downloads/DSCF5941.jpg     # портрет в разделе «О нас»
#
set -e
cd "$(dirname "$0")"

SLOT="$1"; SRC="$2"
case "$SLOT" in
  hero)    DST="img/elnur-hero.jpg";    WHAT="первый экран" ;;
  founder) DST="img/elnur-founder.jpg"; WHAT="раздел «О нас»" ;;
  *) echo "Укажи слот: hero или founder"; echo "Пример: ./add-photo.sh hero ~/Downloads/фото.jpg"; exit 1 ;;
esac
[ -f "$SRC" ] || { echo "Файл не найден: $SRC"; exit 1; }

cp "$SRC" "$DST"
sips --resampleWidth 1600 "$DST" >/dev/null
sips -s format jpeg -s formatOptions 72 "$DST" --out "$DST" >/dev/null
SIZE=$(du -h "$DST" | cut -f1)
DIM=$(sips -g pixelWidth -g pixelHeight "$DST" | tail -2 | awk '{print $2}' | paste -sd'x' -)
echo "Готово: $DST — $DIM, $SIZE ($WHAT)"

git add "$DST"
git -c user.name="Elnur" -c user.email="el.khankishiev@gmail.com" commit -q -m "Фото на сайт: $SLOT"
echo "Закоммичено. Осталось: git push"
