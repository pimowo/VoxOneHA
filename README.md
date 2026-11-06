# VoxOneHA

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/pimowo/VoxOneHA.svg)](https://GitHub.com/pimowo/VoxOneHA/releases/)

Oficjalna integracja Home Assistant dla radioodtwarzaczy **VoxOne** (wersje S, M, L, W). 

Integracja jest w pełni samodzielna – **nie wymaga MQTT**. Komunikacja odbywa się lokalnie (LAN) za pomocą WebSockets i REST API, co zapewnia natychmiastową aktualizację stanów (local_push).

## ✨ Funkcje

- **Wsparcie dla wielu urządzeń** – każde radio dodawane jest jako osobne urządzenie.
- **Odtwarzacz multimedialny (Media Player)** – pełna kontrola (Play, Stop, Następna/Poprzednia, Głośność, Wyciszenie).
- **Sensory** – monitorowanie Wi-Fi RSSI, Uptime (czas działania) i Bitrate.
- **Przyciski i Przełączniki** – zdalny restart radia oraz wybór źródła (Radio/Bluetooth).
- **Bezpieczeństwo** – pełne wsparcie dla haseł w trybie `PROTECTED` (autoryzacja przez ciasteczka sesyjne).
- **Konfiguracja przez UI** – bez edycji plików YAML.

## 📦 Instalacja

Integracja jest dostępna w oficjalnym Katalogu Społeczności (Marketplace) w Home Assistant.

### Metoda 1: Katalog Społeczności (HA 2026.11+)
1. Przejdź do **Ustawienia -> Katalog społeczności** (Settings -> Community Catalog).
2. Kliknij menu (3 kropki) w prawym górnym rogu i wybierz **Dodaj z linku** (Add from link).
3. Wklej adres: `https://github.com/pimowo/VoxOneHA`
4. Wyszukaj **VoxOne** na liście i kliknij **Zainstaluj**.
5. Zrestartuj Home Assistanta.

### Metoda 2: HACS (Starsze wersje HA)
1. Otwórz HACS -> Integracje -> Custom repositories.
2. Wklej `https://github.com/pimowo/VoxOneHA` i wybierz kategorię **Integration**.
3. Wyszukaj **VoxOne**, kliknij **Download** i zrestartuj HA.

### Metoda 3: Ręcznie
Skopiuj folder `custom_components/voxoneha` do katalogu `config/custom_components/` w Home Assistant i zrestartuj system.

## ⚙️ Konfiguracja

1. Przejdź do **Ustawienia -> Urządzenia i usługi -> Dodaj integrację**.
2. Wyszukaj **VoxOne**.
3. Wprowadź dane:
   - **Host / IP**: Adres IP radia w sieci lokalnej (np. `192.168.1.54`) lub nazwa mDNS (np. `voxone.local`).
   - **Port**: Domyślnie `80`.
   - **Hasło**: Wpisz hasło, jeśli radio ma włączony tryb ochrony `PROTECTED`. W trybie `OPEN` pozostaw puste.

## 📊 Encje (Entities)

Po dodaniu urządzenia, w Home Assistant pojawią się następujące encje:

| Platforma | Encja | Opis |
|---|---|---|
| `media_player` | `media_player.voxone_...` | Odtwarzacz z kontrolą głośności i stacji. |
| `sensor` | `sensor.voxone_..._rssi` | Siła sygnału Wi-Fi (dBm). |
| `sensor` | `sensor.voxone_..._uptime` | Czas działania od ostatniego restartu. |
| `sensor` | `sensor.voxone_..._bitrate` | Przepływność aktualnego strumienia audio (kbps). |
| `button` | `button.voxone_..._restart` | Zdalny restart urządzenia. |
| `select` | `select.voxone_..._source` | Wybór źródła dźwięku (Radio / Bluetooth). |

## 🔧 Rozwiązywanie problemów

**Błąd: "Nie można połączyć" (Cannot connect)**
- Upewnij się, że radio ma nadane statyczne IP w routerze (DHCP Reservation). Zmiana IP po restarcie routera zerwie połączenie z HA.
- Sprawdź, czy Home Assistant i radio znajdują się w tej samej podsieci.
- Jeśli używasz trybu `PROTECTED`, upewnij się, że hasło jest poprawne.

**Brak aktualizacji stanów na żywo**
Integracja opiera się na WebSocketach. Upewnij się, że nic nie blokuje ruchu na porcie `80` w sieci lokalnej. W razie problemów zrestartuj integrację w HA lub zrestartuj samo radio (używając przycisku w HA).

## 🛠️ Wsparcie i rozwój
Projekt jest otwarty na rozbudowę. W planach znajduje się automatyczne wykrywanie urządzeń (mDNS/Zeroconf) po dodaniu odpowiedniej usługi w firmware VoxOne.
Zgłoszenia błędów i propozycje nowych funkcji: [Issues](https://github.com/pimowo/VoxOneHA/issues).

---
*Stworzone przez [pimowo](https://github.com/pimowo).*
