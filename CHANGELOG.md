# Changelog

## Unreleased — UI-Skalierung, Layout-Fixes & sticky Header

Stand: noch nicht committet. Basis: `9fd155c nav UI .4`.

Schwerpunkt dieser Änderungen: Die Oberfläche wurde für das **Raspberry-Pi-Kiosk-Display (800 × 480)** überprüft und überarbeitet. Kernpunkte: einheitliches rem-Maßsystem, eine geräteweite UI-Skalierung, ein dauerhaft fixierter Kopfbereich und ein Antippen-Overlay für abgeschnittene Buchtitel.

### Neu

- **Geräteweite UI-Skalierung** (`app/static/js/scale.js`, neu)
  - Da das gesamte Stylesheet jetzt in `rem` relativ zur Root-`font-size` von `<html>` bemisst, skaliert ein einziger Wert die **komplette** Oberfläche (Text, Buttons, Abstände, Cover, PIN-Pad – alles) gleichmäßig.
  - Stellbereich **16–28 px** (≈ **70 %–122 %**, Standard 23 px = 100 %).
  - Speicherung **pro Gerät** in `localStorage` (`uiRootPx`) – passend für ein festes Kiosk.
  - Wird in jeder Seite **im `<head>` vor dem Stylesheet** geladen → keine sichtbare Umskalierung beim Laden, gilt seitenübergreifend.
  - Öffentliche API: `window.UIScale` mit `get()`, `set(px)`, `reset()`, `pct()` sowie `MIN`/`MAX`/`DEFAULT`.
  - `localStorage`-Zugriffe sind mit `try/catch` gekapselt: Auch bei deaktiviertem Speicher (privater Modus) bricht keine Seite, sie rendert dann nur unskaliert.

- **Bedienelement für die Skalierung** in den Admin-Einstellungen (`app/static/admin/settings.html`)
  - Neue Karte **„Anzeige / Display"** mit Schieberegler, Live-Prozentanzeige und „Zurücksetzen"-Button (`initUiScale()`).
  - Übersetzungen ergänzt (siehe `lang.json`).

- **Antippen langer Buchtitel zeigt den vollen Titel** (`app/static/index.html`)
  - Touchscreens haben kein „Hover": Tippt man einen **abgeschnittenen** Titel an, erscheint der vollständige Text als Hero-Overlay **am oberen Rand des jeweiligen Eintrags**, linksbündig zur Start-X-Position des Titels, und blendet nach **2,5 s** wieder aus.
  - Nur tatsächlich abgeschnittene Titel werden klickbar (Erkennung über vertikales Klemmen `scrollHeight > clientHeight` **oder** horizontal `scrollWidth > clientWidth`, Markierung mit `.is-clipped`).
  - Funktion `showTitleHero()` + delegierter Click-Handler; Styles `.title-hero` in `style.css`.

- **Responsive Buchliste – einspaltig bei schmalem Display** (`app/static/css/style.css`, `.book-list`)
  - Basis ist jetzt **eine Spalte** (Kiosk 800px und Handys); **zwei Spalten** erst ab `@media (min-width: 1100px)`.
  - Grund: Bei zwei Spalten auf 800px bleiben je Karte nur ~280px → Titel wurden stark abgeschnitten ("LIEGE…"). Einspaltig nutzt die volle Breite → Titel voll lesbar. Handys zeigten zuvor unbrauchbare 2×195px.

- **Admin → Benutzer: einspaltig bei schmalem Display** (`app/static/css/style.css`, `.user-list`)
  - War zweispaltig (`repeat(2, 1fr)`, Umbruch erst < 700px) → lief auf dem 800px-Kiosk **horizontal über** (Breite ~982px). Jetzt **eine Spalte** (Kiosk + Handy), **zwei Spalten ab 1100px** – analog zur Buchliste.
  - Skaliert über die UI-Größe mit (alles in rem, `scale.js` auf der Seite geladen): bei ~78% schrumpft die Seitenhöhe 825→648px.

- **Buchtitel kleiner und zweizeilig** (`app/static/css/style.css`, `.be-title`)
  - Schrift `1,92rem` → `1,5rem`, Untertitel `1,3rem` → `1,05rem`.
  - Statt einer Zeile mit Ellipse jetzt **bis zu 2 Zeilen** (`-webkit-line-clamp: 2`). Zusammen mit der Einspaltigkeit passt der komplette Titel der meisten Bücher lesbar in den Eintrag.

### Geändert

- **Komplettes Stylesheet von `px` auf `rem` umgestellt** (`app/static/css/style.css`)
  - Alle `px`-Werte → `rem` (Divisor 23 = bisherige Root-Größe), dadurch **optisch identisch** bei Root 23 px, aber über die Root-`font-size` skalierbar.
  - **Media-Query-Breakpoints bleiben in `px`** (das sind echte Geräte-Pixel).
  - Die Root-`font-size` ist jetzt als einziger absoluter Anker dokumentiert (`html { font-size: 23px }`); sie ist der Hebel für die Skalierung.

- **Kopfbereich (Titel/Logo + Navigation + rote Trennlinie) bleibt jederzeit oben fixiert** (`app/static/css/style.css`, `@media (max-width: 1024px)`)
  - Ursache des bisherigen Fehlers: Das 800-px-Kiosk fällt unter den Phone-Breakpoint `max-width: 1024px`, wo der Header `position: sticky` ist. Weil **sowohl `<html>` als auch `<body>`** Scroll-Container waren, klebte der Header am `body`, während `<html>` scrollte – er rutschte weg.
  - Fix: Nur noch `<html>` scrollt (`body { overflow: visible }`). Verifiziert für Kiosk (800 × 480) und Phone (390 × 844).
  - Die rote Linie ist die Unterkante des Headers und bleibt dadurch automatisch mit oben.

- **Übersetzungen** (`app/static/lang.json`): je 4 neue Schlüssel für EN / DE / Schwäbisch
  (`adminSettings.displayTitle`, `.uiScaleLabel`, `.uiScaleDesc`, `.uiScaleReset`).

- **Alle 12 HTML-Seiten**: `scale.js` im `<head>` vor dem Stylesheet eingebunden
  (`account`, `change-pin`, `index`, `login`, `phone-scan`, `register`, `setup-pin`, `admin/add-book`, `admin/overdue`, `admin/rebuy`, `admin/settings`, `admin/users`).

### Beschriftungen

- **Buchliste:** Bei mehr als einem Exemplar zeigt das „Ausgeliehen"-Badge jetzt die Anzahl, z. B. **„3 Ausgeliehen"** (bei einem Exemplar weiterhin „Ausgeliehen"). `app/static/index.html`
- **Überfällige Ausleihen:** Tagesangabe ausgeschrieben statt „{{n}}d" → **„{{n}} Tage überfällig"** (EN „days overdue", Schwäbisch „Däg überfällig"). `app/static/lang.json`
- **Admin → Settings:** Marken-Präfix aus Titel/Navigation entfernt → nur noch **„Einstellungen"** (EN „Settings", Schwäbisch „Einstellunge"); betrifft `admin.settings` (Nav) und `adminSettings.cardTitle` (Karten-Überschrift). Spart auch den Zeilenumbruch im linken Admin-Menü. `app/static/lang.json`

### Layout

- **Admin → Einstellungen jetzt zweispaltig** (`app/static/admin/settings.html`, `.settings-cols`/`.settings-col`)
  - Statt 3 gestapelter Karten (~1127 px hoch) zwei feste Spalten: **links** „Einstellungen" (hohe Karte), **rechts oben** „Anzeige / UI-Größe", darunter „Admin-Aktionen". Höhe → ~779 px, kein horizontaler Überlauf.
  - Klappt bei schmalem Display / großer UI-Skalierung auf eine Spalte (Reihenfolge: Einstellungen → Anzeige → Admin-Aktionen).

### Eingabe-Module (Vereinheitlichung, in Arbeit)

- **Hardware-Tastatur direkt im PIN-Modul** (`app/static/js/pin.js`, `makePinField`)
  - Ziffern + Backspace werden jetzt **im Modul** abgefangen, solange das Feld sichtbar ist. Damit akzeptieren **alle** Screens, die `makePinField` nutzen (Account-Verifizierung, PIN ändern, PIN einrichten), direkte Tastatureingabe – ohne eigenen Code pro Screen.
  - Die screen-eigene Tastatur-Behandlung in `account.html` wurde entfernt (Dublette).
- **Alle PIN-Eingaben nutzen jetzt dasselbe Modul** (`makePinField`)
  - Die hartcodierten Pinpads in `login.html` und im Admin-Gate (`nav.js`, 8-stellig mit Lücke) wurden durch `makePinField` ersetzt; `pin.js` ist dafür auf Login + allen Admin-Seiten eingebunden. `makePinField` unterstützt jetzt eine Mittel-Lücke für 8-stellige PINs.
  - Verifiziert: Login per Tastatur **und** On-Screen → `/index.html`; Falsch-PIN zeigt Fehler & leert die Punkte; Lockout-Countdown weiter funktionsfähig; Admin-Gate per Tastatur „14890369" verifiziert.
  - Wert-Eingaben (Guthaben, ISBN) nutzen weiterhin `numpad.js` (Inline-Zahlenfeld) – ebenfalls ein gemeinsames Modul.
- **Admin-Bereich ohne Hintergrund-Flackern** (`nav.js`, `requireAdminPin`): Beim Betreten wird sofort ein deckendes Overlay gezeigt, bis Verifizierung/PIN-Gate steht – der Admin-Inhalt blitzt nicht mehr kurz auf.
- **Tooltips bleiben im Bild** (`nav.js`): Lange `data-tip`-Texte (z. B. der Haupt-Admin-Schutzhinweis) werden auf den sichtbaren Bereich geklemmt und kippen bei Bedarf nach oben.

### Navbar & Sprache

- **Sprach-Flaggen-Dropdown in der Navbar** (`app/static/js/nav.js`) rechts neben dem Titel: Toggle zeigt die **aktuelle** Sprache (SVG-Flagge + Kürzel in 100%), das Menü listet **alle** Sprachen als reine Flaggen (keine Labels/Tooltips), bündig ohne Padding – die Menü-Radien beschneiden den Flaggen-Stapel; die Toggle-Flagge hat eine dünne weiße Outline. Flaggen als SVG (Emoji-Flaggen rendern auf dem Pi nicht zuverlässig): EN = Union Jack, DE = Trikolore, Schwäbisch = Baden-Württemberg (schwarz/gold). Auswahl speichert via `Lang.set` + Server und lädt neu.
- **Titel exakt mittig**: drei ausgewogene Header-Gruppen; das Dropdown ist absolut am rechten Logo-Rand verankert, damit das Logo zentriert bleibt. Aktive Titel-Umrandung mit etwas horizontalem Innenabstand.
- **Abbruch-Fixes:** Account-PIN-Gate hat jetzt einen **Abbrechen**-Button; beim Abbrechen des Admin-PIN-Gates bleibt das Cover-Overlay bis zur Navigation stehen → **kein leerer Screen** mehr. Beide PIN-Gates erlauben nach falscher Eingabe erneut Auto-Submit.

### Admin-Navigation

- **Überfällig-Anzahl als Notification-Badge, immer sichtbar** (`app/static/js/nav.js`, alle Admin-Seiten)
  - Die Anzahl überfälliger Ausleihen erscheint jetzt als rotes Eck-Badge am Nav-Eintrag auf **jeder** Admin-Seite (vorher nur auf der Überfällig-Seite). Befüllt zentral via `loadOverdueBadge()` in `nav.js`.
  - Badge ist absolut in der Ecke positioniert → verbreitert das Label nicht; Nav-Einträge sind per `white-space: nowrap` **einzeilig**.
  - Label gekürzt: „Überfällige Ausleihen" → **„Überfällig"** (EN „Overdue").

### Sicherheit

- **Haupt-Admin ist geschützt** (`app/routers/admin.py`, `app/static/admin/users.html`)
  - Der „Haupt-Admin" (der Admin mit der kleinsten ID = zuerst angelegt) kann von **niemand anderem** degradiert, deaktiviert oder gelöscht werden (Backend gibt 400). Selbst-Aktionen waren bereits gesperrt.
  - Die Users-API liefert dazu `is_main_admin`; das Frontend zeigt ein „Haupt-Admin"-Badge und blendet Demote/Deaktivieren/Löschen für diesen Nutzer aus.
  - Übersetzt (EN/DE/Schwäbisch): `adminUsers.mainAdmin`, `adminUsers.mainAdminTip`.

### Behoben

- **Account-PIN-Pad lief unten aus dem Bild** (`app/static/css/style.css`, `@media (max-height: 540px)`)
  - Auf dem 480-px-Panel lagen die Tasten `0`, `C`, `⌫` unter der Bildkante (kritisch).
  - Neuer **höhenbasierter** Media-Query verkleinert die PIN-Pads kompakt (Tasten `68px → ~46px`, engere Abstände, kleinerer Untertitel) – greift **nur auf kurzen Bildschirmen** (Kiosk), Desktop/Handy bleiben unberührt.
  - Tasten bleiben **≥ 44 px** (Touch-Standard). Verifiziert: Account-Gate (Karte endet bei 418 px), Admin-Gate und Login-Overlay passen alle vollständig in 480 px.

### Festgestellt, aber noch NICHT behoben (Folge-Arbeit)

Beim 800 × 480-Audit gefunden, steht noch aus:

- **Admin-Formulare zu hoch** (Einstellungen ~1127 px, Buch hinzufügen ~1122 px) → sollten zwei-spaltig werden.
- **„Verfügbar"-Checkbox nur 13 × 13 px** – deutlich unter jedem Touch-Standard.
- Touch-Ziele liegen genau auf der **44-px-Untergrenze** – ein globales Verkleinern würde sie darunter drücken; Fit-Fixes daher über Layout, nicht über Verkleinern.

### Hinweise

- `requirements.txt` (+`bcrypt`) war bereits vor dieser Session geändert.
- Nicht in `requirements.txt`, aber vom Code importiert: `requests`, `apscheduler` (vorbestehende Lücke).
