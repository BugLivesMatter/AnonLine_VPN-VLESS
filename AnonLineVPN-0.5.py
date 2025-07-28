import os
import sys
import json
import uuid
import subprocess
import winreg
import socket
import urllib.parse
import ctypes
import re
import time
import threading
import platform
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5 import QtGui
import signal
from datetime import datetime


class VlessVPNApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.xray_process = None
        self.is_connected = False
        self.saved_proxy = None
        self.local_port = 10808
        # Сохраненные настройки времени
        self.original_time_zone = None
        self.original_time_format = None
        self.time_server = "time.nist.gov"  # Сервер для синхронизации времени

        # Убираем стандартную рамку окна
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.initUI()
        self.load_settings()
        self.check_admin()
        # Обработка Ctrl+C в консоли
        signal.signal(signal.SIGINT, self.signal_handler)
        # Обработка системных событий закрытия
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Close:
            self.closeEvent(event)
            return True
        return super().eventFilter(obj, event)

    def signal_handler(self, signum, frame):
        """Обработка Ctrl+C и других сигналов"""
        self.restore_network_settings()
        QApplication.quit()

    def __del__(self):
        """Деструктор - последняя попытка восстановить настройки"""
        if self.is_connected:
            self.restore_network_settings()

    def initUI(self):
        self.setWindowTitle('NeonVLESS VPN')
        self.setFixedSize(600, 700)
        self.setWindowIcon(QIcon('icon.ico'))

        # Создаем главный контейнер с закругленными углами
        self.main_widget = QWidget()
        self.main_widget.setObjectName("mainWidget")
        self.setCentralWidget(self.main_widget)

        # Стиль приложения
        self.setStyleSheet("""
            #mainWidget {
                background-color: #0d1117;
                border-radius: 15px;
                border: 2px solid #00b4ff;
            }
            QGroupBox {
                color: #58a6ff;
                font-weight: bold;
                border: 1px solid #30363d;
                border-radius: 10px;
                margin-top: 1ex;
                background-color: #161b22;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
            QLineEdit {
                background-color: #0d1117;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 5px;
                padding: 5px;
                selection-background-color: #1c6ea4;
            }
            QTextEdit {
                background-color: #0d1117;
                color: #58a6ff;
                border: 1px solid #30363d;
                border-radius: 5px;
                font-family: Consolas;
            }
            QPushButton {
                background-color: #161b22;
                color: #58a6ff;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 8px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1c6ea4;
                color: #ffffff;
                border: 1px solid #58a6ff;
            }
            QPushButton:pressed {
                background-color: #0d2b4e;
            }
            QLabel {
                color: #8b949e;
            }
            #titleBar {
                background-color: transparent;
                padding: 5px;
                border-top-left-radius: 15px;
                border-top-right-radius: 15px;
            }
            #titleLabel {
                color: #58a6ff;
                font-weight: bold;
                font-size: 12pt;
            }
            #minimizeButton, #closeButton {
                background-color: transparent;
                border: none;
                color: #58a6ff;
                font-size: 14pt;
                padding: 0 10px;
            }
            #minimizeButton:hover, #closeButton:hover {
                color: #ffffff;
                background-color: #1c6ea4;
                border-radius: 4px;
            }
            #closeButton:hover {
                background-color: #8B0000;
            }
        """)

        # Главный лейаут
        main_layout = QVBoxLayout(self.main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Панель заголовка с кнопками управления
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(35)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(10, 0, 5, 0)

        # Заголовок приложения
        title_label = QLabel("AnonLine VPN")
        title_label.setObjectName("titleLabel")

        # Кнопки управления окном
        self.minimize_button = QPushButton("─")
        self.minimize_button.setObjectName("minimizeButton")
        self.minimize_button.setFixedSize(30, 25)
        self.minimize_button.clicked.connect(self.showMinimized)

        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("closeButton")
        self.close_button.setFixedSize(30, 25)
        self.close_button.clicked.connect(self.close_app)

        # Расположение элементов в заголовке
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.minimize_button)
        title_layout.addWidget(self.close_button)

        # Основной контент
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 10, 20, 20)
        content_layout.setSpacing(15)

        # Группа настроек
        settings_group = QGroupBox("VLESS Configuration")
        settings_layout = QVBoxLayout()

        key_layout = QHBoxLayout()
        self.key_label = QLabel("VLESS Key:")
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("vless://...")
        key_layout.addWidget(self.key_label)
        key_layout.addWidget(self.key_input)

        buttons_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Подключиться")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.change_key_btn = QPushButton("Изменить ключ")
        self.change_key_btn.clicked.connect(self.change_key)

        buttons_layout.addWidget(self.connect_btn)
        buttons_layout.addWidget(self.change_key_btn)

        settings_layout.addLayout(key_layout)
        settings_layout.addLayout(buttons_layout)
        settings_group.setLayout(settings_layout)

        # Группа консоли
        console_group = QGroupBox("Консоль вывода")
        console_layout = QVBoxLayout()
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        console_layout.addWidget(self.console)
        console_group.setLayout(console_layout)

        content_layout.addWidget(settings_group)
        content_layout.addWidget(console_group)

        # Группа настроек анонимности
        anonymity_group = QGroupBox("Настройки анонимности")
        anonymity_layout = QVBoxLayout()

        # Главный чекбокс максимальной анонимности
        self.max_anonymity_cb = QCheckBox("Максимальная анонимность")
        self.max_anonymity_cb.setChecked(True)
        self.max_anonymity_cb.stateChanged.connect(self.toggle_anonymity_options)

        # Дополнительные опции
        self.disable_ipv6_cb = QCheckBox("Отключить IPv6")
        self.block_webrtc_cb = QCheckBox("Блокировать WebRTC")
        self.firewall_killswitch_cb = QCheckBox("Активировать Firewall Kill-Switch")
        self.use_local_dns_cb = QCheckBox("Использовать локальный DNS")
        self.hide_system_time_cb = QCheckBox("Скрыть системное время (Долгое подключение)")

        # Группируем дополнительные опции
        options_layout = QVBoxLayout()
        options_layout.addWidget(self.disable_ipv6_cb)
        options_layout.addWidget(self.block_webrtc_cb)
        options_layout.addWidget(self.firewall_killswitch_cb)
        options_layout.addWidget(self.use_local_dns_cb)
        options_layout.addWidget(self.hide_system_time_cb)

        # Добавляем все в основную группу
        anonymity_layout.addWidget(self.max_anonymity_cb)
        anonymity_layout.addLayout(options_layout)
        anonymity_group.setLayout(anonymity_layout)

        # Добавляем группу настроек анонимности в основной интерфейс
        content_layout.addWidget(anonymity_group)
        content_layout.addWidget(settings_group)
        content_layout.addWidget(console_group)

        # Сборка всех компонентов
        main_layout.addWidget(title_bar)
        main_layout.addWidget(content_widget)

        # Таймер для проверки соединения
        self.connection_timer = QTimer(self)
        self.connection_timer.timeout.connect(self.check_connection)
        self.connection_timer.start(5000)

        # Неоновая тень
        self.set_neon_effect()

        self.log("Приложение инициализировано. Готово к подключению.")

    def toggle_anonymity_options(self, state):
        """Включает/выключает дополнительные опции анонимности"""
        enabled = state == Qt.Checked
        self.disable_ipv6_cb.setChecked(enabled)
        self.block_webrtc_cb.setChecked(enabled)
        self.firewall_killswitch_cb.setChecked(enabled)
        self.use_local_dns_cb.setChecked(enabled)
        self.hide_system_time_cb.setChecked(enabled)

        self.disable_ipv6_cb.setEnabled(not enabled)
        self.block_webrtc_cb.setEnabled(not enabled)
        self.firewall_killswitch_cb.setEnabled(not enabled)
        self.use_local_dns_cb.setEnabled(not enabled)
        self.hide_system_time_cb.setEnabled(not enabled)



    def set_neon_effect(self):
        """Добавляет неоновый эффект к окну"""
        self.shadow = QGraphicsDropShadowEffect()
        self.shadow.setBlurRadius(25)
        self.shadow.setColor(QColor(0, 180, 255, 200))
        self.shadow.setOffset(0, 0)
        self.main_widget.setGraphicsEffect(self.shadow)

    def log(self, message):
        """Выводит сообщение в консоль"""
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.console.append(f"[{timestamp}] {message}")
        self.console.ensureCursorVisible()

    def mousePressEvent(self, event):
        """Позволяет перемещать окно за заголовок"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Перемещение окна"""
        if hasattr(self, 'drag_position') and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def load_settings(self):
        """Загружает сохраненные настройки"""
        try:
            if os.path.exists("vless_settings.json"):
                with open("vless_settings.json", "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    self.key_input.setText(settings.get("key", ""))

                    # Загружаем состояние чекбоксов
                    self.max_anonymity_cb.setChecked(settings.get("max_anonymity", True))
                    self.disable_ipv6_cb.setChecked(settings.get("disable_ipv6", True))
                    self.block_webrtc_cb.setChecked(settings.get("block_webrtc", True))
                    self.firewall_killswitch_cb.setChecked(settings.get("firewall_killswitch", True))
                    self.use_local_dns_cb.setChecked(settings.get("use_local_dns", True))
                    self.hide_system_time_cb.setChecked(settings.get("hide_system_time", True))

                    # Активируем состояние зависимых чекбоксов
                    self.toggle_anonymity_options(
                        2 if self.max_anonymity_cb.isChecked() else 0
                    )

            self.load_saved_key()
        except Exception as e:
            self.log(f"Ошибка загрузки настроек: {str(e)}")

    def save_settings(self):
        """Сохраняет текущие настройки"""
        try:
            settings = {
                "key": self.key_input.text().strip(),
                "max_anonymity": self.max_anonymity_cb.isChecked(),
                "disable_ipv6": self.disable_ipv6_cb.isChecked(),
                "block_webrtc": self.block_webrtc_cb.isChecked(),
                "firewall_killswitch": self.firewall_killswitch_cb.isChecked(),
                "use_local_dns": self.use_local_dns_cb.isChecked(),
                "hide_system_time": self.hide_system_time_cb.isChecked(),
            }

            with open("vless_settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)

            return True
        except Exception as e:
            self.log(f"Ошибка сохранения настроек: {str(e)}")
            return False

    def hide_system_time(self):
        """Скрывает реальное системное время (устанавливает UTC, сохраняет текущее)"""
        try:
            # 1. Сохраняем текущий часовой пояс
            self.original_time_zone = subprocess.check_output(
                ['tzutil', '/g'],
                creationflags=subprocess.CREATE_NO_WINDOW,
                text=True
            ).strip()

            # 2. Сохраняем текущую дату и время
            self.original_datetime = datetime.now()

            # 3. Устанавливаем UTC
            subprocess.run(
                ['tzutil', '/s', 'UTC'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # 4. Отключаем авто-синхронизацию
            subprocess.run(
                ['w32tm', '/config', '/syncfromflags:manual', '/update'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # 5. Принудительная синхронизация с сервером
            subprocess.run(
                ['w32tm', '/resync', '/computer:' + self.time_server, '/nowait'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            self.log("Системное время скрыто (установлен UTC и синхронизировано с сервером)")
            return True
        except Exception as e:
            self.log(f"Ошибка скрытия времени: {str(e)}")
            return False

    def restore_system_time(self):
        """Восстанавливает исходный часовой пояс и дату/время"""
        try:
            # 1. Возвращаем часовой пояс
            if self.original_time_zone:
                subprocess.run(
                    ['tzutil', '/s', self.original_time_zone],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                self.log(f"Часовой пояс восстановлен: {self.original_time_zone}")

            # 2. Устанавливаем обратно дату и время
            if hasattr(self, 'original_datetime'):
                dt = self.original_datetime
                datetime_str = dt.strftime("%m-%d-%Y %H:%M:%S")

                subprocess.run(
                    ['powershell', '-Command', f'Set-Date -Date "{datetime_str}"'],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )

                self.log(f"Дата и время восстановлены: {datetime_str}")
            else:
                self.log("Предупреждение: сохранённое время не найдено")

            # 3. Возвращаем автоматическую синхронизацию
            subprocess.run(
                ['w32tm', '/config', '/syncfromflags:domhier', '/update'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            subprocess.run(
                ['w32tm', '/resync'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            return True
        except Exception as e:
            self.log(f"Ошибка восстановления времени: {str(e)}")
            return False


    def load_saved_key(self):
        """Загружает сохраненный ключ из файла с UTF-8"""
        try:
            if os.path.exists("vless_key.txt"):
                with open("vless_key.txt", "r", encoding="utf-8") as f:
                    key = f.read().strip()
                    if key.startswith("vless://"):
                        self.key_input.setText(key)
                        self.log("Ключ загружен из сохранения")
        except Exception as e:
            self.log(f"Ошибка загрузки ключа: {str(e)}")

    def save_key(self):
        """Сохраняет ключ в файл с UTF-8"""
        key = self.key_input.text().strip()
        if key.startswith("vless://"):
            try:
                with open("vless_key.txt", "w", encoding="utf-8") as f:
                    f.write(key)
                return True
            except Exception as e:
                self.log(f"Ошибка сохранения ключа: {str(e)}")
                return False
        return False

    def parse_vless_url(self, url):
        """Парсит VLESS-ссылку"""
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme != "vless":
                return None

            # Извлечение основных параметров
            netloc = parsed.netloc.split('@')
            if len(netloc) < 2:
                return None

            uuid = netloc[0]
            server_port = netloc[1].split(':')
            server = server_port[0]
            port = int(server_port[1]) if len(server_port) > 1 else 443

            query = urllib.parse.parse_qs(parsed.query)

            return {
                "uuid": uuid,
                "server": server,
                "port": port,
                "type": query.get('type', ['tcp'])[0],
                "security": query.get('security', ['reality'])[0],
                "fp": query.get('fp', ['chrome'])[0],
                "pbk": query.get('pbk', [''])[0],
                "sni": query.get('sni', [''])[0],
                "flow": query.get('flow', [''])[0],
                "sid": query.get('sid', [''])[0],
                "spx": query.get('spx', ['/'])[0],
                "fragment": parsed.fragment
            }
        except Exception as e:
            self.log(f"Ошибка парсинга URL: {str(e)}")
            return None

    def generate_xray_config(self, params):
        """Генерирует конфиг для Xray с максимальными настройками анонимности"""
        config = {
            "log": {
                "loglevel": "warning"
            },
            "inbounds": [
                {
                    "port": self.local_port,
                    "protocol": "socks",
                    "settings": {
                        "auth": "noauth",
                        "udp": True,
                        "ip": "127.0.0.1"
                    },
                    "sniffing": {
                        "enabled": True,
                        "destOverride": ["http", "tls", "fakedns"],
                        "routeOnly": True
                    }
                },
                {
                    "port": 53,
                    "protocol": "dokodemo-door",
                    "settings": {
                        "address": "1.1.1.1",
                        "port": 53,
                        "network": "tcp,udp"
                    },
                    "tag": "dns-inbound"
                }
            ],
            "outbounds": [
                {
                    "protocol": "vless",
                    "settings": {
                        "vnext": [
                            {
                                "address": params["server"],
                                "port": params["port"],
                                "users": [
                                    {
                                        "id": params["uuid"],
                                        "flow": params["flow"],
                                        "encryption": "none"
                                    }
                                ]
                            }
                        ]
                    },
                    "streamSettings": {
                        "network": params["type"],
                        "security": params["security"],
                        "realitySettings": {
                            "serverName": params["sni"],
                            "publicKey": params["pbk"],
                            "fingerprint": params["fp"],
                            "shortId": params["sid"],
                            "spiderX": params["spx"]
                        }
                    },
                    "tag": "proxy"
                },
                {
                    "protocol": "freedom",
                    "settings": {
                        "domainStrategy": "UseIPv4"
                    },
                    "tag": "direct"
                },
                {
                    "protocol": "blackhole",
                    "tag": "block"
                }
            ],
            "routing": {
                "domainStrategy": "IPOnDemand",
                "rules": [
                    {
                        "type": "field",
                        "inboundTag": ["dns-inbound"],
                        "outboundTag": "proxy"
                    },
                    {
                        "type": "field",
                        "ip": ["geoip:private"],
                        "outboundTag": "direct"
                    },
                    {
                        "type": "field",
                        "ip": ["geoip:cn"],
                        "outboundTag": "direct"
                    },
                    {
                        "type": "field",
                        "protocol": ["bittorrent"],
                        "outboundTag": "block"
                    },
                    # Блокировка IPv6
                    {
                        "type": "field",
                        "ip": ["::/0"],
                        "outboundTag": "block"
                    },
                    # Блокировка STUN (WebRTC)
                    {
                        "type": "field",
                        "port": "3478,3479,5349,5350,5351,19302,19305,19307-19309",
                        "outboundTag": "block"
                    },
                    {
                        "type": "field",
                        "port": "0-65535",
                        "outboundTag": "proxy"
                    }
                ]
            },
            "dns": {
                "servers": [
                    "1.1.1.1",
                    "8.8.8.8",
                    {
                        "address": "1.1.1.1",
                        "domains": ["geosite:geolocation-!cn"]
                    },
                    {
                        "address": "223.5.5.5",
                        "domains": ["geosite:cn"]
                    },
                    "localhost"
                ],
                "queryStrategy": "UseIPv4"
            }
        }

        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)

        return os.path.abspath("config.json")

    def disable_ipv6(self):
        """Отключает IPv6 для всех интерфейсов"""
        try:
            # Для Windows 10/11
            if platform.system() == "Windows":
                # Отключаем IPv6 для всех интерфейсов
                subprocess.run(
                    ['netsh', 'interface', 'ipv6', 'set', 'global', 'state=disabled'],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                self.log("IPv6 полностью отключен в системе")

            return True
        except Exception as e:
            self.log(f"Ошибка отключения IPv6: {str(e)}")
            return False

    def enable_ipv6(self):
        """Включает IPv6 обратно"""
        try:
            if platform.system() == "Windows":
                subprocess.run(
                    ['netsh', 'interface', 'ipv6', 'set', 'global', 'state=enabled'],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                self.log("IPv6 включен обратно")

            return True
        except Exception as e:
            self.log(f"Ошибка включения IPv6: {str(e)}")
            return False

    def block_webrtc(self):
        """Блокирует WebRTC на уровне системы и браузера"""
        try:
            # Добавляем блокировку в файл hosts
            hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
            webrtc_blocks = [
                "\n# Блокировка WebRTC",
                "0.0.0.0 stun.l.google.com",
                "0.0.0.0 stun1.l.google.com",
                "0.0.0.0 stun2.l.google.com",
                "0.0.0.0 stun3.l.google.com",
                "0.0.0.0 stun4.l.google.com",
                "0.0.0.0 stun.services.mozilla.com",
                "0.0.0.0 global.stun.twilio.com"
            ]

            with open(hosts_path, "a", encoding="utf-8") as f:
                f.write("\n".join(webrtc_blocks))

            self.log("WebRTC серверы заблокированы через hosts файл")
            return True
        except Exception as e:
            self.log(f"Ошибка блокировки WebRTC: {str(e)}")
            return False

    def unblock_webrtc(self):
        """Восстанавливает файл hosts"""
        try:
            hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
            with open(hosts_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Удаляем наши блокировки
            new_lines = [line for line in lines if "stun" not in line and "WebRTC" not in line]

            with open(hosts_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            self.log("WebRTC блокировки удалены")
            return True
        except Exception as e:
            self.log(f"Ошибка восстановления hosts: {str(e)}")
            return False

    def create_firewall_rules(self):
        """Создает правила брандмауэра для полной изоляции"""
        try:
            # Блокируем все исходящие соединения, кроме VPN
            subprocess.run(
                ['netsh', 'advfirewall', 'firewall', 'add', 'rule',
                 'name="VPN Kill Switch"', 'dir=out', 'action=block', 'enable=yes'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # Разрешаем только наш VPN
            subprocess.run(
                ['netsh', 'advfirewall', 'firewall', 'add', 'rule',
                 'name="Allow Xray"', 'dir=out', 'action=allow', 'program="' + os.path.abspath("xray.exe") + '"',
                 'enable=yes'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            self.log("Создан kill-switch в брандмауэре")
            return True
        except Exception as e:
            self.log(f"Ошибка создания правил брандмауэра: {str(e)}")
            return False

    def remove_firewall_rules(self):
        """Удаляет правила брандмауэра"""
        try:
            subprocess.run(
                ['netsh', 'advfirewall', 'firewall', 'delete', 'rule',
                 'name="VPN Kill Switch"', 'dir=out'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            subprocess.run(
                ['netsh', 'advfirewall', 'firewall', 'delete', 'rule',
                 'name="Allow Xray"', 'dir=out'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.log("Правила брандмауэра удалены")
            return True
        except Exception as e:
            self.log(f"Ошибка удаления правил брандмауэра: {str(e)}")
            return False

    def set_dns(self):
        """Устанавливает DNS-серверы для предотвращения утечек"""
        try:
            # Получаем имя активного интерфейса
            result = subprocess.run(
                ['netsh', 'interface', 'show', 'interface'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            interfaces = result.stdout.split('\n')
            active_interface = "Ethernet"  # значение по умолчанию
            for line in interfaces:
                if "Connected" in line and "Loopback" not in line:
                    parts = line.split()
                    if len(parts) > 3:
                        active_interface = parts[-1]
                        break

            # Устанавливаем DNS на 127.0.0.1
            subprocess.run(
                ['netsh', 'interface', 'ipv4', 'set', 'dnsservers',
                 f'name="{active_interface}"', 'source=static', 'address=127.0.0.1', 'register=primary'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            self.log("DNS настроены на 127.0.0.1 для предотвращения утечек")
            return True
        except Exception as e:
            self.log(f"Ошибка настройки DNS: {str(e)}")
            return False

    def restore_dns(self):
        """Восстанавливает DNS-настройки"""
        try:
            # Получаем имя активного интерфейса
            result = subprocess.run(
                ['netsh', 'interface', 'show', 'interface'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            interfaces = result.stdout.split('\n')
            active_interface = "Ethernet"  # значение по умолчанию
            for line in interfaces:
                if "Connected" in line and "Loopback" not in line:
                    parts = line.split()
                    if len(parts) > 3:
                        active_interface = parts[-1]
                        break

            # Восстанавливаем автоматическое получение DNS
            subprocess.run(
                ['netsh', 'interface', 'ipv4', 'set', 'dnsservers',
                 f'name="{active_interface}"', 'source=dhcp'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            self.log("DNS настройки восстановлены")
            return True
        except Exception as e:
            self.log(f"Ошибка восстановления DNS: {str(e)}")
            return False

    def save_network_settings(self):
        """Сохраняет текущие сетевые настройки"""
        try:
            # Сохраняем настройки прокси
            reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            try:
                key = winreg.OpenKey(reg, key_path, 0, winreg.KEY_READ)
            except:
                self.saved_proxy = {"enabled": 0, "server": "", "override": ""}
                return True

            try:
                enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            except:
                enabled = 0

            try:
                server, _ = winreg.QueryValueEx(key, "ProxyServer")
            except:
                server = ""

            try:
                override, _ = winreg.QueryValueEx(key, "ProxyOverride")
            except:
                override = ""

            winreg.CloseKey(key)

            self.saved_proxy = {
                "enabled": enabled,
                "server": server,
                "override": override
            }

            self.log("Сетевые настройки сохранены")
            return True
        except Exception as e:
            self.log(f"Ошибка сохранения настроек: {str(e)}")
            return False

    def set_proxy(self):
        """Устанавливает прокси-настройки"""
        try:
            reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(reg, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                                 0, winreg.KEY_WRITE)

            # Включаем прокси
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)

            # Устанавливаем SOCKS прокси
            proxy_str = f"socks=127.0.0.1:{self.local_port}"
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_str)

            # Локальные адреса без прокси
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "<local>")

            winreg.CloseKey(key)

            # Применяем изменения
            subprocess.call(["netsh", "winhttp", "import", "proxy", "source=ie"])
            self.log(f"Прокси настроен: SOCKS 127.0.0.1:{self.local_port}")
            return True
        except Exception as e:
            self.log(f"Ошибка настройки прокси: {str(e)}")
            return False

    def restore_network_settings(self):
        """Восстанавливает все настройки с улучшенной обработкой ошибок"""
        try:
            restore_success = True

            if self.is_connected:
                # Восстановление прокси
                if self.saved_proxy:
                    try:
                        reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                        key = winreg.OpenKey(
                            reg,
                            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                            0,
                            winreg.KEY_WRITE
                        )

                        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, self.saved_proxy["enabled"])
                        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, self.saved_proxy["server"])
                        winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, self.saved_proxy["override"])

                        winreg.CloseKey(key)

                        # Применяем изменения
                        subprocess.call(["netsh", "winhttp", "import", "proxy", "source=ie"])
                        self.log("Настройки прокси восстановлены")
                    except Exception as e:
                        self.log(f"Ошибка восстановления прокси: {str(e)}")
                        restore_success = False

                # Восстановление DNS (если использовали локальный DNS)
                if self.use_local_dns_cb.isChecked():
                    try:
                        self.restore_dns()
                    except Exception as e:
                        self.log(f"Ошибка восстановления DNS: {str(e)}")
                        restore_success = False

                # Включение IPv6 обратно (если отключали)
                if self.disable_ipv6_cb.isChecked():
                    try:
                        self.enable_ipv6()
                    except Exception as e:
                        self.log(f"Ошибка включения IPv6: {str(e)}")
                        restore_success = False

                # Разблокировка WebRTC (если блокировали)
                if self.block_webrtc_cb.isChecked():
                    try:
                        self.unblock_webrtc()
                    except Exception as e:
                        self.log(f"Ошибка разблокировки WebRTC: {str(e)}")
                        restore_success = False

                # Удаление firewall kill-switch (если создавали)
                if self.firewall_killswitch_cb.isChecked():
                    try:
                        self.remove_firewall_rules()
                    except Exception as e:
                        self.log(f"Ошибка удаления правил брандмауэра: {str(e)}")
                        restore_success = False

                # Восстановление времени (если изменяли)
                if self.hide_system_time_cb.isChecked():
                    try:
                        self.restore_system_time()
                    except Exception as e:
                        self.log(f"Ошибка восстановления времени: {str(e)}")
                        restore_success = False

                # Завершение Xray
                try:
                    self.kill_xray_processes()
                    self.xray_process = None
                    self.is_connected = False
                    self.connect_btn.setText("Подключиться")
                    self.connect_btn.setStyleSheet("")
                except Exception as e:
                    self.log(f"Ошибка завершения Xray: {str(e)}")
                    restore_success = False

            return restore_success

        except Exception as e:
            self.log(f"Критическая ошибка при восстановлении: {str(e)}")
            return False

    def closeEvent(self, event):
        """Обработка события закрытия окна с подтверждением"""
        if self.is_connected:
            reply = QMessageBox.question(
                self,
                'Подтверждение отключения',
                'VPN подключен! Вы действительно хотите закрыть приложение?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                if self.restore_network_settings():
                    event.accept()
                else:
                    self.log("Не удалось восстановить настройки сети!")
                    event.ignore()
            else:
                event.ignore()
        else:
            event.accept()

    def start_xray(self, config_path):
        """Запускает Xray с выбранными настройками анонимности"""
        try:
            xray_path = "xray.exe"
            if not os.path.exists(xray_path):
                self.log("Ошибка: xray.exe не найден в папке приложения")
                return False

            # Закрываем предыдущие экземпляры Xray
            self.kill_xray_processes()

            # Отключаем IPv6 (если выбрано)
            if self.disable_ipv6_cb.isChecked():
                if not self.disable_ipv6():
                    self.log("Предупреждение: не удалось отключить IPv6")

            # Блокируем WebRTC (если выбрано)
            if self.block_webrtc_cb.isChecked():
                if not self.block_webrtc():
                    self.log("Предупреждение: не удалось заблокировать WebRTC")

            # Создаем firewall kill-switch (если выбрано)
            if self.firewall_killswitch_cb.isChecked():
                if not self.create_firewall_rules():
                    self.log("Предупреждение: не удалось создать правила брандмауэра")

            # Запускаем Xray
            self.xray_process = subprocess.Popen(
                [xray_path, "run", "-c", config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # Поток для чтения вывода Xray
            self.log_thread = XrayLogThread(self.xray_process.stdout)
            self.log_thread.log_signal.connect(self.log)
            self.log_thread.start()

            # Даем Xray время на запуск
            QTimer.singleShot(100, lambda: self.log("Xray запущен с выбранными настройками анонимности"))


            # Настраиваем DNS (если выбрано)
            if self.use_local_dns_cb.isChecked():
                if not self.set_dns():
                    self.log("Предупреждение: не удалось настроить DNS, возможны утечки")

            # Скрываем системное время (если выбрано)
            if self.hide_system_time_cb.isChecked():
                if not self.hide_system_time():
                    self.log("Предупреждение: не удалось скрыть системное время")

            return True
        except Exception as e:
            self.log(f"Ошибка запуска Xray: {str(e)}")

            # В случае ошибки пытаемся восстановить настройки
            self.restore_network_settings()
            return False

    def kill_xray_processes(self):
        """Завершает все процессы xray.exe"""
        try:
            subprocess.run(
                ['taskkill', '/F', '/IM', 'xray.exe'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            time.sleep(1)
            self.log("Процессы Xray завершены")
        except Exception as e:
            self.log(f"Ошибка завершения Xray: {str(e)}")

    def check_admin(self):
        """Проверяет права администратора"""
        try:
            if not ctypes.windll.shell32.IsUserAnAdmin():
                self.log("ТРЕБУЮТСЯ ПРАВА АДМИНИСТРАТОРА!")
                self.log("Перезапустите приложение от имени администратора")
        except:
            pass

    def check_connection(self):
        """Проверяет активное подключение"""
        if self.is_connected:
            try:
                # Создаем временный сокет для проверки
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                s.connect(("www.google.com", 80))
                s.close()
                self.connect_btn.setStyleSheet("background-color: #006400; color: white;")
                return True
            except:
                self.connect_btn.setStyleSheet("background-color: #8B0000; color: red;")
                self.log("Нет интернет-соединения")
                return False
        else:
            self.connect_btn.setStyleSheet("")
            return False

    def toggle_connection(self):
        """Переключает состояние подключения"""
        if self.is_connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        """Устанавливает соединение"""
        self.log("Сохраняем настройки...")
        QApplication.processEvents()  # Это позволяет не блокировать GUI
        if not self.save_settings():
            self.log("Ошибка: Не удалось сохранить настройки")
            return



        self.log("Парсим VLESS URL...")
        vless_url = self.key_input.text().strip()
        if not vless_url.startswith("vless://"):
            self.log("Ошибка: Неверный формат VLESS-ключа")
            return

        self.log("Генерируем конфиг...")
        params = self.parse_vless_url(vless_url)
        if not params:
            self.log("Ошибка: Не удалось разобрать VLESS-ключ")
            return

        # Сохраняем текущие настройки сети
        if not self.save_network_settings():
            self.log("Ошибка: Не удалось сохранить сетевые настройки")
            return

        # Генерируем конфиг для Xray
        config_path = self.generate_xray_config(params)
        self.log(f"Конфиг сгенерирован: {config_path}")

        self.log("Запускаем Xray...")
        # Запускаем Xray
        if not self.start_xray(config_path):
            self.log("Ошибка: Не удалось запустить Xray")
            self.restore_network_settings()
            return

        self.log("Настраиваем прокси...")
        # Настраиваем прокси
        if not self.set_proxy():
            self.log("Ошибка: Не удалось настроить прокси")
            self.restore_network_settings()
            return

        self.is_connected = True
        self.connect_btn.setText("Отключить")

        # Проверяем соединение
        if self.check_connection():
            self.log("VPN подключен! Ваш IP изменен.")
        else:
            self.log("VPN подключен, но интернет недоступен. Проверьте ключ.")

    def disconnect(self):
        """Разрывает соединение"""
        self.log("Отключение VPN...")
        if self.restore_network_settings():
            self.log("VPN отключен. Настройки сети восстановлены")
        else:
            self.log("Ошибка при отключении VPN")

    def change_key(self):
        """Изменяет ключ"""
        if self.is_connected:
            self.disconnect()
        self.key_input.clear()
        self.key_input.setFocus()
        self.log("Готов к вводу нового ключа")

    def close_app(self):
        """Закрывает приложение"""
        if self.is_connected:
            self.disconnect()
        self.close()



class XrayLogThread(QThread):
    """Поток для чтения логов Xray"""
    log_signal = pyqtSignal(str)

    def __init__(self, stdout):
        super().__init__()
        self.stdout = stdout

    def run(self):
        while True:
            line = self.stdout.readline()
            if not line:
                break
            self.log_signal.emit(line.strip())


if __name__ == "__main__":
    def is_admin():
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False


    if not is_admin():
        # Запуск с правами администратора
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, None, 1)
        sys.exit(0)

    app = QApplication(sys.argv)

    # Установка стиля для приложения
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QColor(13, 17, 23))
    palette.setColor(QtGui.QPalette.WindowText, QColor(200, 200, 200))
    app.setPalette(palette)

    window = VlessVPNApp()
    window.show()
    sys.exit(app.exec_())