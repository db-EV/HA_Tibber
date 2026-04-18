<p align="center"><img src="custom_components/ha_tibber/brand/icon.png" width="128" alt="HA Tibber icon"></p>

# HA Tibber

🇬🇧 [English](#-english) | 🇩🇪 [Deutsch](#-deutsch) | 🇸🇪 [Svenska](#-svenska) | 🇳🇱 [Nederlands](#-nederlands) | 🇳🇴 [Norsk](#-norsk)

---

## 🇬🇧 English

Custom Home Assistant integration for [Tibber](https://tibber.com/) — connect your Tibber electricity account and get live prices, consumption data, and costs directly in your Home Assistant dashboard.

### What you need before starting

- A [Tibber](https://tibber.com/) account
- [Home Assistant](https://www.home-assistant.io/) installed and running (version 2024.1.0 or newer)
- [HACS](https://hacs.xyz/) installed *(for the recommended installation method)*
- Your Home Assistant reachable via a URL — either on your local network (e.g. `http://homeassistant.local:8123`) or remotely

### Features

- **Live electricity price** — current price per kWh, updated every hour, with today's and tomorrow's hourly prices, min/max/average, and price level
- **Monthly statistics** — running total of your electricity cost and consumption for the current month
- **Monthly peak hour** — the single hour with highest consumption this month *(useful if your grid tariff is based on peak usage)*
- **Real-time power sensors** — requires a Tibber Pulse or Watty device; shows live watt consumption, voltage, current, and more
- **Energy Dashboard** — automatically populates Home Assistant's built-in Energy Dashboard with historical cost and consumption
- **Push notifications** — send notifications to the Tibber app from Home Assistant automations
- **Price service** — fetch hourly price data for any date range via `ha_tibber.get_prices`

---

### Installation

#### Option A — HACS (recommended)

1. Open HACS in your Home Assistant sidebar
2. Click the three-dot menu (⋮) in the top right and choose **Custom repositories**
3. Paste `https://github.com/db-EV/HA_Tibber` and select category **Integration**, then click **Add**
4. Search for **HA Tibber** and click **Download**
5. Restart Home Assistant

#### Option B — Manual

1. Download or clone this repository
2. Copy the `custom_components/ha_tibber` folder into your Home Assistant configuration directory: `config/custom_components/ha_tibber`
3. Restart Home Assistant

---

### Setup

#### Step 1 — Create Tibber OAuth credentials

You need to create an OAuth2 client in the Tibber developer portal. This is a one-time setup.

1. Go to [data-api.tibber.com/clients/manage](https://data-api.tibber.com/clients/manage) and log in with your Tibber account
2. Click **New client**
3. Give it any name (e.g. "Home Assistant")
4. Under **Scopes**, tick `data-api-homes-read`
5. Set the **Redirect URI** to:
   ```
   https://my.home-assistant.io/redirect/oauth
   ```
   > If your Home Assistant is not registered with the My Home Assistant service, use your own URL instead, e.g. `http://homeassistant.local:8123/auth/external/callback`
6. Click **Save** and note down the **Client ID** and **Client Secret**

#### Step 2 — Add the integration in Home Assistant

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration** (blue button, bottom right)
3. Search for **HA Tibber** and select it
4. Enter your **Client ID** and **Client Secret** from Step 1
5. You will be redirected to Tibber's login page — sign in and approve the connection
6. Home Assistant will return to the integration page. Setup is complete.

Your sensors will appear within a few seconds under **Settings** → **Devices & Services** → **HA Tibber**.

---

### Sensors

| Sensor | What it shows |
|--------|--------------|
| Current electricity price | Price per kWh right now. Attributes include hourly prices for today and tomorrow, min/max/average, and price level (cheap / normal / expensive) |
| Monthly cost | Total electricity cost so far this month |
| Monthly consumption | Total kWh used so far this month |
| Monthly peak hour consumption | kWh used during the single busiest hour this month |
| Monthly peak hour time | When that peak hour occurred |
| Current power consumption *(Pulse/Watty)* | Live power draw in watts |
| Current power production *(Pulse/Watty)* | Live power export in watts (solar etc.) |
| Daily accumulated consumption/cost/reward | Running totals since midnight |
| Voltage & Current (phases 1–3) *(Pulse/Watty)* | Per-phase electrical measurements |
| Power factor / Reactive power *(Pulse/Watty)* | Power quality measurements |
| Pulse signal strength | Wi-Fi signal of your Tibber Pulse device |

### Energy Dashboard

HA Tibber registers its sensors with Home Assistant's Energy Dashboard automatically. After adding the integration, go to **Settings** → **Dashboards** → **Energy** to configure which sensors to display.

### Service: Get Energy Prices

Call `ha_tibber.get_prices` from any automation or script to retrieve hourly price data.

| Field | Description |
|-------|-------------|
| `start` | Start time for the price query (optional, defaults to start of today) |
| `end` | End time for the price query (optional, defaults to end of tomorrow) |

The service returns price data grouped by home.

---

### Troubleshooting

| Problem | Solution |
|---------|----------|
| "HA Tibber" not found during Add Integration | Restart Home Assistant after installation |
| OAuth error / redirect fails | Make sure the redirect URI in your Tibber client matches exactly — including the protocol (`https://` vs `http://`) |
| Sensors show "Unavailable" | Go to **Settings** → **Devices & Services**, find HA Tibber, and check for an error message. Re-authenticate if prompted. |
| No real-time sensors | Real-time sensors only appear if you have a Tibber Pulse or Watty device registered on your account |
| Wrong account configured | Remove the integration and re-add it with the correct account |

---

### AI-Developed

This integration was entirely developed by AI using [Claude Code](https://claude.ai/code) by Anthropic.

### License

GPLv3 — see [LICENSE](LICENSE)

---

<details>
<summary>🇩🇪 Deutsch</summary>

## 🇩🇪 Deutsch

Custom Home Assistant Integration für [Tibber](https://tibber.com/) — verbinde dein Tibber-Stromkonto und erhalte Live-Preise, Verbrauchsdaten und Kosten direkt in deinem Home Assistant Dashboard.

### Was du vorher brauchst

- Ein [Tibber](https://tibber.com/)-Konto
- [Home Assistant](https://www.home-assistant.io/) installiert und in Betrieb (Version 2024.1.0 oder neuer)
- [HACS](https://hacs.xyz/) installiert *(für die empfohlene Installationsmethode)*
- Home Assistant über eine URL erreichbar — entweder im lokalen Netzwerk (z.B. `http://homeassistant.local:8123`) oder aus der Ferne

### Funktionen

- **Live-Strompreis** — aktueller Preis pro kWh, stündlich aktualisiert, mit stündlichen Preisen für heute und morgen, Min/Max/Durchschnitt und Preisniveau
- **Monatsstatistiken** — laufende Summe der Stromkosten und des Verbrauchs für den aktuellen Monat
- **Monatliche Spitzenstunde** — die Stunde mit dem höchsten Verbrauch diesen Monat *(nützlich bei netzentgeltbasierten Tarifen)*
- **Echtzeit-Sensoren** — erfordert ein Tibber Pulse oder Watty Gerät; zeigt Live-Watt-Verbrauch, Spannung, Strom und mehr
- **Energy Dashboard** — befüllt automatisch das eingebaute Home Assistant Energy Dashboard
- **Push-Benachrichtigungen** — Benachrichtigungen an die Tibber-App senden
- **Preisservice** — stündliche Preisdaten für beliebige Zeiträume abrufen

---

### Installation

#### Option A — HACS (empfohlen)

1. HACS in der Home Assistant Seitenleiste öffnen
2. Drei-Punkte-Menü (⋮) oben rechts → **Benutzerdefinierte Repositories**
3. `https://github.com/db-EV/HA_Tibber` einfügen, Kategorie **Integration** wählen, **Hinzufügen** klicken
4. Nach **HA Tibber** suchen und **Herunterladen** klicken
5. Home Assistant neu starten

#### Option B — Manuell

1. Dieses Repository herunterladen oder klonen
2. Den Ordner `custom_components/ha_tibber` in dein Home Assistant Konfigurationsverzeichnis kopieren: `config/custom_components/ha_tibber`
3. Home Assistant neu starten

---

### Einrichtung

#### Schritt 1 — Tibber OAuth-Zugangsdaten erstellen

1. Zu [data-api.tibber.com/clients/manage](https://data-api.tibber.com/clients/manage) gehen und mit dem Tibber-Konto anmelden
2. **Neuer Client** klicken
3. Einen beliebigen Namen vergeben (z.B. „Home Assistant")
4. Unter **Scopes** den Eintrag `data-api-homes-read` auswählen
5. Die **Redirect URI** auf folgendes setzen:
   ```
   https://my.home-assistant.io/redirect/oauth
   ```
6. **Speichern** klicken und **Client ID** sowie **Client Secret** notieren

#### Schritt 2 — Integration in Home Assistant hinzufügen

1. **Einstellungen** → **Geräte & Dienste**
2. **Integration hinzufügen** klicken
3. Nach **HA Tibber** suchen und auswählen
4. **Client ID** und **Client Secret** aus Schritt 1 eingeben
5. Der Tibber-Anmeldeseite folgen und die Verbindung bestätigen
6. Setup abgeschlossen — Sensoren erscheinen unter **Einstellungen** → **Geräte & Dienste** → **HA Tibber**

---

### Sensoren

| Sensor | Was er anzeigt |
|--------|---------------|
| Aktueller Strompreis | Preis pro kWh jetzt. Attribute: stündliche Preise für heute/morgen, Min/Max/Durchschnitt, Preisniveau |
| Monatliche Kosten | Gesamtstromkosten bisher diesen Monat |
| Monatlicher Verbrauch | Gesamt-kWh bisher diesen Monat |
| Monatlicher Spitzenstundenverbrauch | kWh in der verbrauchsstärksten Stunde diesen Monat |
| Monatliche Spitzenstundenzeit | Zeitpunkt der Spitzenstunde |
| Aktuelle Leistung *(Pulse/Watty)* | Live-Verbrauch in Watt |
| Spannung & Strom (Phase 1–3) *(Pulse/Watty)* | Elektrische Messwerte pro Phase |

### Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| „HA Tibber" nicht gefunden | Home Assistant nach der Installation neu starten |
| OAuth-Fehler | Redirect URI im Tibber-Client genau prüfen |
| Sensoren zeigen „Nicht verfügbar" | Unter **Einstellungen** → **Geräte & Dienste** → HA Tibber nach Fehlermeldung suchen. Ggf. neu authentifizieren. |
| Keine Echtzeit-Sensoren | Nur verfügbar mit Tibber Pulse oder Watty Gerät |

</details>

---

<details>
<summary>🇸🇪 Svenska</summary>

## 🇸🇪 Svenska

Anpassad Home Assistant-integration för [Tibber](https://tibber.com/) — koppla ditt Tibber-elkonto och få live-priser, förbrukningsdata och kostnader direkt i ditt Home Assistant-instrumentpanel.

### Vad du behöver innan du börjar

- Ett [Tibber](https://tibber.com/)-konto
- [Home Assistant](https://www.home-assistant.io/) installerat och igång (version 2024.1.0 eller senare)
- [HACS](https://hacs.xyz/) installerat *(för den rekommenderade installationsmetoden)*
- Home Assistant nåbart via en URL — antingen på ditt lokala nätverk (t.ex. `http://homeassistant.local:8123`) eller via internet

### Funktioner

- **Live-elpris** — aktuellt pris per kWh, uppdateras varje timme, med timpriser för idag och imorgon, min/max/genomsnitt och prisnivå
- **Månadsstatistik** — löpande summa av elkostnader och förbrukning för aktuell månad
- **Månadens topptimme** — timmen med högst förbrukning denna månad *(användbart om din nätavgift baseras på topplast)*
- **Realtidssensorer** — kräver Tibber Pulse eller Watty; visar live effektförbrukning, spänning, ström och mer
- **Energidashboard** — fyller automatiskt i Home Assistants inbyggda Energidashboard
- **Push-notiser** — skicka notiser till Tibber-appen från Home Assistant-automatiseringar
- **Pristjänst** — hämta timprisdata för valfritt datumintervall

---

### Installation

#### Alternativ A — HACS (rekommenderas)

1. Öppna HACS i Home Assistant-sidofältet
2. Trepunktsmenyn (⋮) uppe till höger → **Anpassade förråd**
3. Klistra in `https://github.com/db-EV/HA_Tibber`, välj kategori **Integration** och klicka **Lägg till**
4. Sök efter **HA Tibber** och klicka **Ladda ned**
5. Starta om Home Assistant

#### Alternativ B — Manuellt

1. Ladda ned eller klona detta förråd
2. Kopiera mappen `custom_components/ha_tibber` till din Home Assistant-konfigurationskatalog: `config/custom_components/ha_tibber`
3. Starta om Home Assistant

---

### Konfiguration

#### Steg 1 — Skapa Tibber OAuth-uppgifter

1. Gå till [data-api.tibber.com/clients/manage](https://data-api.tibber.com/clients/manage) och logga in med ditt Tibber-konto
2. Klicka **Ny klient**
3. Ge den ett valfritt namn (t.ex. "Home Assistant")
4. Under **Scopes**, välj `data-api-homes-read`
5. Ange **Redirect URI**:
   ```
   https://my.home-assistant.io/redirect/oauth
   ```
6. Klicka **Spara** och notera **Client ID** och **Client Secret**

#### Steg 2 — Lägg till integrationen i Home Assistant

1. **Inställningar** → **Enheter och tjänster**
2. Klicka **Lägg till integration**
3. Sök efter **HA Tibber** och välj den
4. Ange **Client ID** och **Client Secret** från Steg 1
5. Följ Tibbers inloggningssida och godkänn anslutningen
6. Konfigurationen är klar — sensorer visas under **Inställningar** → **Enheter och tjänster** → **HA Tibber**

---

### Sensorer

| Sensor | Vad den visar |
|--------|--------------|
| Aktuellt elpris | Pris per kWh nu. Attribut: timpriser för idag/imorgon, min/max/genomsnitt, prisnivå |
| Månadskostnad | Total elkostnad hittills denna månad |
| Månadsförbrukning | Totalt kWh hittills denna månad |
| Månadens förbrukning under topptimme | kWh under den mest belastade timmen denna månad |
| Månadens tidpunkt för topptimme | När topptimmen inträffade |
| Aktuell effekt *(Pulse/Watty)* | Live effektförbrukning i watt |
| Spänning & Ström (fas 1–3) *(Pulse/Watty)* | Elektriska mätvärden per fas |

### Felsökning

| Problem | Lösning |
|---------|---------|
| "HA Tibber" inte hittad | Starta om Home Assistant efter installation |
| OAuth-fel | Kontrollera att Redirect URI i Tibber-klienten stämmer exakt |
| Sensorer visar "Ej tillgänglig" | Gå till **Inställningar** → **Enheter och tjänster** → HA Tibber för felmeddelande. Autentisera om på nytt om uppmanas. |
| Inga realtidssensorer | Kräver Tibber Pulse eller Watty-enhet |

</details>

---

<details>
<summary>🇳🇱 Nederlands</summary>

## 🇳🇱 Nederlands

Aangepaste Home Assistant-integratie voor [Tibber](https://tibber.com/) — koppel je Tibber-elektriciteitsaccount en bekijk live prijzen, verbruiksgegevens en kosten direct in je Home Assistant-dashboard.

### Wat je nodig hebt

- Een [Tibber](https://tibber.com/)-account
- [Home Assistant](https://www.home-assistant.io/) geïnstalleerd en actief (versie 2024.1.0 of nieuwer)
- [HACS](https://hacs.xyz/) geïnstalleerd *(voor de aanbevolen installatiemethode)*
- Home Assistant bereikbaar via een URL — op je lokale netwerk (bijv. `http://homeassistant.local:8123`) of op afstand

### Functies

- **Live elektriciteitsprijs** — huidige prijs per kWh, elk uur bijgewerkt, met uurprijzen voor vandaag en morgen, min/max/gemiddelde en prijsniveau
- **Maandstatistieken** — lopend totaal van elektriciteitskosten en verbruik voor de huidige maand
- **Maandelijks piekuur** — het uur met het hoogste verbruik deze maand *(handig bij netbeheerderstarief op basis van piekverbruik)*
- **Realtimesensoren** — vereist Tibber Pulse of Watty; toont live vermogensverbruik, spanning, stroom en meer
- **Energiedashboard** — vult automatisch het ingebouwde Home Assistant Energiedashboard
- **Pushmeldingen** — meldingen sturen naar de Tibber-app vanuit Home Assistant-automatiseringen
- **Prijsservice** — uurlijkse prijsgegevens ophalen voor elke gewenste periode

---

### Installatie

#### Optie A — HACS (aanbevolen)

1. Open HACS in de Home Assistant-zijbalk
2. Driepuntsmenu (⋮) rechtsboven → **Aangepaste opslagplaatsen**
3. Plak `https://github.com/db-EV/HA_Tibber`, kies categorie **Integratie** en klik **Toevoegen**
4. Zoek naar **HA Tibber** en klik **Downloaden**
5. Herstart Home Assistant

#### Optie B — Handmatig

1. Download of kloon deze repository
2. Kopieer de map `custom_components/ha_tibber` naar je Home Assistant-configuratiemap: `config/custom_components/ha_tibber`
3. Herstart Home Assistant

---

### Instellen

#### Stap 1 — Tibber OAuth-gegevens aanmaken

1. Ga naar [data-api.tibber.com/clients/manage](https://data-api.tibber.com/clients/manage) en log in met je Tibber-account
2. Klik **Nieuwe client**
3. Geef het een naam (bijv. "Home Assistant")
4. Vink onder **Scopes** de optie `data-api-homes-read` aan
5. Stel de **Redirect URI** in op:
   ```
   https://my.home-assistant.io/redirect/oauth
   ```
6. Klik **Opslaan** en noteer de **Client ID** en **Client Secret**

#### Stap 2 — Integratie toevoegen in Home Assistant

1. **Instellingen** → **Apparaten & Diensten**
2. Klik **Integratie toevoegen**
3. Zoek naar **HA Tibber** en selecteer het
4. Voer de **Client ID** en **Client Secret** in uit Stap 1
5. Volg de Tibber-inlogpagina en keur de verbinding goed
6. Instellen voltooid — sensoren verschijnen onder **Instellingen** → **Apparaten & Diensten** → **HA Tibber**

---

### Sensoren

| Sensor | Wat het toont |
|--------|--------------|
| Actuele elektriciteitsprijs | Prijs per kWh nu. Kenmerken: uurprijzen voor vandaag/morgen, min/max/gemiddelde, prijsniveau |
| Maandelijkse kosten | Totale elektriciteitskosten tot nu toe deze maand |
| Maandelijks verbruik | Totaal kWh tot nu toe deze maand |
| Maandelijks verbruik piekuur | kWh tijdens het drukste uur deze maand |
| Maandelijks tijdstip piekuur | Wanneer het piekuur plaatsvond |
| Actueel vermogen *(Pulse/Watty)* | Live vermogensverbruik in watt |
| Spanning & Stroom (fase 1–3) *(Pulse/Watty)* | Elektrische metingen per fase |

### Probleemoplossing

| Probleem | Oplossing |
|----------|-----------|
| "HA Tibber" niet gevonden | Herstart Home Assistant na installatie |
| OAuth-fout | Controleer of de Redirect URI in de Tibber-client exact overeenkomt |
| Sensoren tonen "Niet beschikbaar" | Ga naar **Instellingen** → **Apparaten & Diensten** → HA Tibber voor foutmelding. Authenticeer opnieuw indien gevraagd. |
| Geen realtimesensoren | Vereist Tibber Pulse of Watty-apparaat |

</details>

---

<details>
<summary>🇳🇴 Norsk</summary>

## 🇳🇴 Norsk

Tilpasset Home Assistant-integrasjon for [Tibber](https://tibber.com/) — koble til Tibber-strømkontoen din og få live-priser, forbruksdata og kostnader direkte i Home Assistant-dashboardet ditt.

### Hva du trenger før du begynner

- En [Tibber](https://tibber.com/)-konto
- [Home Assistant](https://www.home-assistant.io/) installert og i gang (versjon 2024.1.0 eller nyere)
- [HACS](https://hacs.xyz/) installert *(for den anbefalte installasjonsmetoden)*
- Home Assistant tilgjengelig via en URL — enten på lokalt nettverk (f.eks. `http://homeassistant.local:8123`) eller eksternt

### Funksjoner

- **Live strømpris** — nåværende pris per kWh, oppdateres hver time, med timepriser for i dag og i morgen, min/maks/gjennomsnitt og prisnivå
- **Månedlig statistikk** — løpende sum av strømkostnader og forbruk for inneværende måned
- **Månedlig topptime** — timen med høyest forbruk denne måneden *(nyttig hvis nettleien er basert på toppforbruk)*
- **Sanntidssensorer** — krever Tibber Pulse eller Watty; viser live effektforbruk, spenning, strøm og mer
- **Energi-dashboard** — fyller automatisk Home Assistants innebygde Energi-dashboard
- **Push-varsler** — send varsler til Tibber-appen fra Home Assistant-automatiseringer
- **Pristjeneste** — hent timebaserte prisdata for valgfri tidsperiode

---

### Installasjon

#### Alternativ A — HACS (anbefalt)

1. Åpne HACS i Home Assistant-sidefeltet
2. Trepunktsmenyen (⋮) øverst til høyre → **Egendefinerte depoter**
3. Lim inn `https://github.com/db-EV/HA_Tibber`, velg kategori **Integrasjon** og klikk **Legg til**
4. Søk etter **HA Tibber** og klikk **Last ned**
5. Start Home Assistant på nytt

#### Alternativ B — Manuelt

1. Last ned eller klon dette depotet
2. Kopier mappen `custom_components/ha_tibber` til Home Assistant-konfigurasjonsmappe: `config/custom_components/ha_tibber`
3. Start Home Assistant på nytt

---

### Oppsett

#### Trinn 1 — Opprett Tibber OAuth-legitimasjon

1. Gå til [data-api.tibber.com/clients/manage](https://data-api.tibber.com/clients/manage) og logg inn med Tibber-kontoen din
2. Klikk **Ny klient**
3. Gi den et navn (f.eks. "Home Assistant")
4. Under **Scopes**, velg `data-api-homes-read`
5. Sett **Redirect URI** til:
   ```
   https://my.home-assistant.io/redirect/oauth
   ```
6. Klikk **Lagre** og noter **Client ID** og **Client Secret**

#### Trinn 2 — Legg til integrasjonen i Home Assistant

1. **Innstillinger** → **Enheter og tjenester**
2. Klikk **Legg til integrasjon**
3. Søk etter **HA Tibber** og velg den
4. Skriv inn **Client ID** og **Client Secret** fra Trinn 1
5. Følg Tibbers innloggingsside og godkjenn tilkoblingen
6. Oppsettet er fullført — sensorer vises under **Innstillinger** → **Enheter og tjenester** → **HA Tibber**

---

### Sensorer

| Sensor | Hva den viser |
|--------|--------------|
| Nåværende strømpris | Pris per kWh nå. Egenskaper: timepriser for i dag/morgen, min/maks/gjennomsnitt, prisnivå |
| Månedlig kostnad | Totale strømkostnader så langt denne måneden |
| Månedlig forbruk | Totalt kWh så langt denne måneden |
| Månedlig forbruk i topptime | kWh i den mest belastede timen denne måneden |
| Månedlig tidspunkt for topptime | Når topptimen inntraff |
| Nåværende effekt *(Pulse/Watty)* | Live effektforbruk i watt |
| Spenning & Strøm (fase 1–3) *(Pulse/Watty)* | Elektriske målinger per fase |

### Feilsøking

| Problem | Løsning |
|---------|---------|
| "HA Tibber" ikke funnet | Start Home Assistant på nytt etter installasjon |
| OAuth-feil | Sjekk at Redirect URI i Tibber-klienten stemmer nøyaktig |
| Sensorer viser "Utilgjengelig" | Gå til **Innstillinger** → **Enheter og tjenester** → HA Tibber for feilmelding. Autentiser på nytt hvis bedt om det. |
| Ingen sanntidssensorer | Krever Tibber Pulse eller Watty-enhet |

</details>
