# AnonLine VPN (VLESS + Reality)

Небольшой VPN-клиент для подключения к серверам по **VLESS-протоколу** с поддержкой **security = reality**.  
Проект собран на **Python + PyQt5**, с использованием [Xray-core](https://github.com/XTLS/Xray-core) в качестве backend-движка.

---

## 🚀 Возможности
- Подключение к VLESS-серверу через графический интерфейс (PyQt5).
- Поддержка `security = reality`.
- Работа с ключами формата VLESS.
- Простая конфигурация и запуск.
- Компиляция в standalone `.exe` (через PyInstaller).

---

## 📦 Установка и запуск

### 1. Скачайте Xray-core
Для работы обязательно нужен [Xray-core](https://github.com/XTLS/Xray-core/releases).  
Скачайте архив для вашей платформы и распакуйте его рядом с клиентом.

### 2. Запуск из исходников
```bash
git clone https://github.com/USERNAME/AnonLine_VPN-VLESS.git
cd AnonLine_VPN-VLESS
pip install -r requirements.txt
python main.py
