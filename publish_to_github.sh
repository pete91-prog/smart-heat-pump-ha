#!/usr/bin/env bash
# =============================================================================
# Publiser Smart Varmepumpe Styring til GitHub og gjør klar for HACS
# =============================================================================
# Krav: git og gh (GitHub CLI) installert og innlogget
#   brew install gh   (macOS)
#   gh auth login
# =============================================================================
set -euo pipefail

REPO_NAME="smart-heat-pump-ha"
DESCRIPTION="Smart varmepumpestyring for Home Assistant med hysterese og Zigbee-sensor"
VERSION="1.0.0"

echo "🔧 Initialiserer git-repo..."
cd "$(dirname "$0")"
git init
git add .
git commit -m "feat: initial release v${VERSION}

Smart Varmepumpe Styring – HACS custom integration
- Hysterese/dead band-kontroll
- Konfigurerbar cooldown mellom setpunktendringer
- Preset-moduser: Komfort, Økonomi, Borte, Boost, Manuell
- UI-oppsett via ConfigFlow (ingen YAML)
- Norsk og engelsk oversettelse"

echo ""
echo "📦 Oppretter GitHub-repo: ${REPO_NAME}"
gh repo create "${REPO_NAME}" \
  --public \
  --description "${DESCRIPTION}" \
  --push \
  --source .

echo ""
echo "🏷️  Oppretter release v${VERSION}..."
gh release create "v${VERSION}" \
  --title "v${VERSION} – Første utgivelse" \
  --notes "## Smart Varmepumpe Styring v${VERSION}

### Funksjoner
- Hysterese-kontroll (dead band) for å unngå konstant jaging
- Konfigurerbar cooldown mellom setpunktendringer
- Preset-moduser: Komfort, Økonomi, Borte, Boost, Manuell
- UI-oppsett via ConfigFlow – ingen YAML nødvendig
- Norsk og engelsk grensesnitt

### Installasjon via HACS
1. HACS → Custom repositories → legg til denne repo-URL-en
2. Kategori: Integration
3. Download → restart HA
4. Innstillinger → Integrasjoner → + Legg til → Smart Varmepumpe Styring"

echo ""
REPO_URL=$(gh repo view "${REPO_NAME}" --json url -q .url)
echo "✅ Ferdig!"
echo ""
echo "📋 Neste steg – installer i HACS:"
echo "   1. Åpne HACS i Home Assistant"
echo "   2. Tre prikker → Custom repositories"
echo "   3. Lim inn: ${REPO_URL}"
echo "   4. Kategori: Integration → Add"
echo "   5. Søk etter 'Smart Varmepumpe' → Download"
echo "   6. Start HA på nytt"
echo ""
echo "🔗 Repo: ${REPO_URL}"
