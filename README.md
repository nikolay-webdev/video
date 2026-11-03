# Face Lock Assistant

**Ein Python-Prototyp für Windows, der die Anwesenheit einer registrierten Person über eine Webcam prüft und den Arbeitsplatz bei längerer Abwesenheit automatisch sperrt.**

> **Status:** Persönliches Entwicklungsprojekt / Prototyp. Das Programm ist kein Ersatz für Windows-Anmeldeschutz oder professionelle Zutrittskontrolle. Eine automatische Entsperrung ist nicht vorgesehen.

## Projektüberblick

Das Projekt verbindet Gesichtserkennung, Kameraverarbeitung und die Windows-Sperrfunktion. Zuerst werden mit einem Aufnahmeassistenten Referenzbilder erstellt. Anschließend prüft die Anwendung regelmäßig das Kamerabild. Wird die registrierte Person über einen einstellbaren Zeitraum nicht erkannt, löst das Programm die Windows-Bildschirmsperre aus.

## Funktionen

- Registrierung von Referenzbildern mithilfe eines geführten Kamera-Assistenten
- Erkennung und Verifizierung von Gesichtern mit OpenCV und DeepFace
- Automatische Sperrung des Windows-Arbeitsplatzes bei längerer Abwesenheit
- Konfigurierbare Prüfintervalle und Wartezeiten
- Schutzzeit nach manueller Entsperrung zur Vermeidung sofortiger erneuter Sperrung
- Diagnosemodus für Kamerazugriff und Gesichtserkennungs-Backends
- Selbsttest ohne automatische Bildschirmsperre
- Optionales Speichern von Bildern nicht erkannter Personen **nur lokal**

## Technologien

**Python · OpenCV · DeepFace · TensorFlow/Keras · Windows API · Git**

## Projektstruktur

```text
main.py             Gesichtserkennung, Überwachung und Sperrlogik
scan_owner.py       Assistent zur Aufnahme von Referenzbildern
config.py           Konfiguration der Kamera und Zeitintervalle
requirements.txt    Python-Abhängigkeiten
logs/               Lokale Protokolle (nicht einchecken)
snapshots/          Lokale Aufnahmen (nicht einchecken)
known_faces/        Lokale Referenzbilder (selbst anlegen, nicht einchecken)
```

## Voraussetzungen und Einrichtung

- Windows mit funktionsfähiger Webcam
- Python und `pip`; die kompatible Python-Version hängt von den installierten DeepFace-/TensorFlow-Versionen ab
- Internetzugang bei der ersten Installation von Abhängigkeiten bzw. Modellgewichten

In PowerShell:

```powershell
git clone https://github.com/Nikoshot23/video.git
cd video
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scan_owner.py
python main.py --self-test
```

Wenn der Selbsttest erfolgreich ist, kann die eigentliche Überwachung gestartet werden:

```powershell
python main.py
```

**Hinweis:** Die Installation und Ausführung wurden für diese README-Überarbeitung nicht auf einem Windows-Rechner erneut verifiziert.

## Bedienung

`python scan_owner.py` öffnet den Aufnahmeassistenten:

- **Leertaste:** Referenzbild speichern
- **S:** Schritt überspringen
- **Q / Esc:** Beenden

Weitere Befehle:

```powershell
python main.py --self-test
python main.py --diagnose-detectors
```

In `config.py` können unter anderem die Kameraindizes, `ABSENCE_SECONDS_BEFORE_LOCK`, `UNLOCK_GRACE_SECONDS`, `CHECK_INTERVAL_SECONDS` und `DETECTOR_BACKEND` angepasst werden.

## Technische Umsetzung

1. Mit OpenCV werden Bilder der ausgewählten Webcam eingelesen.
2. DeepFace sucht nach Gesichtern und vergleicht diese mit lokal hinterlegten Referenzbildern.
3. Ein Timer auf Basis von `time.monotonic()` misst, wie lange die registrierte Person nicht erkannt wurde.
4. Nach Ablauf des festgelegten Intervalls wird die Windows-Sperrfunktion aufgerufen.
5. Nach einer manuellen Entsperrung verhindert eine einstellbare Schutzzeit die sofortige erneute Sperrung.

## Datenschutz und Sicherheit

**Wichtig:** Referenzbilder und Aufnahmen anderer Personen sind personenbezogene Daten. Sie dürfen nicht in ein öffentliches Repository hochgeladen werden. Die lokale Speicherung unbekannter Gesichter kann in `config.py` mit `SAVE_UNKNOWN_FACE_SNAPSHOT = False` abgeschaltet werden. Die Verwendung einer Kamera muss die Privatsphäre aller betroffenen Personen respektieren.

Die `.gitignore`-Datei schließt Laufzeitdaten und Referenzbilder bei zukünftigen Commits aus. **Bereits in früheren Commits gespeicherte Dateien werden dadurch nicht aus der Git-Historie entfernt.** Vor einer Veröffentlichung ist die gesamte Historie separat zu bereinigen.

Die Erkennung kann bei ungünstigem Licht, bestimmten Blickwinkeln oder ähnlichen Gesichtern fehlerhaft sein. Die Anwendung ist keine geprüfte Sicherheitslösung.

## Bekannte Einschränkungen

- Nur für Windows ausgelegt
- Keine automatische Entsperrung
- Keine 3D- oder Lebenderkennung (Liveness Detection)
- Gesichtserkennung und CPU-Last hängen von Hardware, Modellen und Zahl der Referenzbilder ab
- Die Sperrlogik muss auf dem Zielsystem praktisch getestet werden
- Es gibt derzeit keine automatisierte Testsuite

## Weiterentwicklung

Mögliche nächste Schritte sind automatisierte Tests der Zustandslogik, eine genauere Fehlerbehandlung der Windows-Sperrfunktion sowie die Optimierung der Gesichtserkennung durch vorab berechnete Referenz-Embeddings.

