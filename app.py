from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
import random
from datetime import datetime
import requests
import os
import firebase_admin
from firebase_admin import credentials, auth, firestore
import socket
import uuid
import platform
import psutil
import subprocess
import pythoncom
import wmi
from flask import render_template
import time
last_status = {}
last_update = 0

def get_cached_status():
    global last_status, last_update
    if time.time() - last_update > 10:
        last_status = get_real_status()
        last_update = time.time()
    return last_status



def log_action(user_email, action, equipment_id, details):
    try:
        # Получаем название оборудования (если оно есть)
        equipment_name = "Неизвестно"
        equipment_doc = db.collection("equipment").document(equipment_id).get()
        if equipment_doc.exists:
            equipment_data = equipment_doc.to_dict()
            equipment_name = equipment_data.get("name", "Без названия")
            details = f"{details} (устройство: {equipment_name})"

        db.collection("logs").add({
            "timestamp": datetime.now().isoformat(),
            "user": user_email,
            "action": action,
            "equipment_id": equipment_id,
            "equipment_name": equipment_name,
            "details": details
        })

    except Exception as e:
        print("Ошибка логирования:", e)



def get_device_info():
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff)
                    for i in range(0, 8 * 6, 8)][::-1])
    os_info = platform.platform()
    return {
        'hostname': hostname,
        'ip': ip,
        'mac': mac,
        'os': os_info
    }


def get_ping(host="8.8.8.8"):
    try:
        output = subprocess.check_output(["ping", "-n", "1", host], universal_newlines=True)
        for line in output.splitlines():
            if "время=" in line.lower() or "time=" in line.lower():
                time_part = [s for s in line.split() if "мс" in s or "ms" in s]
                if time_part:
                    return float(''.join(filter(str.isdigit, time_part[0])))
    except:
        return 0

#def get_real_status():
  #  cpu = psutil.cpu_percent(interval=1)
 #   memory = psutil.virtual_memory().percent
  #  net = psutil.net_io_counters()
  #  network = (net.bytes_sent + net.bytes_recv) / 1024 / 1024  # MB
  #  response_time = get_ping()
  #  temperature = 0  # Заглушка: можно добавить с помощью внешних средств

  #  try:
        # Возвращает список температурных датчиков процессора
  #      temperature = psutil.sensors_temperatures().get('coretemp', [])[0].current
   # except (AttributeError, IndexError):
   #     temperature = None  # Если температура не доступна

   # return {
   #     'cpu': round(cpu, 1),
   ##     'memory': round(memory, 1),
   ##     'network': round(network, 2),
   #     'response': round(response_time, 1),
    #    'temperature': temperature,
   ##    'last_update': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
   # }

# Инициализация Firebase
cred = credentials.Certificate("firebase_key.json")  # Замените на путь к вашему ключу
firebase_admin.initialize_app(cred)
db = firestore.client()

# Авторизация Firebase
def firebase_sign_in(email, password):
    api_key = "AIzaSyBIfo4aAC4ASDXB29kL2rAqb2URHmGJWuU"
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    response = requests.post(url, json=payload)
    return response.json()

app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route("/delete_equipment/<equipment_id>", methods=["POST"])
def delete_equipment(equipment_id):
    if "user" not in session:
        return redirect(url_for("login"))

    try:
        db.collection('equipment').document(equipment_id).delete()

        # ЛОГИРУЕМ УДАЛЕНИЕ после успешного удаления
        log_action(
            user_email=session["user"]["email"],
            action="deleted",
            equipment_id=equipment_id,
            details="Оборудование удалено"
        )

        flash("Оборудование успешно удалено.", "success")
    except Exception as e:
        flash(f"Ошибка при удалении оборудования: {e}", "danger")

    return redirect(url_for('index'))


@app.route("/edit/<equipment_id>", methods=["POST"])
def edit_equipment(equipment_id):
    new_ip = request.form['ip']  # например, поле в форме

    db.collection('equipment').document(equipment_id).update({
        "ip": new_ip
    })

    # ЛОГИРУЕМ ОБНОВЛЕНИЕ
    log_action(
        user_email=session["user"]["email"],
        action="updated",
        equipment_id=equipment_id,
        details=f"IP изменён на {new_ip}"
    )
    return redirect(url_for('index'))

# Регистрация
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            # Создание пользователя в Firebase Auth
            user = auth.create_user(email=email, password=password)
            
            # Добавление данных в Firestore
            db.collection('users').document(user.uid).set({
                'email': email,
                'role': 'user'
            })

            flash('Регистрация прошла успешно. Войдите в аккаунт.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            flash(f'Ошибка при регистрации: {e}', 'danger')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        result = firebase_sign_in(email, password)

        if "idToken" in result:
            session["user"] = {
                "email": result["email"],
                "idToken": result["idToken"]
            }
            flash("Вы успешно вошли!", "success")
            return redirect(url_for("index"))
        else:
            flash("Ошибка входа: " + result.get("error", {}).get("message", "Неизвестная ошибка"), "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы.")
    return redirect(url_for("login"))



# Главная страница
@app.route("/", methods=["GET", "POST"])
def index():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form['name']
        description = request.form['description']
        device_type = request.form['type']  # получаем тип из формы

        doc_ref = db.collection('equipment').document()

        # Базовые поля
        data = {
            'name': name,
            'description': description,
            'type': device_type,
            'last_update': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Генерация параметров по типу
        if device_type == 'pc':
            fake = generate_fake_status()
            data.update({
                'cpu': fake['cpu'],
                'memory': fake['memory'],
                'temperature': fake['temperature'],
                'ip': fake['ip'],
                'os': fake['os']
            })

        elif device_type == 'server':
            fake = generate_fake_status()
            data.update({
                'cpu': fake['cpu'],
                'memory': fake['memory'],
                'temperature': fake['temperature'],
                'ip': fake['ip'],
                'os': fake['os'],
                'uptime': f"{random.randint(1, 90)} дней",
                'roles': random.choice(["БД", "Web", "Файловый"])
            })

        elif device_type == 'network':
            data.update({
                'ip': "192.168.0." + str(random.randint(1, 254)),
                'ping': random.randint(1, 100),
                'traffic': round(random.uniform(1.0, 100.0), 2),
                'port_status': random.choice(["OK", "Warning", "Offline"])
            })

        elif device_type == 'peripheral':
            data.update({
                'ip': "192.168.0." + str(random.randint(1, 254)),
                'status': random.choice(["Готов", "Ошибка", "Офлайн"]),
                'toner': random.randint(10, 100)
            })

        doc_ref.set(data)

        # Логируем
        log_action(
            user_email=session.get("user", {}).get("email", "unknown"),
            action='added',
            equipment_id=doc_ref.id,
            details=f"Добавлено устройство: {name} (тип: {device_type})"
        )


    # 1. Получаем список устройств
    equipment_docs = db.collection('equipment').stream()

    for doc in equipment_docs:
        status = get_cached_status()
        db.collection('equipment').document(doc.id).update(status)

        # Добавляем запись в историю
        db.collection('device_history').add({
            'device_id': doc.id,
            'timestamp': datetime.now(),
            'cpu': status['cpu'],
            'memory': status['memory']
        })

        # Логируем
        log_action(
            user_email=session.get("user", {}).get("email", "unknown"),
            action='updated',
            equipment_id=doc.id,
            details="Обновлен статус оборудования"
        )

    # 3. Снова получаем обновленные данные
    updated_docs = db.collection('equipment').stream()
    equipment = []
    for doc in updated_docs:
        data = doc.to_dict()
        data['id'] = doc.id
        equipment.append(data)


    return render_template("index.html", equipment=equipment)


@app.route('/archive_equipment/<equipment_id>', methods=['POST'])
def archive_equipment(equipment_id):
    if "user" not in session:
        return redirect(url_for("login"))

    try:
        # Получаем данные устройства
        doc = db.collection('equipment').document(equipment_id).get()
        if doc.exists:
            data = doc.to_dict()
            # Переносим данные в архив
            db.collection('archived_equipment').add(data)
            # Удаляем из текущей коллекции
            db.collection('equipment').document(equipment_id).delete()

            # Логируем действие
            log_action(
                user_email=session["user"]["email"],
                action="archived",
                equipment_id=equipment_id,
                details=f"Оборудование '{data.get('name')}' было архивировано"
            )

            flash("Оборудование архивировано", "success")
        else:
            flash("Оборудование не найдено", "danger")

    except Exception as e:
        flash(f"Ошибка при архивировании: {e}", "danger")

    return redirect(url_for('index'))

@app.route('/restore/<device_id>', methods=['POST'])
def restore(device_id):
    archived_ref = db.collection('archived_equipment').document(device_id)
    archived_data = archived_ref.get().to_dict()
    
    if archived_data:
        db.collection('equipment').document(device_id).set(archived_data)
        archived_ref.delete()  # Удаляем из архива

        # Логирование восстановления
        log_action(
            user_email=session["user"]["email"],  # Получаем email пользователя
            action="restored",  # Действие — восстановлено
            equipment_id=device_id,  # ID устройства
            details=f'Восстановлено устройство {archived_data["name"]}'  # Подробности
        )
    
    return redirect(url_for('archive'))


from datetime import datetime

@app.route('/device/<device_id>')
def device_detail(device_id):
    device_doc = db.collection('equipment').document(device_id).get()
    device = device_doc.to_dict() if device_doc.exists else None

    if not device:
        archived_doc = db.collection('archived_equipment').document(device_id).get()
        device = archived_doc.to_dict() if archived_doc.exists else None
    if not device:
        flash("Устройство не найдено", "danger")
        return redirect(url_for('index'))

    device_type = device.get("type", "unknown")

    # Графики — подгружаем историю
    history_ref = db.collection('device_history').where('device_id', '==', device_id).order_by("timestamp")
    history = history_ref.stream()

    history_data = {
        'dates': [],
        'cpu': [],
        'memory': [],
        'ping': [],
        'traffic': [],
        'toner': []
    }

    for record in history:
        data = record.to_dict()
        timestamp = data.get('timestamp')
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            timestamp_str = str(timestamp)

        history_data['dates'].append(timestamp_str)
        history_data['cpu'].append(data.get('cpu', 0))
        history_data['memory'].append(data.get('memory', 0))
        history_data['ping'].append(data.get('ping', 0))
        history_data['traffic'].append(data.get('traffic', 0))
        history_data['toner'].append(data.get('toner', 0))

    # Получаем действия (логи) по устройству
    logs_ref = db.collection("logs")\
    .where("equipment_id", "==", device_id)\
    .order_by("timestamp", direction=firestore.Query.DESCENDING)\
    .order_by("__name__", direction=firestore.Query.DESCENDING)




    logs = [doc.to_dict() for doc in logs_ref.stream()]

    return render_template('device_detail.html',
                      device=device,
                      device_type=device.get("type", "unknown"),
                      history_data=history_data,
                      logs=logs,
                      device_id=device_id)  # ← вот это добавлено


@app.route('/archive')
def archive():
    archived_equipment = []
    try:
        docs = db.collection('archived_equipment').stream()
        for doc in docs:
            equipment = doc.to_dict()
            equipment['id'] = doc.id
            archived_equipment.append(equipment)
        print("Архив:", archived_equipment)
    except Exception as e:
        print("Ошибка при получении архива:", e)

    return render_template('archive.html', equipment=archived_equipment)

def get_archived_equipment():
    archived_equipment = []
    docs = db.collection('archive').stream()
    for doc in docs:
        equipment = doc.to_dict()
        equipment['id'] = doc.id
        archived_equipment.append(equipment)
    return archived_equipment

    # Обновление статуса оборудования
def get_ping(host="8.8.8.8"):
    try:
        output = subprocess.check_output(["ping", "-n", "1", host], universal_newlines=True)
        for line in output.splitlines():
            if "время=" in line.lower() or "time=" in line.lower():
                time_part = [s for s in line.split() if "мс" in s or "ms" in s]
                if time_part:
                    return float(''.join(filter(str.isdigit, time_part[0])))
    except:
        pass  # Не выводим ошибку

    return 0.0  # <-- важно!



def get_real_status():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    net = psutil.net_io_counters()
    network = (net.bytes_sent + net.bytes_recv) / 1024 / 1024  # MB
    response_time = get_ping()

    try:
        temperature = psutil.sensors_temperatures().get('coretemp', [])[0].current
    except (AttributeError, IndexError):
        temperature = None

    return {
        'cpu': round(cpu, 1),
        'memory': round(memory, 1),
        'network': round(network, 2),
        'response': round(response_time, 1),
        'temperature': temperature,
        'last_update': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def generate_fake_status():
    return {
        'cpu': random.randint(10, 90),
        'memory': random.randint(20, 90),
        'network': round(random.uniform(0.1, 50.0), 2),
        'response': random.randint(1, 100),
        'temperature': round(random.uniform(30.0, 70.0), 1),
        'ip': "192.168.1." + str(random.randint(2, 254)),
        'os': random.choice(["Windows 11", "Ubuntu 22.04", "Debian", "macOS"]),
        'mac': f"{random.randint(0,255):02x}:{random.randint(0,255):02x}:{random.randint(0,255):02x}:{random.randint(0,255):02x}:{random.randint(0,255):02x}:{random.randint(0,255):02x}",
        'last_update': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

        
from flask import Response

@app.route('/export_logs')
def export_logs():
    logs_ref = db.collection('logs').order_by('timestamp', direction=firestore.Query.DESCENDING)
    logs = [doc.to_dict() for doc in logs_ref.stream()]

    lines = []
    for log in logs:
        lines.append(
            f"[{log.get('timestamp')}] {log.get('user')} - {log.get('action')} - ID: {log.get('equipment_id')} - {log.get('details')}"
        )

    # Формируем текст для файла
    log_text = "\n".join(lines)

    return Response(
        log_text,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment; filename=logs.txt"}
    )


@app.route("/logs/clear", methods=["POST"])
def clear_logs():
    logs_ref = db.collection("logs").stream()
    for doc in logs_ref:
        doc.reference.delete()
    
    flash("История логов очищена.", "success")
    return redirect(url_for("view_logs"))


@app.route("/api/equipment")
def api_equipment():
    equipment = []
    equipment_docs = db.collection('equipment').stream()
    for doc in equipment_docs:
        data = doc.to_dict()
        data['id'] = doc.id
        equipment.append(data)
    return jsonify(equipment)

@app.route('/logs')
def view_logs():
    logs_ref = db.collection('logs').order_by('timestamp', direction=firestore.Query.DESCENDING)
    logs = [doc.to_dict() for doc in logs_ref.stream()]
    return render_template('logs.html', logs=logs)

@app.route('/get_status', methods=["GET"])
def get_status():
    equipment = []
    equipment_docs = db.collection('equipment').stream()
    
    for doc in equipment_docs:
        device = doc.to_dict()
        device['id'] = doc.id
        device_type = device.get("type")

        status = get_real_status()

        if device_type == "pc":
            update_fields = {
                'cpu': status['cpu'],
                'memory': status['memory'],
                'temperature': status['temperature']
            }

        elif device_type == "server":
            update_fields = {
                'cpu': status['cpu'],
                'memory': status['memory'],
                'response': status['response']
            }

        elif device_type == "network":
            update_fields = {
                'network': status['network'],
                'response': status['response']
            }

        else:
            continue  # не обновляем другие

        update_fields["last_update"] = status["last_update"]
        db.collection('equipment').document(doc.id).update(update_fields)

        # логирование в логах
        log_action(
            user_email="system",
            action="auto_update",
            equipment_id=doc.id,
            details=f"Автообновление: {update_fields}"
        )

        device.update(update_fields)
        equipment.append(device)

    return jsonify(equipment)






# Страница добавления оборудования
@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        name = request.form['name']
        description = request.form['description']

        # Добавление оборудования
        _, doc_ref = db.collection('equipment').add({
        'name': name,
        'description': description,
        'temperature': round(random.uniform(30, 60), 1),
        'cpu': random.randint(10, 90),
        'memory': random.randint(20, 90),
        'network': round(random.uniform(0.1, 50.0), 2),
        'response': random.randint(1, 100),
        'ip': "192.168.1." + str(random.randint(2, 254)),
        'os': random.choice(["Windows 11", "Ubuntu 22.04", "Debian", "macOS"]),
        'mac': f"{random.randint(0,255):02x}:{random.randint(0,255):02x}:{random.randint(0,255):02x}:{random.randint(0,255):02x}:{random.randint(0,255):02x}:{random.randint(0,255):02x}",
        'last_update': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        # Логирование действия
        log_action(
            user_email=session.get("user", {}).get("email", "unknown"),
            action='added',
            equipment_id=doc_ref.id,
            details=f"Добавлено устройство: {name}"
        )

        return redirect(url_for('index'))

    return render_template("add.html")



@app.route('/usb-devices')
def scan_usb_devices():
    pythoncom.CoInitialize()  # ИНИЦИАЛИЗАЦИЯ COM
    
    c = wmi.WMI()
    usb_devices = []

    for usb in c.Win32_USBHub():
        usb_devices.append({
            "Name": usb.Name,
            "DeviceID": usb.DeviceID,
            "Status": usb.Status,
            "PNPDeviceID": usb.PNPDeviceID
        })

    return render_template("usb_devices.html", devices=usb_devices)

from flask import jsonify

@app.route('/api/device_history/<device_id>')
def api_device_history(device_id):
    history_ref = db.collection('device_history').where('device_id', '==', device_id)
    history = history_ref.stream()

    history_data = {'dates': [], 'cpu': [], 'memory': []}
    for record in history:
        data = record.to_dict()
        timestamp = data.get('timestamp')
        if isinstance(timestamp, datetime):
            timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            timestamp = str(timestamp)

        history_data['dates'].append(timestamp)
        history_data['cpu'].append(data.get('cpu', 0))
        history_data['memory'].append(data.get('memory', 0))

    return jsonify(history_data)

from flask import Response
import csv
from datetime import datetime

@app.route("/device/<device_id>/export")
def export_device_history(device_id):
    history_ref = db.collection('device_history').where('device_id', '==', device_id)
    history = history_ref.stream()

    lines = []
    for record in history:
        data = record.to_dict()
        timestamp = data.get('timestamp')
        if isinstance(timestamp, datetime):
            timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            timestamp = str(timestamp)

        cpu = data.get('cpu', '—')
        memory = data.get('memory', '—')

        lines.append(f"[{timestamp}] CPU: {cpu}% | Memory: {memory}%")

    txt_content = "\n".join(lines)

    return Response(
        txt_content,
        mimetype='text/plain',
        headers={"Content-Disposition": f"attachment; filename=history_{device_id}.txt"}
    )


def register_current_computer():
    hostname = socket.gethostname()
    doc_id = hostname  # используем как ID

    doc_ref = db.collection('equipment').document(doc_id)
    if not doc_ref.get().exists:
        status = get_cached_status()
        info = get_device_info()

        doc_ref.set({
    'type': 'pc',  # ← это ключевое
    'name': hostname,
    'description': 'Локальный компьютер',
    'cpu': status['cpu'],
    'memory': status['memory'],
    'network': status['network'],
    'response': status['response'],
    'temperature': status['temperature'],
    'ip': info['ip'],
    'mac': info['mac'],
    'os': info['os'],
    'last_update': status['last_update']
})


        print(f"[✔] Локальный компьютер добавлен: {hostname}")
    else:
        print(f"[i] Компьютер уже есть: {hostname}")

def get_local_pc_info():
    import psutil
    import socket
    import platform

    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    os_name = platform.system() + " " + platform.release()
    cpu_percent = psutil.cpu_percent(interval=1)
    memory_percent = psutil.virtual_memory().percent

    return {
        'type': 'pc',
        'name': hostname,
        'description': 'Локальный компьютер',
        'ip': ip,
        'os': os_name,
        'cpu': cpu_percent,
        'memory': memory_percent,
        'temperature': '—',
        'network': None,
        'response': None,
        'last_update': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

import threading

def update_local_status_loop():
    while True:
        time.sleep(10)  # каждые 10 секунд
        try:
            hostname = socket.gethostname()
            doc_ref = db.collection('equipment').document(hostname)

            if doc_ref.get().exists:
                status = get_real_status()
                doc_ref.update(status)

                log_action(
                    user_email="system",
                    action="auto_update",
                    equipment_id=hostname,
                    details=f"Автообновление локального ПК: {status}"
                )
        except Exception as e:
            print("Ошибка автообновления локального ПК:", e)

if __name__ == '__main__':
    register_current_computer()

    # Запуск фонового обновления
    threading.Thread(target=update_local_status_loop, daemon=True).start()

    app.run(debug=False, use_reloader=False)


