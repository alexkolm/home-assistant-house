# Дом в Шадринске

Живая конфигурация Home Assistant на HAOS. Репозиторий хранит **логику**, не снимок системы. Восстановление — из бэкапа HAOS, не из git.

Соседний проект: `../home-assistant-apart` (квартира в Екатеринбурге, отдельный репозиторий). Общие приёмы есть, железо и `entity_id` разные — не копировать автоматизации один в один.

Подробный обзор для людей: `README.md` (он короче фактов в коде). Этот файл — рабочая выжимка для правок.

## Границы репозитория

`.gitignore` игнорирует всё, кроме корневых `*.yaml`, `pages.jsonl`, каталогов `automations/` и `custom_templates/`, `README.md`, `AGENTS.md`.

Явно исключены `secrets.yaml` и `go2rtc.yaml`. Туда же не класть токены, пароли домофона, RTSP, `chat_id`. Чувствительное — только через `!secret`.

## Стек

- Zigbee через **Zigbee2MQTT**, префикс топиков `zigbee2mqtt_poe` (счётчик воды). Остальные устройства в основном как сущности HA.
- Уведомления: `notify.me` (Telegram). Голос на Яндекс.Станции (`!secret yandex_station_livingroom`) — режим «уехали».
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
| `scripts.yaml` | `open_gate` — `switch.domofon_door_relay_0` |
| `scenes.yaml`, `known_devices.yaml` | пустые |

Подключение автоматизаций: `automation: !include_dir_merge_list automations/`.

## Панель openHASP

Страница 0 — общая шапка и навигация. Дальше: 1 свет гостиной, 2 погода, 3 газовый котёл, 4 домофон, 5 почасовой прогноз, 6 кадр с домофона. Объект в шаблонах вида `p3b11` = страница 3, id 11.

Ручная смена температуры с панели (`p3b11` / `p3b12`, шаг 0.1 °C) выключает `input_boolean.climate_daily`, чтобы график сна не затёр оверрайд. Пресет с dropdown тоже уходит в `climate.livingroom_thermostat`.

## Отопление

Цепочка в `automations/heating.yaml`:

1. Комнатная температура (`sensor.livingroom_sensor_temperature`) уходит в `number.boiler_t_indoor` каждые 10 с, только если изменилась ≥ 0.05 °C.
2. Уличная (`sensor.yard_sensor_temperature`, запасной источник — погода) уходит в `number.boiler_t_outdoor` каждые 30 с. Если там ещё нет числа, значение пишется сразу; дальше — только при изменении ≥ 0.05 °C. Неизвестную цель не подменять `float(0)`: 0 °C на улице — настоящая температура.
3. `sensor.gas_boiler_required_mode` = `heat`, если `climate.livingroom_thermostat` в `heat` и `hvac_action: heating`, иначе `off`. Сейчас в списке зон только гостиная.
4. `gas_boiler_sync` ставит `climate.boiler_kotel` в этот режим сразу и страхуется каждые 5 минут. При включении обнуляет счётчик тактов цикла, при выключении пишет его в Telegram.
5. Потолок теплоносителя **65 °C**. Прошивка SmartTherm после старта ставит MaxTSet 80 °C, поэтому лимит заново выставляется при возврате `binary_sensor.gas_ping` и если атрибут `temperature` у котла ушёл выше 65.
6. Watchdog: `binary_sensor.gas_ping` off 5 минут. Если вместе с ним недоступен и контрольный хост сети (`binary_sensor.192_168_0_185`, в тексте алерта это часы Awtrix) — рестарт не делается. Иначе до 3 раз дёргается питание `switch.gas_usb` (10 с off, 90 с на проверку).
7. `schedule.night_mode` + `input_boolean.climate_daily` переключают пресет термостата `comfort` / `sleep`. Пресет `away` эта автоматизация не трогает.
8. Такты горелки: `binary_sensor.boiler_gorelka` on дольше 5 с. Часовой счётчик сбрасывается в ноль минут, предыдущий час сохраняется. Ошибки котла: `sensor.boiler_oshibki`, нормальное значение — `нет`.

Away не включается сам. Если `group.family` = `not_home` дольше 4 часов и пресет не `away`, приходит напоминание. Включение — команда Telegram `/away` → `input_boolean.notify_away_home`. Дальше: голос, выключение `switch.boiler_plug`, короткий цикл `switch.main_floor_relay` и `switch.towel_dryer_plug` (off, 5 с, on), и если термостат в `heat` — пресет `away` и выключение `climate_daily`.

## Домофон

- Открыть дверь: REST `rest_command.domofon_open_door` через template-switch `switch.domofon_door_rest` (состояние всегда off). С панели — `p4b2`, с Zigbee-кнопки — автоматизация `button_door_open`. Скрипт `open_gate` бьёт в другое реле, `switch.domofon_door_relay_0`.
- Сброс вызова: `rest_command.domofon_reject_call`, на панели `button.domofon_reject_call`.
- Камера: ffmpeg `camera.domofon_audio` из `!secret domofon_rtsp_url`. Кадр на панель и запись — `shell_command.record_domofon_video` / `delete_domofon_video` (`/config/www/domofon.mp4`).

## Прочие контуры

- **Свет:** гостиная `switch.livingroom_relay`, торшер `light.torsher_lamp`, кухня `switch.kitchen_led_relay`. Magic Cube крутит яркость WLED и переключает подсветку. Правая кнопка AWTRIX — подсветка под кроватью. WLED пресеты — `rest_command.wled_preset_1` / `_2` на фиксированный адрес в LAN.
- **Спальня:** датчик присутствия держит `input_boolean.bedroom_presence_state`; потеря присутствия запускает `timer.bedroom_presence_off_delay` (15 мин), по окончании виртуальное присутствие гаснет.
- **Вытяжка:** по датчику присутствия в душевой, не по порогу влажности (в квартире наоборот).
- **Протечка:** одна автоматизация на перекрытие воды и оповещение.
- **Связь:** `input_boolean.notify_offline` и алерт о потере устройств; флаг сам возвращается через 48 часов.
- **Учёт:** суточные `utility_meter` энергии (общий и котёл) и воды. Вода: импульсы `zigbee2mqtt_poe/impulse_counter` → м³ с постоянным смещением `+ 21.925`. Электричество: `sensor.energy_total` прибавляет к `sensor.energy_relay_energy` смещение `19360.7` и не даёт значению упасть. Смещения не удалять — это продолжение счётчика после обнуления.
- **Давление:** `sensor.atmospheric_pressure_mmhg` — среднее `yard` и `podval` (ноль считается отсутствием данных), перевод hPa→мм рт. ст. (`× 0.750062`) и поправка `+ 7`.
- Закат шлёт сообщение с температурами — heartbeat, что HA жив. Свет гасится, если горит дольше 5 часов. Полив: напоминание по влажности почвы.

## Сервер

Снимок 14 октября 2026, около 23:30 по местному времени. Вход с компьютера в квартире по SSH через Tailscale: аддон Advanced SSH & Web Terminal, пользователь `hassio`. Адрес и ключ в git не хранятся. Неинтерактивные команды `ha` нужно оборачивать в `bash -lc`, иначе нет `SUPERVISOR_TOKEN`.

Платформа — виртуальная машина KVM, плата `ova`, ядро `6.18.52-haos`. HAOS **18.3** загружен со слота B, слот A хранит 18.2 и помечен хорошим. 2 CPU, около 4 ГБ памяти, диск 30.8 ГБ (занято 13.3, свободно 16.2). Имя хоста `homeassistant`, часовой пояс `Asia/Yekaterinburg`. Флаг синхронизации NTP был выключен, сами часы в момент проверки совпали с реальным временем.

Версии: Core **2026.10.0**, к установке есть **2026.10.1**. Supervisor **2026.09.3**, канал stable, `healthy` и `supported`. Центр восстановления пуст: ни issues, ни suggestions. Нагрузка Core около 1.5 % CPU и 24 % его лимита памяти.

Аддоны все запущены, обновлений нет:

| Аддон | Версия |
|---|---|
| Advanced SSH & Web Terminal | 24.1.7 |
| Tailscale | 0.30.2 |
| Mosquitto broker | 7.1.1 |
| Zigbee2MQTT | 2.14.2-1 |
| go2rtc | 1.9.14 |
| Hikvision Doorbell | 3.0.34 |
| File editor | 6.2.0 |
| Home Assistant Google Drive Backup | 0.112.1 |

Репозитории ESPHome и Music Assistant подключены, самих приложений нет. Рабочий Zigbee2MQTT — репозиторий `8c77aaed`; второй репозиторий Zigbee2MQTT в списке лишний. Matter Server не установлен.

Полный бэкап аддон Google Drive снимает каждую ночь в 03:00. Последний на момент проверки — 14 октября 2026, около 200 МБ. В списке 187 копий на примерно 5 ГБ: четыре полных и много частичных, самые старые с апреля 2023. Датчики встроенного backup (`sensor.backup_last_*`) были `unknown`: расписание держит аддон, не интеграция Core.

Zigbee2MQTT на префиксе `zigbee2mqtt_poe`: MQTT подключён, в health-снимке 33 устройства, `leave_count` у всех 0, процесс жил около 4.5 суток и занимал примерно 170 МБ. Слабее остальных в тот момент отвечали кран воды (linkquality около 20) и датчик растения (батарея 0).

Сущностей 555. Все автоматизации из yaml включены: **47** `on`, это ровно число alias в `automations/` (31 + 16). Ещё **59** `automation.*` в `unavailable` — старые записи реестра, в yaml их нет. Рядом такие же осиротевшие сущности, их не чинить правкой текущих файлов: `sensor.water_consumption`, `sensor.water_consumption_2`, `sensor.water_consumption_3` (живой счётчик — `sensor.water_consumption_cubic_meters`), `sensor.boiler_starts_last_hour` и `counter.boiler_starts_hourly` (живые — `input_number.boiler_starts_*`), `light.livingroomlight`, `timer.coridor`, `timer.lamp_off`, `timer.light_turn_off`, `input_boolean.boiler_turn_off`, `input_boolean.boiler_turn_on_min`, `input_boolean.boiler_turn_on_norm`. `number.boiler_t_outdoor` был `unknown`, `number.boiler_t_indoor` значение имел. `person.alex` и `person.tanya` были `unknown`; `device_tracker.alex` и `device_tracker.tanya` в недоступных не числились. `unknown` у `button`, `notify` и части `select` — пустое состояние MQTT, не авария.

## Правила правок

- Перед правкой логики и перед выкладкой файлов на HAOS запусти `python check_haos_drift.py`. Если он пишет, что код разъехался, локальную копию на сервер не заливать: сначала показать список файлов. Так ловятся правки из веб-морды, сделанные не с этого компьютера. `AGENTS.md` скрипт не сравнивает.
- Не добавлять секреты, URL камер, пароли и адреса в git. Новый секрет — `!secret`.
- Отопление менять в `automations/heating.yaml`, не размазывать по общему файлу. Синхронизатор котла — одна точка записи `climate.boiler_kotel`; не добавлять второй `set_hvac_mode` из других автоматизаций.
- Ручной оверрайд температуры с панели обязан сбрасывать `input_boolean.climate_daily`.
- Watchdog не должен рестартовать контроллер, если недоступна сеть целиком.
- Потолок 65 °C — осознанный лимит против дефолта прошивки 80 °C.
- Комментарии в yaml — часть документации.
