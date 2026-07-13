# SI3PSI - TIM TriDev

# Specifikacija baze podataka za projekat SideKick

---

## Sadržaj

1. [Uvod](#1-uvod)
   1. [Namena](#11-namena)
   2. [Organizacija dokumenta](#12-organizacija-dokumenta)
2. [Model podataka](#2-model-podataka)
   1. [Model baze u IE notaciji](#21-model-baze-u-ie-notaciji)
   2. [Šema relacione baze podataka](#22-šema-relacione-baze-podataka)
3. [Tabele](#3-tabele)
   1. [Tabela `USER`](#31-tabela-user)
   2. [Tabela `AUTH_TOKEN`](#32-tabela-auth_token)
   3. [Tabela `RESEARCH_SPACE`](#33-tabela-research_space)
   4. [Tabela `MEMBERSHIP`](#34-tabela-membership)
   5. [Tabela `COLLABORATION_REQUEST`](#35-tabela-collaboration_request)
   6. [Tabela `ITEM`](#36-tabela-item)
   7. [Tabela `SHARE_LINK`](#37-tabela-share_link)
4. [Kardinalnosti i referencijalni integritet](#4-kardinalnosti-i-referencijalni-integritet)
   1. [Veza `USER` - `AUTH_TOKEN`](#41-veza-user---auth_token)
   2. [Veza `USER` - `RESEARCH_SPACE`](#42-veza-user---research_space)
   3. [Veza `RESEARCH_SPACE` - `MEMBERSHIP`](#43-veza-research_space---membership)
   4. [Veza `USER` - `MEMBERSHIP`](#44-veza-user---membership)
   5. [Veza `RESEARCH_SPACE` - `COLLABORATION_REQUEST`](#45-veza-research_space---collaboration_request)
   6. [Veza `USER` - `COLLABORATION_REQUEST` (`requesterId`)](#46-veza-user---collaboration_request-requesterid)
   7. [Veza `USER` - `COLLABORATION_REQUEST` (`resolvedBy`)](#47-veza-user---collaboration_request-resolvedby)
   8. [Veza `RESEARCH_SPACE` - `ITEM`](#48-veza-research_space---item)
   9. [Veza `USER` - `ITEM`](#49-veza-user---item)
   10. [Veza `RESEARCH_SPACE` - `SHARE_LINK`](#410-veza-research_space---share_link)
   11. [Veza `USER` - `SHARE_LINK`](#411-veza-user---share_link)

---

## 1. Uvod

### 1.1 Namena

Ovaj dokument predstavlja specifikaciju baze podataka za projekat **SideKick**. Cilj dokumenta je da definiše osnovne entitete, njihove atribute, međusobne veze i šemu relacione baze podataka koja će biti korišćena u fazi implementacije sistema.

Specifikacija baze podataka zasniva se na funkcionalnim zahtevima i scenarijima upotrebe definisanim za sistem SideKick. Baza podataka treba da podrži upravljanje korisničkim nalozima, research space-ovima, članstvom korisnika u prostorima, zahtevima za saradnju, stavkama koje se čuvaju u okviru prostora, deljenim linkovima i autentifikacionim tokenima.

### 1.2 Organizacija dokumenta

Dokument je organizovan u četiri glavne celine:

- u prvom delu dat je uvod i objašnjena je namena dokumenta
- u drugom delu prikazan je model podataka, uključujući model baze u IE notaciji i šemu relacione baze
- u trećem delu detaljno su opisane sve tabele koje čine bazu podataka sistema SideKick
- u četvrtom delu eksplicitno su definisani kardinalnosti i referencijalni integritet za sve veze u modelu

---

## 2. Model podataka

### 2.1 Model baze u IE notaciji

U ovom odeljku biće prikazan logički model baze podataka izrađen u **IE notaciji**.

### 2.2 Šema relacione baze podataka

USER (`userId`, email, passwordHash, fullName, createdAt, updatedAt)

AUTH_TOKEN (`tokenId`, userId, tokenValue, clientType, issuedAt, expiresAt, isRevoked)

RESEARCH_SPACE (`spaceId`, ownerId, name, description, isArchived, createdAt, updatedAt)

MEMBERSHIP (`membershipId`, spaceId, userId, role, status, createdAt, updatedAt)

COLLABORATION_REQUEST (`requestId`, spaceId, requesterId, resolvedBy, status, message, requestedAt, resolvedAt)

ITEM (`itemId`, spaceId, addedBy, itemType, contentText, sourceUrl, imagePath, title, note, sourcePlatform, capturedUrl, pageTitle, createdAt, updatedAt)

SHARE_LINK (`shareLinkId`, spaceId, createdBy, token, createdAt, expiresAt, isActive)

---

## 3. Tabele

### 3.1 Tabela `USER`

Tabela `USER` čuva osnovne podatke o korisnicima sistema.

**Atributi:**

- `userId` - jedinstveni identifikator korisnika, primarni ključ
- `email` - email adresa korisnika, jedinstvena vrednost
- `passwordHash` - heširana lozinka korisnika
- `fullName` - puno ime korisnika
- `createdAt` - datum i vreme kreiranja korisničkog naloga
- `updatedAt` - datum i vreme poslednje izmene korisničkog naloga

**Opis tabele:**

Svaki korisnik sistema mora imati jedinstvenu email adresu. Tabela `USER` predstavlja centralni entitet nad kojim se vezuju autentifikacioni tokeni, research space-ovi, članstva, zahtevi za saradnju, stavke i deljeni linkovi.

### 3.2 Tabela `AUTH_TOKEN`

Tabela `AUTH_TOKEN` čuva podatke o autentifikacionim tokenima korisnika.

**Atributi:**

- `tokenId` - jedinstveni identifikator tokena, primarni ključ
- `userId` - strani ključ koji referencira korisnika kome token pripada
- `tokenValue` - vrednost autentifikacionog tokena
- `clientType` - tip klijenta koji koristi token, na primer `web` ili `extension`
- `issuedAt` - datum i vreme izdavanja tokena
- `expiresAt` - datum i vreme isteka tokena
- `isRevoked` - oznaka da li je token opozvan

**Opis tabele:**

Ova tabela omogućava modelovanje token-based autentifikacije koja se koristi i u web aplikaciji i u Chrome ekstenziji. Jedan korisnik može imati više aktivnih ili istorijskih tokena.

### 3.3 Tabela `RESEARCH_SPACE`

Tabela `RESEARCH_SPACE` čuva podatke o research space-ovima u okviru sistema.

**Atributi:**

- `spaceId` - jedinstveni identifikator prostora, primarni ključ
- `ownerId` - strani ključ koji referencira korisnika koji je vlasnik prostora
- `name` - naziv prostora
- `description` - opis prostora
- `isArchived` - oznaka da li je prostor arhiviran
- `createdAt` - datum i vreme kreiranja prostora
- `updatedAt` - datum i vreme poslednje izmene prostora

**Opis tabele:**

Svaki research space ima tačno jednog vlasnika. U okviru jednog research space-a mogu postojati članovi, zahtevi za saradnju, stavke i deljeni linkovi.

### 3.4 Tabela `MEMBERSHIP`

Tabela `MEMBERSHIP` modeluje članstvo korisnika u research space-ovima.

**Atributi:**

- `membershipId` - jedinstveni identifikator članstva, primarni ključ
- `spaceId` - strani ključ koji referencira research space
- `userId` - strani ključ koji referencira korisnika
- `role` - uloga korisnika u prostoru, na primer `collaborator` ili `viewer`
- `status` - status članstva, na primer `active` ili `removed`
- `createdAt` - datum i vreme kreiranja članstva
- `updatedAt` - datum i vreme poslednje izmene članstva

**Opis tabele:**

Tabela `MEMBERSHIP` omogućava da jedan korisnik bude član više research space-ova i da jedan research space ima više korisnika. Kombinacija korisnika i research space-a treba da bude jedinstvena.

### 3.5 Tabela `COLLABORATION_REQUEST`

Tabela `COLLABORATION_REQUEST` čuva zahteve korisnika za pristup research space-u.

**Atributi:**

- `requestId` - jedinstveni identifikator zahteva, primarni ključ
- `spaceId` - strani ključ koji referencira research space
- `requesterId` - strani ključ koji referencira korisnika koji je poslao zahtev
- `resolvedBy` - strani ključ koji referencira korisnika koji je obradio zahtev
- `status` - status zahteva, na primer `pending`, `approved` ili `rejected`
- `message` - opciona poruka vezana za zahtev
- `requestedAt` - datum i vreme slanja zahteva
- `resolvedAt` - datum i vreme obrade zahteva

**Opis tabele:**

Ova tabela omogućava evidenciju životnog ciklusa zahteva za saradnju. Zahtev je modelovan kao poseban entitet, odvojen od članstva, kako bi bilo moguće pratiti njegova stanja kroz vreme.

### 3.6 Tabela `ITEM`

Tabela `ITEM` čuva sve stavke koje korisnici dodaju u research space-ove.

**Atributi:**

- `itemId` - jedinstveni identifikator stavke, primarni ključ
- `spaceId` - strani ključ koji referencira research space
- `addedBy` - strani ključ koji referencira korisnika koji je dodao stavku
- `itemType` - tip stavke, na primer `text`, `link` ili `image`
- `contentText` - tekstualni sadržaj stavke
- `sourceUrl` - izvorni URL sadržaja
- `imagePath` - putanja do sačuvane slike
- `title` - naslov stavke
- `note` - dodatna beleška korisnika
- `sourcePlatform` - platforma preko koje je stavka dodata, na primer `web` ili `extension`
- `capturedUrl` - URL stranice sa koje je sadržaj preuzet
- `pageTitle` - naslov stranice sa koje je sadržaj preuzet
- `createdAt` - datum i vreme kreiranja stavke
- `updatedAt` - datum i vreme poslednje izmene stavke

**Opis tabele:**

Tabela `ITEM` modeluje centralni sadržaj sistema SideKick. Sve vrste sadržaja modelovane su u okviru jedne tabele, uz korišćenje atributa koji mogu biti opcioni u zavisnosti od tipa stavke.

### 3.7 Tabela `SHARE_LINK`

Tabela `SHARE_LINK` čuva podatke o deljenim linkovima za pristup research space-ovima.

**Atributi:**

- `shareLinkId` - jedinstveni identifikator deljenog linka, primarni ključ
- `spaceId` - strani ključ koji referencira research space
- `createdBy` - strani ključ koji referencira korisnika koji je kreirao link
- `token` - jedinstvena vrednost tokena deljenog linka
- `createdAt` - datum i vreme kreiranja linka
- `expiresAt` - datum i vreme isteka linka
- `isActive` - oznaka da li je link trenutno aktivan

**Opis tabele:**

Tabela `SHARE_LINK` omogućava da se research space deli putem jedinstvenog linka. Ovakav model omogućava i čuvanje istorije kreiranih linkova, kao i njihovu deaktivaciju po potrebi.

---

## 4. Kardinalnosti i referencijalni integritet

### 4.1 Veza `USER` - `AUTH_TOKEN`

- **Kardinalnost:** jedan korisnik može imati nula ili više autentifikacionih tokena, dok jedan token pripada tačno jednom korisniku (`1:N`).
- **Referencijalni integritet:** `AUTH_TOKEN.userId` referencira `USER.userId`.
- **Preporučena pravila:** `ON UPDATE CASCADE`, `ON DELETE CASCADE`.

### 4.2 Veza `USER` - `RESEARCH_SPACE`

- **Kardinalnost:** jedan korisnik može biti vlasnik nula ili više research space-ova, dok svaki research space ima tačno jednog vlasnika (`1:N`).
- **Referencijalni integritet:** `RESEARCH_SPACE.ownerId` referencira `USER.userId`.
- **Preporučena pravila:** `ON UPDATE CASCADE`, `ON DELETE RESTRICT`.

### 4.3 Veza `RESEARCH_SPACE` - `MEMBERSHIP`

- **Kardinalnost:** jedan research space može imati nula ili više članstava, dok jedno članstvo pripada tačno jednom research space-u (`1:N`).
- **Referencijalni integritet:** `MEMBERSHIP.spaceId` referencira `RESEARCH_SPACE.spaceId`.
- **Preporučena pravila:** `ON UPDATE CASCADE`, `ON DELETE CASCADE`.

### 4.4 Veza `USER` - `MEMBERSHIP`

- **Kardinalnost:** jedan korisnik može imati nula ili više članstava, dok jedno članstvo pripada tačno jednom korisniku (`1:N`).
- **Referencijalni integritet:** `MEMBERSHIP.userId` referencira `USER.userId`.
- **Preporučena pravila:** `ON UPDATE CASCADE`, `ON DELETE CASCADE`.

### 4.5 Veza `RESEARCH_SPACE` - `COLLABORATION_REQUEST`

- **Kardinalnost:** jedan research space može imati nula ili više zahteva za saradnju, dok jedan zahtev pripada tačno jednom research space-u (`1:N`).
- **Referencijalni integritet:** `COLLABORATION_REQUEST.spaceId` referencira `RESEARCH_SPACE.spaceId`.
- **Preporučena pravila:** `ON UPDATE CASCADE`, `ON DELETE CASCADE`.

### 4.6 Veza `USER` - `COLLABORATION_REQUEST` (`requesterId`)

- **Kardinalnost:** jedan korisnik može podneti nula ili više zahteva za saradnju, dok jedan zahtev ima tačno jednog podnosioca (`1:N`).
- **Referencijalni integritet:** `COLLABORATION_REQUEST.requesterId` referencira `USER.userId`.
- **Preporučena pravila:** `ON UPDATE CASCADE`, `ON DELETE RESTRICT`.

### 4.7 Veza `USER` - `COLLABORATION_REQUEST` (`resolvedBy`)

- **Kardinalnost:** jedan korisnik može obraditi nula ili više zahteva za saradnju, dok jedan zahtev može biti obrađen od strane najviše jednog korisnika (`1:N` sa opcionom vezom sa strane zahteva).
- **Referencijalni integritet:** `COLLABORATION_REQUEST.resolvedBy` referencira `USER.userId`.
- **Preporučena pravila:** `ON UPDATE CASCADE`, `ON DELETE SET NULL`.

### 4.8 Veza `RESEARCH_SPACE` - `ITEM`

- **Kardinalnost:** jedan research space može sadržati nula ili više stavki, dok jedna stavka pripada tačno jednom research space-u (`1:N`).
- **Referencijalni integritet:** `ITEM.spaceId` referencira `RESEARCH_SPACE.spaceId`.
- **Preporučena pravila:** `ON UPDATE CASCADE`, `ON DELETE CASCADE`.

### 4.9 Veza `USER` - `ITEM`

- **Kardinalnost:** jedan korisnik može dodati nula ili više stavki, dok je svaka stavka dodata od strane tačno jednog korisnika (`1:N`).
- **Referencijalni integritet:** `ITEM.addedBy` referencira `USER.userId`.
- **Preporučena pravila:** `ON UPDATE CASCADE`, `ON DELETE RESTRICT`.

### 4.10 Veza `RESEARCH_SPACE` - `SHARE_LINK`

- **Kardinalnost:** jedan research space može imati nula ili više deljenih linkova, dok jedan deljeni link pripada tačno jednom research space-u (`1:N`).
- **Referencijalni integritet:** `SHARE_LINK.spaceId` referencira `RESEARCH_SPACE.spaceId`.
- **Preporučena pravila:** `ON UPDATE CASCADE`, `ON DELETE CASCADE`.

### 4.11 Veza `USER` - `SHARE_LINK`

- **Kardinalnost:** jedan korisnik može kreirati nula ili više deljenih linkova, dok jedan deljeni link kreira tačno jedan korisnik (`1:N`).
- **Referencijalni integritet:** `SHARE_LINK.createdBy` referencira `USER.userId`.
- **Preporučena pravila:** `ON UPDATE CASCADE`, `ON DELETE RESTRICT`.
