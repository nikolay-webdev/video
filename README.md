# Face Lock Assistant

Минимальный MVP для Windows: программа смотрит в камеру, распознает лицо владельца и блокирует рабочую станцию, если владельца слишком долго нет перед камерой.

Проект не делает авто-разблокировку Windows. Разблокировку лучше оставлять Windows Hello, PIN или ручному паролю.

## Структура

```text
video/
  main.py
  capture_owner.py
  scan_owner.py
  config.py
  requirements.txt
  requirements-capture.txt
  README.md
  known_faces/
  logs/
  snapshots/
```

## Запуск

```powershell
python main.py
```

Если `python` указывает не на `.venv`, `main.py` сам перезапустится через:

```text
.\.venv\Scripts\python.exe
```

Остановить программу можно через `Ctrl+C`.

## Самопроверка

Безопасная проверка без блокировки Windows и без сохранения снимков:

```powershell
python main.py --self-test
```

Диагностика разных детекторов лиц:

```powershell
python main.py --diagnose-detectors
```

## Сканирование лица

Запуск мастера с овалом и подсказками:

```powershell
python scan_owner.py
```

Можно также запускать привычный файл:

```powershell
python capture_owner.py
```

По умолчанию `capture_owner.py` тоже откроет мастер сканирования. Старый режим одного фото:

```powershell
python capture_owner.py --single
```

Мастер сохраняет несколько эталонных фото в `known_faces/`: прямо, взгляд на монитор, взгляд на клавиатуру, повороты головы, позиции слева/справа/выше/ниже в кадре. `main.py` сверяет лицо со всеми `.jpg`, `.jpeg`, `.png` из `known_faces/`.

## Настройки

Главные настройки находятся в `config.py`:

```python
USE_EXTERNAL_CAMERA = False
BUILT_IN_CAMERA_INDEX = 1
EXTERNAL_CAMERA_INDEX = 0
ABSENCE_SECONDS_BEFORE_LOCK = 15
UNLOCK_GRACE_SECONDS = 30
CHECK_INTERVAL_SECONDS = 2
DETECTOR_BACKEND = "mtcnn"
UNKNOWN_FACE_SNAPSHOT_COOLDOWN_SECONDS = 30
PAUSE_SECONDS_AFTER_LOCK = 1800
LOCK_MIN_WAIT_BEFORE_UNLOCK_CHECK_SECONDS = 5
LOCK_STATE_CHECK_INTERVAL_SECONDS = 5
```

Камера:

- `USE_EXTERNAL_CAMERA = True` — использовать внешнюю камеру.
- `USE_EXTERNAL_CAMERA = False` — использовать встроенную камеру.
- `BUILT_IN_CAMERA_INDEX` и `EXTERNAL_CAMERA_INDEX` можно менять, если Windows отдаёт камеры под другими индексами.

Поведение:

- `ABSENCE_SECONDS_BEFORE_LOCK` — сколько секунд владельца не должно быть видно до блокировки.
- `UNLOCK_GRACE_SECONDS` — защита после ручной разблокировки; в это время повторная блокировка запрещена.
- `CHECK_INTERVAL_SECONDS` — пауза между проверками камеры.
- `UNKNOWN_FACE_SNAPSHOT_COOLDOWN_SECONDS` — минимальная пауза между снимками неизвестного лица.
- `PAUSE_SECONDS_AFTER_LOCK` — максимальное ожидание ручной разблокировки после блокировки.

## Статусы

- `OWNER_PRESENT` — владелец распознан.
- `NO_FACE` — лицо не найдено.
- `UNKNOWN_FACE` — лицо найдено, но оно не совпало с владельцем.
- `LOCKED_WAIT` — Windows заблокирован, скрипт ждёт ручную разблокировку.
- `UNLOCK_GRACE` — Windows разблокирован, идёт защитная пауза.

## Логи и снимки

Логи:

```text
logs/app.log
```

Снимки неизвестных лиц:

```text
snapshots/
```

## Ограничения

- Только Windows.
- Без авто-разблокировки Windows.
- Качество распознавания зависит от освещения, камеры, угла лица и эталонных фото.
- Обычная веб-камера не делает настоящий 3D-скан лица. Для 3D/IR-разблокировки лучше использовать Windows Hello с совместимой камерой.
