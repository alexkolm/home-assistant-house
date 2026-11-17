# Дом в Шадринске

Живая конфигурация Home Assistant на HAOS. Репозиторий хранит **логику**, не снимок системы. Восстановление — из бэкапа HAOS, не из git.

Соседний проект: `../home-assistant-apart` (квартира в Екатеринбурге, отдельный репозиторий). Общие приёмы есть, железо и `entity_id` разные — не копировать автоматизации один в один.

Подробный обзор для людей: `README.md` (он короче фактов в коде). Этот файл — рабочая выжимка для правок.

## Границы репозитория

`.gitignore` игнорирует всё, кроме корневых `*.yaml`, `pages.jsonl`, каталогов `automations/` и `custom_templates/`, `README.md`, `AGENTS.md`.

Явно исключены `secrets.yaml` и `go2rtc.yaml`. Туда же не класть токены, пароли домофона, RTSP, `chat_id`. Чувствительное — только через `!secret`.

## Стек

- Zigbee через **Zigbee2MQTT**, префикс топиков `zigbee2mqtt_poe` (счётчик воды). Остальные устройства в основном как сущности HA.
- Уведомления: `notify.send_message` на `!secret telegram_notify_entity` (групповой чат Telegram). Фото и видео — `telegram_bot.send_photo` / `telegram_bot.send_video`. Голос на Яндекс.Станции (`!secret yandex_station_livingroom`) — режим «уехали».
- Настенная панель **openHASP** `plate1`: разметка в `pages.jsonl`, привязка к HA в `openhasp.yaml`. Топики панели: `hasp/plate1/...`.
- Погода: `weather.forecast_house_lenina`. Прогноз для панели готовит trigger-template `sensor.openhasp_weather_daily` и макросы `custom_templates/weather_helpers.jinja`.
- Дашборд в YAML-режиме: `ui-lovelace.yaml`. Вкладки: Сервер HA, Дом, Погода, Учет ресурсов, Отопление. Lovelace тянет `button-card` и `webrtc-camera` из `/local/community/` — этих файлов в git нет.
- Люди: `device_tracker.alex`, `device_tracker.tanya` в `group.family`.

## Файлы

| Файл | Роль |
|---|---|
| `configuration.yaml` | helpers, template-сенсоры, домофон (ffmpeg + REST), WLED `rest_command`, utility_meter, погодный сенсор панели, MQTT воды |
| `automations/automations.yaml` | свет, панель, домофон, присутствие, протечки, уведомления |
| `automations/heating.yaml` | газовый котёл Wertrus ECO-24FF + контроллер SmartTherm и термостат гостиной |
| `openhasp.yaml` | объекты панели: свет, погода, котёл, домофон |
| `pages.jsonl` | вёрстка openHASP, страницы 0–6 |
| `custom_templates/weather_helpers.jinja` | иконки, цвета, направление ветра, короткие дни недели |
| `custom_templates/boiler_link.jinja` | поля одной строки журнала котла |
| `boiler_link_append.py`, `boiler_link_trim.py` | дописать и обрезать `/config/boiler_link.jsonl` |
| `check_haos_drift.py` | сравнение этой папки с живым `/homeassistant` по SSH `haos-house` |
| `scripts.yaml` | `open_gate` — `switch.domofon_door_relay_0`; `awtrix_reboot`; `send_domofon_media` — очередь фото и видео калитки |
| `scenes.yaml`, `known_devices.yaml` | пустые |

Подключение автоматизаций: `automation: !include_dir_merge_list automations/`.

## Панель openHASP

Страница 0 — общая шапка и навигация. Дальше: 1 свет гостиной, 2 погода, 3 газовый котёл, 4 домофон, 5 почасовой прогноз, 6 кадр с домофона. Объект в шаблонах вида `p3b11` = страница 3, id 11.

Ручная смена температуры с панели (`p3b11` / `p3b12`, шаг 0.1 °C) выключает `input_boolean.climate_daily`, чтобы график сна не затёр оверрайд. Пресет с dropdown тоже уходит в `climate.livingroom_thermostat`.

## Отопление

Цепочка в `automations/heating.yaml`:

1. Комнатная температура для котла — `sensor.heating_control_temperature`. Пока за 90 минут менялся любой канал гостиной (температура, влажность или давление), это её показание. Дольше молчания источник — спальня, если та отвечала за последние 3 часа. Молчат оба — сенсор `unavailable`, и `switch.virtual_heating_relay` снимается: термостат застывшее число сам не отпускает. Возврат на гостиную после двух пакетов с паузой от 15 минут. В Telegram по одному сообщению на уход и на возврат. Эта температура уходит в `number.boiler_t_indoor` каждые 10 с, только если изменилась ≥ 0.05 °C. Предел топки читает её же.
2. Уличная (`sensor.yard_sensor_temperature`, запасной источник — погода) уходит в `number.boiler_t_outdoor` каждые 30 с. Если там ещё нет числа, значение пишется сразу; дальше — только при изменении ≥ 0.05 °C. Неизвестную цель не подменять `float(0)`: 0 °C на улице — настоящая температура.
3. `sensor.gas_boiler_required_mode` = `heat`, если `climate.livingroom_thermostat` в `heat` и `hvac_action: heating`, иначе `off`. Сейчас в списке зон только гостиная.
4. `gas_boiler_sync` ставит `climate.boiler_kotel` в этот режим сразу и страхуется каждые 5 минут. При включении обнуляет счётчик тактов цикла. В Telegram включение и выключение не пишет.
5. Потолок теплоносителя **65 °C**. Прошивка SmartTherm после старта ставит MaxTSet 80 °C, поэтому лимит заново выставляется при возврате `binary_sensor.gas_ping` и если атрибут `temperature` у котла ушёл выше 65.
6. Watchdog: `binary_sensor.gas_ping` off 5 минут. Если вместе с ним недоступен и контрольный хост сети (`binary_sensor.192_168_0_185`, в тексте алерта это часы Awtrix) — рестарт не делается. Иначе до 3 раз дёргается питание `switch.gas_usb` (10 с off, 90 с на проверку).
7. `schedule.night_mode` + `input_boolean.climate_daily` переключают пресет термостата `comfort` / `sleep`. Пресет `away` эта автоматизация не трогает.
8. Такты горелки: `binary_sensor.boiler_gorelka` on дольше 5 с. Часовой счётчик сбрасывается в ноль минут, предыдущий час сохраняется. Ошибки котла: `sensor.boiler_oshibki`, нормальное значение — `нет`.

Away не включается сам. Если `group.family` = `not_home` дольше 4 часов и пресет не `away`, приходит напоминание. Включение — команда Telegram `/away` → `input_boolean.notify_away_home`. Дальше: голос, выключение `switch.boiler_plug`, короткий цикл `switch.main_floor_relay` и `switch.towel_dryer_plug` (off, 5 с, on), и если термостат в `heat` — пресет `away` и выключение `climate_daily`. Возврат — `/heat`: флаг «уехали» снимается, `switch.boiler_plug` включается, `climate_daily` включается, термостат в `heat` и пресет `comfort` (после короткой паузы, чтобы график сна не записал свой пресет поверх).

## Домофон

- Открыть дверь: REST `rest_command.domofon_open_door` через template-switch `switch.domofon_door_rest` (состояние всегда off). С панели — `p4b2`, с Zigbee-кнопки — автоматизация `button_door_open`. Скрипт `open_gate` бьёт в другое реле, `switch.domofon_door_relay_0`.
- Сброс вызова: `rest_command.domofon_reject_call`, на панели `button.domofon_reject_call`.
- Камера: ffmpeg `camera.domofon_audio` из `!secret domofon_rtsp_url`. Кадр на панель и запись — `shell_command.record_domofon_video` (`/config/www/domofon.mp4`). После записи копия со штампом уходит в `script.send_domofon_media`: несколько попыток с паузой, затем подбор каждые 10 минут и после старта HA. Файл удаляется только после ответа Telegram. Старше суток клип снимается с очереди.

## Прочие контуры

- **Свет:** гостиная `switch.livingroom_relay`, торшер `light.torsher_lamp`, кухня `switch.kitchen_led_relay`. Magic Cube крутит яркость WLED и переключает подсветку. Правая кнопка AWTRIX — подсветка под кроватью. WLED пресеты — `rest_command.wled_preset_1` / `_2` на фиксированный адрес в LAN.
- **Спальня:** датчик присутствия держит `input_boolean.bedroom_presence_state`; потеря присутствия запускает `timer.bedroom_presence_off_delay` (15 мин), по окончании виртуальное присутствие гаснет.
- **Вытяжка:** по датчику присутствия в душевой, не по порогу влажности (в квартире наоборот).
- **Протечка:** одна автоматизация на перекрытие воды и оповещение.
- **Камера кошки:** `switch.ipcam_plug` включается, когда `group.family` становится `not_home`, и выключается, когда кто-то из `device_tracker.alex` / `device_tracker.tanya` дома. Выключение не стоит после Telegram: таймаут бота обрывает сценарий. Повторно гасит розетку `ipcam_off_while_home` (приход, включение розетки, старт HA, каждые 5 минут).
- **Связь:** `input_boolean.notify_offline` и алерт о потере устройств; флаг сам возвращается через 48 часов.
- **Учёт:** суточные `utility_meter` энергии (общий и котёл) и воды. Вода: импульсы `zigbee2mqtt_poe/impulse_counter` → м³ с постоянным смещением `+ 21.925`. Электричество: `sensor.energy_total` прибавляет к `sensor.energy_relay_energy` смещение `19360.7` и не даёт значению упасть. Смещения не удалять — это продолжение счётчика после обнуления.
- **Давление:** `sensor.atmospheric_pressure_mmhg` — среднее `yard` и `podval` (ноль считается отсутствием данных), перевод hPa→мм рт. ст. (`× 0.750062`) и поправка `+ 7`.
- Закат шлёт сообщение с температурами — heartbeat, что HA жив. Свет гасится, если горит дольше 5 часов. Полив: напоминание по влажности почвы.

## Сервер

Снимок 17 ноября 2026, около 16:45 по местному времени (`Asia/Yekaterinburg`). Вход с компьютера в квартире по SSH через Tailscale: аддон Advanced SSH & Web Terminal, пользователь `hassio`, псевдоним `haos-house`. Адрес и ключ в git не хранятся. Неинтерактивные команды `ha` нужно оборачивать в `bash -lc`, иначе нет `SUPERVISOR_TOKEN`.

`python check_haos_drift.py` в этот момент: код совпадает с `/homeassistant`, 13 файлов. Markdown скрипт не сравнивает.

Платформа — виртуальная машина KVM, плата `ova`, ядро `6.18.58-haos`. HAOS **18.4** загружен со слота A, слот B хранит 18.3, оба помечены хорошими. Диск 30.8 ГБ (занято 13.2, свободно 16.3). Имя хоста `homeassistant`. NTP включён (`use_ntp: true`); флаг `dt_synchronized` в момент проверки был выключен.

Версии: Core **2026.11.1**, к установке есть **2026.11.2**. Supervisor **2026.11.0**, канал stable, `healthy` и `supported`. Платформа `notify` с `platform: telegram` в этом Core уже нет — текст уходит через `notify.send_message`.

Аддоны все запущены, обновлений аддонов нет:

| Аддон | Версия |
|---|---|
| Advanced SSH & Web Terminal | 24.2.1 |
| Tailscale | 0.30.7 |
| Mosquitto broker | 7.1.3 |
| Zigbee2MQTT | 2.14.3-1 |
| go2rtc | 1.9.15 |
| Hikvision Doorbell | 3.0.34 |
| File editor | 6.3.1 |
| Home Assistant Google Drive Backup | 0.112.1 |

Репозитории ESPHome и Music Assistant подключены, самих приложений нет. Рабочий Zigbee2MQTT — репозиторий `8c77aaed`; второй репозиторий Zigbee2MQTT в списке лишний. Matter Server не установлен.

Сущностей 589. Все автоматизации из yaml включены: **65** `on`, это ровно число alias в `automations/` (35 + 30). Ещё **59** `automation.*` в `unavailable` — старые записи реестра, в yaml их нет. На снимке 14 октября рядом были такие же осиротевшие сущности, их не чинить правкой текущих файлов: `sensor.water_consumption`, `sensor.water_consumption_2`, `sensor.water_consumption_3` (живой счётчик — `sensor.water_consumption_cubic_meters`), `sensor.boiler_starts_last_hour` и `counter.boiler_starts_hourly` (живые — `input_number.boiler_starts_*`), `light.livingroomlight`, `timer.coridor`, `timer.lamp_off`, `timer.light_turn_off`, `input_boolean.boiler_turn_off`, `input_boolean.boiler_turn_on_min`, `input_boolean.boiler_turn_on_norm`. 17 ноября живые контуры были в работе: источник отопления `livingroom` (24.6 °C), дельта перетопа 0.9 °C, `group.family` = `home` и `switch.ipcam_plug` выключен, `binary_sensor.gas_ping` on, котёл в `heat` с потолком 65 °C, гостиная в `heat` / `heating` / `comfort`, `sensor.boiler_oshibki` = `нет`.

Полный бэкап по-прежнему снимает аддон Google Drive (ночью). Список копий и health Zigbee2MQTT в этот заход не переснимались: на 14 октября было 187 копий и 33 устройства на префиксе `zigbee2mqtt_poe`.

## Правила правок

- Перед правкой логики и перед выкладкой файлов на HAOS запусти `python check_haos_drift.py`. Если он пишет, что код разъехался, локальную копию на сервер не заливать: сначала показать список файлов. Так ловятся правки из веб-морды, сделанные не с этого компьютера. `AGENTS.md` скрипт не сравнивает.
- Не добавлять секреты, URL камер, пароли и адреса в git. Новый секрет — `!secret`.
- Отопление менять в `automations/heating.yaml`, не размазывать по общему файлу. Синхронизатор котла — одна точка записи `climate.boiler_kotel`; не добавлять второй `set_hvac_mode` из других автоматизаций.
- Ручной оверрайд температуры с панели обязан сбрасывать `input_boolean.climate_daily`.
- Watchdog не должен рестартовать контроллер, если недоступна сеть целиком.
- Потолок 65 °C — осознанный лимит против дефолта прошивки 80 °C.
- Комментарии в yaml — часть документации.
- Камера кошки (`switch.ipcam_plug`) выключена, пока `group.family` = `home`. Команду на розетку не ставить после `notify.send_message`.
