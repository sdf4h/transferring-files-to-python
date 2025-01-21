from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
import os
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
import uuid

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Замените на свой секретный ключ

# Конфигурация базы данных
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)

# Конфигурация загрузки файлов
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Разрешенные расширения файлов
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}

# Настройка Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Если неавторизованный пользователь пытается получить доступ к защищенной странице, его перенаправит на эту функцию

# Модель пользователя
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)

# Модель файлов пользователя
class UserFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(150), nullable=False)  # Уникальное имя файла на сервере
    original_filename = db.Column(db.String(150), nullable=False)  # Оригинальное имя файла
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Владелец файла

db.create_all()

# Загрузка пользователя по ID для Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Функция проверки разрешенных файлов
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Главная страница
@app.route('/')
def index():
    return render_template('index.html')

# Страница регистрации
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует')
            return redirect(url_for('signup'))
        new_user = User(username=username)
        db.session.add(new_user)
        db.session.commit()
        flash('Регистрация прошла успешно')
        return redirect(url_for('login'))
    return render_template('signup.html')

# Страница входа
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        user = User.query.filter_by(username=username).first()
        if user:
            login_user(user)
            flash('Вы вошли в систему')
            return redirect(url_for('upload_file'))
        else:
            flash('Неверное имя пользователя')
            return redirect(url_for('login'))
    return render_template('login.html')

# Выход из системы
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы')
    return redirect(url_for('index'))

# Загрузка файла
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    if request.method == 'POST':
        # Проверяем, присутствует ли файл в запросе
      
        if 'file' not in request.files:
            flash('Нет файла для загрузки')
            return redirect(request.url)
        file = request.files['file']
        # Если пользователь не выбрал файл
        if file.filename == '':
            flash('Файл не выбран')
            return redirect(request.url)
        # Проверяем, разрешен ли файл
        if file and allowed_file(file.filename):
            original_filename = file.filename
            filename = secure_filename(file.filename)
            # Генерируем уникальное имя файла
            unique_filename = str(uuid.uuid4()) + "_" + filename
            # Сохраняем файл в указанную папку
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
            # Сохраняем информацию о файле в базу данных
            user_file = UserFile(filename=unique_filename, original_filename=original_filename, owner_id=current_user.id)
            db.session.add(user_file)
            db.session.commit()
            flash('Файл успешно загружен')
            return redirect(url_for('uploaded_files'))
        else:
            flash('Недопустимый тип файла. Разрешены: ' + ', '.join(ALLOWED_EXTENSIONS))
            return redirect(request.url)
    return render_template('upload.html')

# Список загруженных файлов текущего пользователя
@app.route('/files')
@login_required
def uploaded_files():
    user_files = UserFile.query.filter_by(owner_id=current_user.id).all()
    return render_template('files.html', files=user_files)

# Скачивание файла
@app.route('/download/<int:file_id>')
@login_required
def download_file(file_id):
    user_file = UserFile.query.get_or_404(file_id)
    # Проверяем, что файл принадлежит текущему пользователю
    if user_file.owner_id != current_user.id:
        flash('У вас нет доступа к этому файлу')
        return redirect(url_for('uploaded_files'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], user_file.filename, as_attachment=True, attachment_filename=user_file.original_filename)

if __name__ == '__main__':
    # Создаем папку для загрузок, если ее нет
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)
