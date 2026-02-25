# IKT-Sicherheitsrichtlinie

**Version:** 2.0
**Gültigkeitsdatum:** 1. Januar 2026
**Organisation:** Caritas Schweiz

---

# 1. Einleitung

Diese IKT-Sicherheitsrichtlinie legt die Standards und Anforderungen für die Informationssicherheit innerhalb von Caritas Schweiz fest. Die Richtlinie zielt darauf ab, organisatorische Daten, Systeme und Netzwerke vor unbefugtem Zugriff, Offenlegung, Änderung oder Zerstörung zu schützen.

Alle Mitarbeitenden, Auftragnehmer, Freiwillige und externe Dienstleister müssen diese Richtlinie beim Zugriff auf oder der Nutzung von IT-Ressourcen der Organisation einhalten.

## 1.1 Zweck und Ziele

Der Hauptzweck dieser Richtlinie ist:
- Klare Sicherheitsstandards für den IT-Betrieb festzulegen
- Verantwortlichkeiten für Datenschutz und Systemsicherheit zu definieren
- Die Einhaltung schweizerischer Datenschutzgesetze und internationaler Standards sicherzustellen
- Das Risiko von Sicherheitsverletzungen und Datenverlusten zu minimieren

## 1.2 Geltungsbereich

Diese Richtlinie gilt für alle:
- Mitarbeitende (Vollzeit, Teilzeit und befristet)
- Auftragnehmer und Berater
- Freiwillige mit Systemzugriff
- Externe Dienstleister mit Datenzugriff

Die Richtlinie umfasst alle IT-Ressourcen einschließlich Computer, mobile Geräte, Netzwerkinfrastruktur, Cloud-Dienste und Datenspeichersysteme.

---

# 2. Zugriffskontrolle

Der Zugriff auf IT-Systeme und Daten muss nach dem Prinzip der minimalen Rechtevergabe kontrolliert werden. Benutzer sollten nur Zugriff auf Ressourcen haben, die für ihre Aufgaben erforderlich sind.

## 2.1 Benutzerauthentifizierung

Alle Benutzer müssen sich mit eindeutigen Anmeldeinformationen authentifizieren, bevor sie auf IT-Ressourcen zugreifen. Multi-Faktor-Authentifizierung (MFA) ist erforderlich für:
- Zugriff auf E-Mail-Systeme
- Fernzugriff über VPN
- Zugriff auf Finanzsysteme
- Administrative Konten

Benutzerkonten dürfen niemals zwischen Personen geteilt werden.

## 2.2 Passwortanforderungen

Alle Passwörter müssen die folgenden Mindestanforderungen erfüllen:
- Mindestens 12 Zeichen lang
- Kombination aus Groß- und Kleinbuchstaben, Zahlen und Sonderzeichen
- Keine Wörterbuchworte oder persönlichen Informationen
- Nicht wiederverwendet von den letzten 5 Passwörtern

Passwörter für administrative Konten müssen mindestens 16 Zeichen lang sein.

## 2.3 Passwortwechsel

Passwörter müssen nach folgendem Zeitplan geändert werden:
- Reguläre Benutzerkonten: Alle 90 Tage
- Administrative Konten: Alle 60 Tage
- Dienstkonten: Alle 180 Tage (mit dokumentierter Genehmigung)

Wenn der Verdacht besteht, dass ein Passwort kompromittiert wurde, muss es sofort geändert werden. Siehe Abschnitt 5.2 für Verfahren zur Reaktion auf Vorfälle.

## 2.4 Benutzerrollen und Berechtigungen

Die Organisation erkennt die folgenden Benutzerrollen an:

**Standardbenutzer**: Reguläre Mitarbeitende mit Zugriff auf E-Mail, freigegebene Laufwerke und abteilungsspezifische Anwendungen.

**Power-Benutzer**: Abteilungsleiter und Projektmanager mit erhöhten Berechtigungen für Reporting-Tools und Projektmanagementsysteme.

**IT-Administratoren**: IT-Personal mit vollem Systemzugriff für Wartung, Konfiguration und Support. Alle administrativen Aktionen werden gemäss Anhang A protokolliert.

**Sicherheitsadministratoren**: Designiertes Sicherheitspersonal, das Sicherheitstools verwaltet, Audit-Logs überprüft und auf Vorfälle reagiert. Siehe Anhang B für die Struktur des Sicherheitsteams.

## 2.5 Kontobereitstellung

Neue Benutzerkonten werden nur nach Erhalt eines unterzeichneten Autorisierungsformulars vom Vorgesetzten des Benutzers erstellt. Die IT-Abteilung muss:
- Die Autorisierung vor der Kontoerstellung überprüfen
- Berechtigungen basierend auf der Rolle und Abteilung des Benutzers zuweisen
- Sicherheitsschulungen bereitstellen, bevor Zugriff gewährt wird

Die Kontozugriffsrechte werden vierteljährlich überprüft. Siehe Abschnitt 6.1 für den Überprüfungsprozess.

## 2.6 Kontodeaktivierung

Benutzerkonten müssen nach folgendem Zeitplan deaktiviert oder gelöscht werden:
- Sofortige Deaktivierung bei Kündigung aus wichtigem Grund
- Deaktivierung innerhalb von 24 Stunden nach Rücktritt oder Pensionierung
- Vorübergehende Aussetzung bei längerer Abwesenheit (> 30 Tage)

Vorgesetzte müssen die IT-Abteilung sofort informieren, wenn ein Mitarbeitender die Organisation verlässt. Siehe Anhang C für die Offboarding-Checkliste.

---

# 3. Datenschutz

Datenschutz ist entscheidend für die Aufrechterhaltung des Vertrauens von Begünstigten, Spendern und Partnern.

## 3.1 Datenklassifizierung

Alle organisatorischen Daten werden in eine von drei Kategorien klassifiziert:

**Öffentliche Daten**: Informationen, die frei extern geteilt werden können (z.B. veröffentlichte Berichte, Pressemitteilungen).

**Interne Daten**: Informationen, die nur für den internen Gebrauch bestimmt sind (z.B. interne Richtlinien, Mitarbeiterverzeichnisse).

**Vertrauliche Daten**: Sensible Informationen, die streng geschützt werden müssen (z.B. persönliche Daten von Begünstigten, Spenderinformationen, Finanzunterlagen).

## 3.2 Datenverschlüsselung

Verschlüsselung ist erforderlich für:
- Alle vertraulichen Daten, die auf Laptops und mobilen Geräten gespeichert sind
- Alle Daten, die über öffentliche Netzwerke übertragen werden
- Backup-Medien, die extern gespeichert werden
- USB-Laufwerke und externe Speichergeräte mit organisatorischen Daten

Die Verschlüsselung muss branchenübliche Algorithmen verwenden (AES-256 oder stärker).

## 3.3 Datenaufbewahrung

Daten müssen gemäss den folgenden Zeitplänen aufbewahrt werden:

| Datentyp | Aufbewahrungsfrist | Speicherort |
|----------|-------------------|-------------|
| Begünstigtenakten | 10 Jahre nach Fallabschluss | Sichere Datenbank |
| Spenderinformationen | 10 Jahre nach letzter Spende | CRM-System |
| Finanzunterlagen | 10 Jahre | Buchhaltungssystem |
| E-Mail-Korrespondenz | 7 Jahre | E-Mail-Archiv |
| Mitarbeiterakten | 10 Jahre nach Beendigung | HR-System |
| Audit-Logs | 2 Jahre | Sicherheitsüberwachungssystem |

Nach Ablauf der Aufbewahrungsfrist müssen Daten sicher gelöscht oder anonymisiert werden. Siehe Anhang D für das Datenentsorgungsverfahren.

## 3.4 Datensicherung

Kritische Systeme und Daten werden nach folgendem Zeitplan gesichert:
- Tägliche inkrementelle Backups aller Dateiserver und Datenbanken
- Wöchentliche Vollsicherungen kritischer Systeme
- Monatliche Backup-Tests zur Überprüfung der Wiederherstellungsfähigkeit

Backup-Medien werden verschlüsselt und an einem sicheren externen Standort gespeichert.

## 3.5 Umgang mit vertraulichen Daten

Benutzer müssen die folgenden Vorsichtsmaßnahmen beim Umgang mit vertraulichen Daten treffen:
- Physische Dokumente in verschlossenen Schränken aufbewahren, wenn sie nicht verwendet werden
- Vertrauliche Dokumente vor der Entsorgung schreddern
- Computerbildschirme beim Verlassen des Arbeitsplatzes sperren
- Vertrauliche Angelegenheiten nicht in öffentlichen Bereichen besprechen

Vertrauliche Daten dürfen niemals per unverschlüsselter E-Mail an externe Empfänger gesendet werden.

---

# 4. Akzeptable Nutzung

IT-Ressourcen werden bereitgestellt, um organisatorische Aktivitäten zu unterstützen. Begrenzte persönliche Nutzung ist erlaubt, wenn sie die Arbeitspflichten nicht beeinträchtigt.

## 4.1 Verbotene Aktivitäten

Die folgenden Aktivitäten sind strengstens verboten:
- Zugriff, Download oder Verbreitung von illegalen oder unangemessenen Inhalten
- Installation nicht autorisierter Software oder Hardware
- Versuch, Sicherheitskontrollen zu umgehen oder auf nicht autorisierte Systeme zuzugreifen
- Nutzung von IT-Ressourcen für persönlichen finanziellen Gewinn
- Weitergabe von Anmeldedaten an andere

Verstöße können zu Disziplinarmaßnahmen führen, bis hin zur Kündigung.

## 4.2 Internet- und E-Mail-Nutzung

Der Internetzugang wird für arbeitsbezogene Zwecke bereitgestellt. Benutzer müssen:
- Websites vermeiden, die Sicherheitsrisiken darstellen
- Keine ausführbaren Dateien von nicht vertrauenswürdigen Quellen herunterladen
- Verdächtige E-Mails an das IT-Sicherheitsteam melden (security@caritas.ch)

E-Mail muss professionell genutzt werden.

## 4.3 Dateifreigabe und Zusammenarbeit

Benutzer müssen genehmigte Dateifreigabe-Tools für interne und externe Zusammenarbeit verwenden:
- **Interne Freigabe**: Organisatorisches SharePoint oder freigegebene Netzlaufwerke verwenden
- **Externe Freigabe**: Den genehmigten sicheren Dateiübertragungsdienst verwenden

Die Dateifreigabe über persönliche Cloud-Speicherkonten ist für organisatorische Daten verboten. Siehe Anhang E für genehmigte Kollaborationstools.

## 4.4 Mobile Geräte

Mobile Geräte (Smartphones, Tablets, Laptops), die für Arbeitszwecke verwendet werden, müssen:
- Bildschirmsperre mit PIN oder biometrischer Authentifizierung aktiviert haben
- Sicherheitsupdates umgehend installieren
- Geräteverschlüsselung aktiviert haben
- Sofort gemeldet werden, wenn sie verloren gehen oder gestohlen werden

Persönliche mobile Geräte, die für die Arbeit verwendet werden (BYOD), müssen der Mobile Device Management-Richtlinie gemäss Anhang F entsprechen.

---

# 5. Sicherheitsvorfallmanagement

Sicherheitsvorfälle müssen unverzüglich gemeldet und behandelt werden, um Schäden zu minimieren.

## 5.1 Vorfallmeldung

Alle Benutzer müssen verdächtige Sicherheitsvorfälle sofort melden. Beispiele umfassen:
- Verdacht auf Malware-Infektion
- Verlorene oder gestohlene Geräte
- Verdacht auf unbefugten Zugriff
- Phishing-Versuche
- Datenverletzungen oder Lecks

Vorfälle an das IT-Sicherheitsteam melden:
- E-Mail: security@caritas.ch
- Telefon: +41 41 419 2222 (24/7-Hotline)

## 5.2 Vorfallreaktion

Das IT-Sicherheitsteam folgt einem strukturierten Vorfallreaktionsprozess:

1. **Erkennung und Meldung**: Vorfall wird identifiziert und gemeldet
2. **Bewertung**: Sicherheitsteam bewertet Schweregrad und Auswirkungen
3. **Eindämmung**: Sofortmaßnahmen zur Schadensbegrenzung
4. **Untersuchung**: Ursachenanalyse und Beweissammlung
5. **Behebung**: Behebung von Schwachstellen und Wiederherstellung des Normalbetriebs
6. **Dokumentation**: Aufzeichnung von Vorfalldetails und gewonnenen Erkenntnissen

Kritische Vorfälle werden innerhalb von 2 Stunden an die Geschäftsleitung eskaliert.

## 5.3 Malware-Schutz

Alle Computer und Geräte müssen aktuelle Antivirensoftware installiert und ausgeführt haben.

Benutzer müssen:
- Antivirensoftware nicht deaktivieren
- Wöchentlich vollständige Systemscans durchführen
- Viruswarnungen sofort melden
- Verdächtige E-Mail-Anhänge nicht öffnen

---

# 6. Compliance und Durchsetzung

Die Einhaltung dieser Richtlinie ist obligatorisch.

## 6.1 Zugriffsüberprüfungen

Zugriffsrechte werden vierteljährlich von Abteilungsleitern und dem IT-Sicherheitsbeauftragten überprüft. Der Überprüfungsprozess umfasst:
- Überprüfung, dass Benutzerberechtigungen den aktuellen Aufgaben entsprechen
- Identifizierung inaktiver Konten zur Deaktivierung
- Überprüfung von administrativen Zugriffszuweisungen
- Dokumentation der Überprüfungsergebnisse

Abweichungen müssen innerhalb von 10 Werktagen korrigiert werden.

## 6.2 Sicherheitsschulung

Alle Benutzer müssen Sicherheitsschulungen absolvieren:
- Bei Einstellung oder erstmaligem Systemzugriff
- Danach jährlich
- Nach wesentlichen Richtlinienänderungen

Die Schulung umfasst:
- Passwortsicherheit und Authentifizierung
- Phishing und Social Engineering
- Datenschutz und Vertraulichkeit
- Verfahren zur Vorfallmeldung

## 6.3 Audits und Überwachung

Die Organisation führt regelmäßige Sicherheitsaudits durch. Audits umfassen:
- Überprüfung von Zugriffslogs und Systemaktivitäten
- Schwachstellen-Scanning von Netzwerksystemen
- Penetrationstests (jährlich)
- Überprüfung von Sicherheitskontrollen und Konfigurationen

Alle Systemaktivitäten werden protokolliert und überwacht. Gemäss Anhang A werden Logs 2 Jahre aufbewahrt.

## 6.4 Richtlinienverstöße

Verstöße gegen diese Richtlinie können zu Disziplinarmaßnahmen führen, einschließlich:
- Mündliche oder schriftliche Verwarnung
- Vorübergehende Aussetzung des Systemzugriffs
- Obligatorische Nachschulung
- Kündigung des Arbeits- oder Vertragsverhältnisses
- Rechtliche Schritte bei kriminellen Aktivitäten

---

# 7. Verantwortlichkeiten

Sicherheit ist eine gemeinsame Verantwortung.

## 7.1 Benutzerverantwortlichkeiten

Alle Benutzer sind verantwortlich für:
- Schutz ihrer Anmeldedaten
- Befolgung von Sicherheits-Best-Practices
- Meldung von Sicherheitsvorfällen und verdächtigen Aktivitäten
- Absolvierung erforderlicher Sicherheitsschulungen
- Einhaltung aller Aspekte dieser Richtlinie

## 7.2 Vorgesetztenverantwortlichkeiten

Abteilungsleiter sind verantwortlich für:
- Sicherstellung, dass Teammitglieder Sicherheitsschulungen absolvieren
- Autorisierung des Systemzugriffs für ihr Personal
- Vierteljährliche Überprüfung von Benutzerzugriffsberechtigungen
- Umgehende Benachrichtigung der IT bei Personalabgängen oder Rollenwechseln

## 7.3 IT-Abteilungsverantwortlichkeiten

Die IT-Abteilung ist verantwortlich für:
- Implementierung und Wartung von Sicherheitskontrollen
- Verwaltung von Benutzerkonten und Zugriffsberechtigungen
- Überwachung von Systemen auf Sicherheitsbedrohungen
- Reaktion auf Sicherheitsvorfälle
- Bereitstellung von Sicherheitstools und Anleitungen

---

# Anhang A: Audit-Logging-Standards

Alle kritischen Systeme müssen Audit-Logs führen, die Folgendes aufzeichnen:
- Benutzerauthentifizierungsversuche (erfolgreich und fehlgeschlagen)
- Änderungen an Benutzerberechtigungen oder Konten
- Zugriff auf vertrauliche Daten
- Systemkonfigurationsänderungen
- Sicherheitsvorfälle und Warnungen

Logs müssen vor unbefugter Änderung geschützt und 2 Jahre aufbewahrt werden. Das Sicherheitsteam überprüft Logs wöchentlich.

---

# Anhang B: Struktur des Sicherheitsteams

Das Informationssicherheitsteam besteht aus:

**IT-Sicherheitsbeauftragter**: Gesamtverantwortung für das Informationssicherheitsprogramm

**Sicherheitsanalytiker** (2 Positionen): Überwachung von Sicherheitssystemen, Untersuchung von Vorfällen

**Help-Desk-Personal** (4 Positionen): Erstlinien-Support für Sicherheitsprobleme

---

# Anhang C: Mitarbeiter-Offboarding-Checkliste

Wenn ein Mitarbeitender die Organisation verlässt, müssen folgende Schritte abgeschlossen werden:

**Vorgesetztenaktionen** (am oder vor dem letzten Tag):
- [ ] Alle organisatorischen Geräte einsammeln (Laptop, Telefon, Zutrittskarten)
- [ ] Vertrauliche Dokumente oder Dateien zurückholen
- [ ] IT-Abteilung über Austrittsdatum informieren

**IT-Abteilungsaktionen** (innerhalb 24 Stunden):
- [ ] Netzwerkkonto und E-Mail-Zugriff deaktivieren
- [ ] VPN- und Fernzugriffsberechtigungen widerrufen
- [ ] Aus Verteilerlisten und freigegebenen Ordnern entfernen

---

# Anhang D: Datenentsorgungsverfahren

Wenn Daten das Ende ihrer Aufbewahrungsfrist erreichen, müssen sie sicher entsorgt werden.

**Elektronische Datenentsorgung**:
- Dateien von allen Speicherorten löschen
- Speichermedien mit DoD 5220.22-M-Standards überschreiben

**Physische Dokumentenentsorgung**:
- Vertrauliche Dokumente mit Kreuzschnitt-Schreddern schreddern
- Verschlossene Entsorgungsbehälter verwenden

---

# Anhang E: Genehmigte Kollaborationstools

Folgende Tools sind für Dateifreigabe und Zusammenarbeit genehmigt:

**Interne Zusammenarbeit**:
- Microsoft SharePoint
- Freigegebene Netzlaufwerke
- Microsoft Teams

**Externe Zusammenarbeit**:
- SecureShare-Portal
- Passwortgeschützte SharePoint-Links

---

# Anhang F: Mobile Device Management (MDM)-Richtlinie

Mobile Geräte, die auf organisatorische E-Mails oder Daten zugreifen, müssen im MDM-System registriert sein.

**Geräteanforderungen**:
- Bildschirmsperre mit PIN/Passwort oder biometrischer Authentifizierung
- Verschlüsselung für Gerätespeicher aktiviert
- Automatische Sicherheitsupdates
- Remote-Löschfunktion bei Verlust oder Diebstahl

---

**Dokumentgenehmigung**:
- Genehmigt von: Geschäftsführer
- Überprüfungsdatum: 1. Januar 2027
- Richtlinienverantwortlicher: IT-Sicherheitsbeauftragter
