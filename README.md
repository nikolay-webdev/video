# Face Lock Assistant

Windows MVP: скрипт смотрит в камеру, распознаёт владельца и блокирует экран, если владельца нет перед камерой заданное время.

Авто-разблокировка не реализуется: пароль не хранится в проекте и не вводится скриптом.

## Файлы

```text
main.py          основной мониторинг и блокировка
scan_owner.py    мастер записи эталонных фото владельца
config.py        настройки
requirements.txt зависимости полного проекта
known_faces/     эталонные фото владельца
logs/            app.log
snapshots/       снимки неизвестных лиц
```

## Запуск

```powershell
python main.py
```

Если VS Code или PowerShell запустит глобальный Python, `main.py` сам перезапустится через `.venv`.

Безопасная проверка без блокировки:

```powershell
python main.py --self-test
```

Диагностика детекторов:

```powershell
python main.py --diagnose-detectors
```

## Запись лица владельца

```powershell
python scan_owner.py
```

Мастер показывает овал и просит сохранить несколько позиций: прямо, взгляд на монитор, взгляд на клавиатуру, повороты головы, позиции слева/справа/выше/ниже в кадре.

Клавиши:

- `Space` — сохранить текущий шаг.
- `S` — пропустить шаг.
- `Q` или `Esc` — выйти.

`main.py` сравнивает лицо со всеми `.jpg`, `.jpeg`, `.png` из `known_faces/`.

## Настройки

Основные настройки в `config.py`:

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
KNOWN_FACES_DIR = "known_faces"
```

Камера:

- `USE_EXTERNAL_CAMERA = True` — внешняя камера.
- `USE_EXTERNAL_CAMERA = False` — встроенная камера.
- `BUILT_IN_CAMERA_INDEX` и `EXTERNAL_CAMERA_INDEX` можно менять, если Windows отдаёт камеры под другими индексами.

Поведение:

- `ABSENCE_SECONDS_BEFORE_LOCK` — сколько секунд подряд владельца не должно быть видно до блокировки.
- `UNLOCK_GRACE_SECONDS` — защита после ручной разблокировки; в это время повторная блокировка запрещена.
- `CHECK_INTERVAL_SECONDS` — пауза между проверками.
- `UNKNOWN_FACE_SNAPSHOT_COOLDOWN_SECONDS` — пауза между снимками неизвестного лица.
- `PAUSE_SECONDS_AFTER_LOCK` — максимальное ожидание ручной разблокировки.

## Статусы

- `OWNER_PRESENT` — владелец распознан.
- `NO_FACE` — лицо не найдено.
- `UNKNOWN_FACE` — лицо найдено, но не совпало с владельцем.
- `LOCKED_WAIT` — Windows заблокирован, скрипт ждёт ручную разблокировку.
- `UNLOCK_GRACE` — идёт защитная пауза после разблокировки.

## Ограничения

- Только Windows.
- Без авто-разблокировки.
- Обычная веб-камера не делает настоящий 3D-скан.
- Качество зависит от света, угла лица, камеры и эталонных фото.
