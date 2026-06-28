# PDF Kompresor

Prosty i szybki kompresor PDF z ładnym interfejsem (Windows). Zmniejsza ciężkie
PDF-y (skany, plakaty, dużo zdjęć) **bez psucia jakości** — recompresuje tylko
obrazy, a tekst i grafikę wektorową (linie, rysunki) zostawia ostre.

> Na realnym pliku — plakacie B1 (105 MB, obrazy do 707 DPI) — wynik to
> **105 MB → ~39 MB (−63%) w ~45 s**, wizualnie bez różnicy przy 300 DPI.

---

## Dla kogo

- **Nie jesteś programistą?** Pobierz `PDF Kompresor.exe` z zakładki
  [**Releases**](../../releases), kliknij dwa razy — i już. Nie wymaga
  instalacji, Pythona ani internetu.
- **Jesteś programistą?** Zobacz [Uruchomienie ze źródeł](#uruchomienie-ze-źródeł).

## Funkcje

- **Tryb Jakość** — gotowe poziomy: `Super (1:1)`, `Wysoka`, `Średnia`, `Niska`.
- **Tryb Docelowy rozmiar** — wpisujesz ile MB ma ważyć plik, a program sam
  dobiera DPI (binary search), żeby się zmieścić przy najlepszej jakości.
- **Skala szarości** (opcja) — usuwa kolor dla jeszcze mniejszego pliku.
- Zdjęcia i tekst **nieuszkodzone** — zmniejszane są tylko obrazy powyżej
  docelowego DPI; mniejsze zostają nietknięte.
- Działa **offline**, oryginał **nie jest nadpisywany**.

## Jak to działa

Silnik [PyMuPDF](https://pymupdf.readthedocs.io/) (`Document.rewrite_images`)
zmniejsza obrazy powyżej progu DPI do wartości docelowej i przekodowuje je do
JPEG o zadanej jakości. Tekst i wektory nie są ruszane, dlatego napisy i cienkie
linie pozostają idealnie ostre. To główny powód, dla którego ciężkie skany i
plakaty chudną wielokrotnie bez widocznej utraty jakości.

Presety (DPI / jakość JPEG): Super `300/95`, Wysoka `300/90`, Średnia `200/85`,
Niska `120/72`.

## Uruchomienie ze źródeł

Wymaga Pythona 3.9+ (z Tkinter, który jest w standardowej instalacji Windows).

```bash
pip install -r requirements.txt
python pdf_kompresor.py
```

## Budowanie samodzielnego .exe

```bash
build.bat
```

Wynik: `dist/PDF Kompresor.exe` — jeden plik z wbudowanym Pythonem i silnikiem,
działa na każdym Windows 64-bit bez instalacji.

## Licencja

[**AGPL-3.0**](LICENSE). Program korzysta z biblioteki **PyMuPDF / MuPDF**
(© [Artifex Software](https://artifex.com/), AGPL-3.0), dlatego całość jest
rozpowszechniana na tej samej licencji. Jeśli potrzebujesz licencji komercyjnej
(zamkniętej), wymagana jest komercyjna licencja PyMuPDF od Artifex.
