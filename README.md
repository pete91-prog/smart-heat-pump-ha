# Smart Varmepumpe Styring – HACS Custom Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io)

Styrer varmepumpen din basert på et eksternt Zigbee-termometer med hysterese (dead band) for å unngå konstant jaging og unødvendig slitasje.

## Funksjoner

| Funksjon | Beskrivelse |
|----------|-------------|
| **Hysterese / dead band** | Setpunktet endres kun når temp. er utenfor mål ± hysterese |
| **Cooldown** | Konfigurerbar minimumstid mellom endringer (standard 30 min) |
| **Nødoverstyr** | Hopper over cooldown om avviket er > 2 × hysterese |
| **Preset-moduser** | Komfort, Økonomi, Borte, Boost, Manuell |
| **UI-oppsett** | Ingen YAML nødvendig – alt via ConfigFlow |
| **Options flow** | Endre alle innstillinger etter installasjon |
| **Tilstandsgjenoppretting** | Husker preset og innstillinger etter omstart |

## Installasjon via HACS

### 1. Legg til som custom repository

1. Åpne HACS i Home Assistant
2. Klikk de tre prikkene øverst til høyre → **Custom repositories**
3. Lim inn URL-en til dette GitHub-repositoriet
4. Velg kategori **Integration**
5. Klikk **Add**

### 2. Installer integrasjonen

1. Søk etter "Smart Varmepumpe" i HACS
2. Klikk **Download**
3. Start Home Assistant på nytt

### 3. Konfigurer

1. Gå til **Innstillinger → Enheter og tjenester**
2. Klikk **+ Legg til integrasjon**
3. Søk etter **Smart Varmepumpe Styring**
4. Velg temperatursensor (Zigbee-termometeret) og varmepumpe-entiteten
5. En ny `climate`-entitet opprettes og tar umiddelbart over styringen

## Parametre

Alle parametre kan justeres etter installasjon via **Innstillinger → Integrasjoner → Smart Varmepumpe → Konfigurer**.

| Parameter | Standard | Beskrivelse |
|-----------|----------|-------------|
| Komfort-måltemperatur | 20 °C | Ønsket romtemperatur |
| Hysterese | 0,5 °C | Dead band rundt mål. Ingen endring innenfor ±dette |
| Min. tid mellom endringer | 30 min | Cooldown mellom setpunktjusteringer |
| Overshoot | 2 °C | Varmepumpen settes til mål+dette ved oppvarming |
| Økonomi-reduksjon | 2 °C | Økonomi-modus bruker komfortmål − dette |
| Borte-temperatur | 17 °C | Fast setpunkt i borte-modus |
| Boost-setpunkt | 24 °C | Fast setpunkt i boost-modus |

## Slik fungerer anti-jagingen

```
Romtemperatur vs. Justert måltemperatur:

  Mål − hysterese       Mål        Mål + hysterese
        │                │                │
   [Varm opp]    [GJØR INGENTING]   [Hold igjen]
        │                │                │
      19,5°C           20°C            20,5°C
                 (dead band ±0,5°C)

Sekvens med mål=20°C, hysterese=0,5°C, cooldown=30min:
  18:00 Temp 19,3°C → 0,7°C under mål → setter VP til 22°C  ✅
  18:10 Temp 19,7°C → innenfor dead band               → ingenting ✅
  18:30 Temp 20,3°C → innenfor dead band               → ingenting ✅
  18:45 Temp 20,8°C → 0,8°C over mål + 30min siden sist → setter VP til 19°C ✅
  18:50 Temp 20,5°C → innenfor dead band               → ingenting ✅
```

## Moduser

| Modus | Setpunkt | Beskrivelse |
|-------|----------|-------------|
| **Komfort** | Komfortmål | Normal daglig bruk |
| **Økonomi** | Komfortmål − øko-offset | Litt kaldere, sparer strøm |
| **Borte** | Fast lav temp | Minimum mens ingen er hjemme |
| **Boost** | Fast høy temp | Rask oppvarming ved hjemkomst |
| **Manuell** | — | Automatikken pauses, styr VP direkte |

## Støttede varmepumper

Alle varmepumper med en `climate`-entitet i Home Assistant støttes:

- Mitsubishi Electric (MELCloud / mitsubishi_heatpump)
- Daikin (`daikin`)
- Panasonic (`panasonic_cc`)
- LG ThinQ (`smartthinq_sensors`)
- Fujitsu (`fujitsu_general_heatpump`)
- Og alle andre med `climate.set_temperature`-støtte

## Krav

- Home Assistant 2024.1 eller nyere
- HACS installert
- Varmepumpen integrert som `climate`-entitet
- Zigbee-termometer oppsatt (via Zigbee2MQTT, ZHA, eller lignende)
