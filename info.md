# Smart Varmepumpe Styring

Styrer varmepumpen din basert på et eksternt Zigbee-termometer med **hysterese** for å unngå konstant jaging av setpunkt.

## Funksjoner

- **Dead band / hysterese** – setter bare nytt setpunkt når romtemperaturen er utenfor mål ± konfigurerbar sone
- **Cooldown** – minimumstid mellom hver endring (standard 30 min)
- **Nødoverstyr** – hopper over cooldown om avviket er mer enn 2 × hysterese
- **Fire moduser**: Komfort, Økonomi, Borte, Boost
- **UI-oppsett** via ConfigFlow (ingen YAML nødvendig)
- **Options flow** – endre innstillinger etter installasjon

## Oppsett

1. Installer via HACS
2. Innstillinger → Enheter og tjenester → + Legg til integrasjon → *Smart Varmepumpe Styring*
3. Velg Zigbee-termometeret og varmepumpe-entiteten
4. Ferdig – en ny `climate`-entitet opprettes og tar over styringen
