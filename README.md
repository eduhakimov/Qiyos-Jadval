# Qiyos Jadval

Antiplagiat va sun’iy intellekt (SI) detektori hisobotlaridagi belgilangan parchalarni qirqib, Word hujjatidagi qiyosiy jadvalga joylaydigan Windows dasturi.

## Imkoniyatlari

- Hisobot PDF fayllaridan belgilangan parchalarni avtomatik topadi: bir raqamli belgidan keyingisigacha bo‘lgan oraliq bitta rasm va bitta satr bo‘ladi.
- Tartib doim bir xil: o‘zbek, rus, ingliz, SI. Dissertatsiya tilidagi hisobot majburiy, qolganlari ixtiyoriy.
- Rasmlar to‘liq satr kengligida, toza chegara bilan qirqiladi: yuqori va pastki qator yarmidan kesilmaydi, qo‘shni satr izlari tozalanadi.
- Matn satri jadvalda doim 10 sm, shuning uchun hamma rasmda harf o‘lchami bir xil.
- Natija: A4 albom formatdagi Word hujjat, uch ustun (№, elektron matndagi matn, izoh), avtomatik raqamlash, sarlavha va imzolar.
- Bir nechta PDF oynaga tashlansa, tili o‘zi aniqlanadi; sarlavha titul varaqdan avtomatik to‘ldiriladi.
- Tez ishlaydi: sahifalar bir necha jarayonda parallel qayta ishlanadi.

## O‘rnatish

`ornatuvchi/QiyosJadval-ornatuvchi.exe` faylini yuklab olib ishga tushiring. Administrator huquqi talab qilinmaydi, ish stolida yorliq paydo bo‘ladi.

## Ishga tushirish (manba koddan)

```
pip install -r requirements.txt
python app/main.py
```

Buyruq satri rejimi:

```
python app/main.py --cli natija.docx uz=Uz.pdf ru=Ru.pdf en=En.pdf si=Si.pdf
```

## Tuzilishi

- `app/core.py` — parchalarni topish, qirqish va Word hujjatni yozish
- `app/ui.py` — dastur oynasi (PySide6)
- `app/main.py` — ishga tushirish nuqtasi
- `build/` — Windows o‘rnatuvchisini yig‘ish skriptlari (NSIS)
- `ornatuvchi/` — tayyor Windows o‘rnatuvchisi (2.1 versiya)

## Muallif

Bahtiyor Studio
