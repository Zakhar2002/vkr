from flask import Flask, render_template, request, redirect, url_for, session
from database import get_db
from helpers import require_login, require_admin
import mysql.connector
import pymysql
import secrets  
import os
import openpyxl
from werkzeug.utils import secure_filename
from flask import send_file
from io import BytesIO


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app = Flask(__name__) 
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = 'os.urandom(24) \
'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/admin/courses')
@require_admin
def admin_courses():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM courses")
    courses = cursor.fetchall()
    return render_template('admin_courses.html', courses=courses)

@app.route('/admin/add_course', methods=['GET', 'POST'])
@require_admin
def add_course():
    if request.method == 'POST':
        title = request.form['title']
        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO courses (name) VALUES (%s)", (title,))
        db.commit()
        return redirect(url_for('admin_courses'))
    return render_template('admin_add_course.html')

@app.route('/admin/edit_course/<int:course_id>', methods=['GET', 'POST'])
@require_admin
def edit_course(course_id):
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        new_title = request.form['title']
        cursor.execute("UPDATE courses SET title = %s WHERE id = %s", (new_title, course_id))
        db.commit()
        return redirect(url_for('admin_courses'))

    cursor.execute("SELECT * FROM courses WHERE id = %s", (course_id,))
    course = cursor.fetchone()
    return render_template('admin_edit_course.html', course=course)

@app.route('/admin/delete_course/<int:course_id>', methods=['POST'])
@require_admin
def delete_course(course_id):
    db = get_db()
    cursor = db.cursor()

    # Удалим все темы, связанные с курсом (опционально)
    cursor.execute("DELETE FROM topics WHERE course_id = %s", (course_id,))
    cursor.execute("DELETE FROM courses WHERE id = %s", (course_id,))
    db.commit()
    return redirect(url_for('admin_courses'))

@app.route('/admin/courses/<int:course_id>/add_topic', methods=['GET', 'POST'])
@require_admin
def add_topic_to_course(course_id):
    db = get_db()
    cursor = db.cursor()

    # Проверка: курс существует?
    cursor.execute("SELECT * FROM courses WHERE id = %s", (course_id,))
    course = cursor.fetchone()
    if not course:
        return "Курс не найден", 404

    if request.method == 'POST':
        title = request.form['title']
        cursor.execute("INSERT INTO topics (title, course_id) VALUES (%s, %s)", (title, course_id))
        db.commit()
        return redirect(url_for('course_topics', course_id=course_id))

    return render_template('admin_add_topic_to_course.html', course=course)

@app.route('/admin/topics/<int:topic_id>/materials')
@require_admin
def topic_materials(topic_id):
    db = get_db()
    cursor = db.cursor()

    # Получаем тему
    cursor.execute("SELECT * FROM topics WHERE id = %s", (topic_id,))
    topic = cursor.fetchone()
    if not topic:
        return "Тема не найдена", 404

    # Получаем материалы
    cursor.execute("SELECT * FROM materials WHERE topic_id = %s", (topic_id,))
    materials = cursor.fetchall()

    return render_template('admin_topic_materials.html', topic=topic, materials=materials)

@app.route('/admin/courses/<int:course_id>/topics')
@require_admin
def course_topics(course_id):
    db = get_db()
    cursor = db.cursor()

    # Получаем курс
    cursor.execute("SELECT * FROM courses WHERE id = %s", (course_id,))
    course = cursor.fetchone()
    if not course:
        return "Курс не найден", 404

    # Получаем темы по курсу
    cursor.execute("SELECT * FROM topics WHERE course_id = %s", (course_id,))
    topics = cursor.fetchall()

    return render_template('admin_course_topics.html', course=course, topics=topics)

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('user_dashboard'))
    return render_template('login.html')

@app.route("/admin/progress/chart")
@require_admin
def progress_chart():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT t.title, COUNT(cp.user_id) AS viewed_count
        FROM topics t
        LEFT JOIN course_progress cp ON t.id = cp.topic_id AND cp.viewed_materials = TRUE
        GROUP BY t.id, t.title
    """)
    data = cursor.fetchall()

    # Отдельно списки названий курсов и количества
    labels = [row['title'] for row in data]
    values = [row['viewed_count'] for row in data]

    return render_template("admin_progress_chart.html", labels=labels, values=values)

@app.route('/admin/progress/export')    
@require_admin
def export_progress_excel():
    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)  # Чтобы результат был в виде словаря
    cursor.execute("""
        SELECT users.full_name, topics.title AS course, course_progress.viewed_materials,
               course_progress.passed_test, course_progress.test_score
        FROM users
        JOIN course_progress ON users.id = course_progress.user_id
        JOIN topics ON topics.id = course_progress.topic_id
        ORDER BY users.email, topics.title
    """)
    data = cursor.fetchall()

    # Создание Excel-файла
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Прогресс пользователей"

    # Заголовки
    ws.append(["ФИО", "Курс", "Материалы просмотрены", "Тест пройден", "Результат (%)"])

    # Данные
    for row in data:
        ws.append([
           row['full_name'],
            row['course'],
            "Да" if row['viewed_materials'] else "Нет",
            "Да" if row['passed_test'] else "Нет",
            row['test_score'] if row['test_score'] is not None else ""
        ])

    # Подготовка файла для скачивания
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="progress_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/admin/progress")
@require_admin
def admin_progress():
    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute("""
        SELECT
            users.full_name,
            topics.title AS course,
            course_progress.viewed_materials,
            course_progress.passed_test,
            course_progress.test_score
        FROM users
        JOIN course_progress ON users.id = course_progress.user_id
        JOIN topics ON topics.id = course_progress.topic_id
        ORDER BY users.email, topics.title
    """)
    progress_data = cursor.fetchall()
    return render_template("admin_progress.html", progress_data=progress_data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()
        cursor.close()

        if user:
            session['user_id'] = user['id']  # или user['id'], если cursor возвращает dict
            session['role'] = user['role']     # или user['role']
            return redirect(url_for('user_dashboard'))
        else:
            return 'Неверный логин или пароль'

    return render_template('login.html')


@app.route('/admin/invite', methods=['GET', 'POST'])
def invite_user():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    invite_link = None

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form['email']
        token = secrets.token_hex(16)

        db = get_db()
        cursor = db.cursor()
        print("FULL NAME:", full_name)
        cursor.execute("INSERT INTO users (email, role, is_confirmed, invite_token, full_name) VALUES (%s, %s, %s, %s, %s)",
                       (email, 'user', False, token, full_name))
        db.commit()
        cursor.close()

        invite_link = url_for('complete_invite', token=token, _external=True)

    return render_template('admin_invite_user.html', invite_link=invite_link)

@app.route('/invite/<token>', methods=['GET', 'POST'])
def complete_invite(token):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE invite_token = %s AND is_confirmed = FALSE", (token,))
    user = cursor.fetchone()

    if not user:
        return "Ссылка недействительна или пользователь уже активирован."

    if request.method == 'POST':
        password = request.form['password']
        cursor.execute("UPDATE users SET password = %s, is_confirmed = TRUE, invite_token = NULL WHERE id = %s",
                       (password, user['id']))
        db = get_db()
        db.commit()
        cursor.close()
        return redirect(url_for('login'))

    cursor.close()
    return render_template('complete_invite.html', email=user['email'])

@app.route('/admin/materials')
def admin_materials():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM materials")
    materials = cursor.fetchall()
    cursor.close()

    return render_template('admin_materials.html', materials=materials)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # если админ — отправим в админку
    if session.get('role') == 'admin':
        return redirect(url_for('admin_panel'))

    return render_template('user_dashboard.html')

@app.route('/material/<int:material_id>')
def view_material(material_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM materials WHERE id = %s", (material_id,))
    material = cursor.fetchone()

    if not material:
        return "Материал не найден", 404

    cursor.execute("SELECT title FROM topics WHERE id = %s", (material['topic_id'],))
    topic_row = cursor.fetchone()
    topic_title = topic_row['title'] if topic_row else 'Без названия'

    return render_template("material_view.html", material=material, topic=topic_title)


@app.route('/admin')
def admin_panel():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin.html')

@app.route('/admin/topics')
def admin_topics():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM topics")
    topics = cursor.fetchall()
    cursor.close()

    return render_template('admin_topics.html', topics=topics)

@app.route('/admin/add_topic', methods=['GET', 'POST'])
def add_topic():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO topics (title) VALUES (%s)", (title,))
        db = get_db()
        db.commit()
        cursor.close()
        return redirect(url_for('admin_topics'))

    return render_template('admin_add_topic.html')

@app.route('/admin/add_material/<int:topic_id>', methods=['GET', 'POST'])
def add_material(topic_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        content = request.form['content']
        body = request.form.get('body')
        file = request.files.get('file')
        file_path = None

        if file and file.filename:
            filename = secure_filename(file.filename)
            file_path = f"uploads/{filename}"
            full_path = os.path.join(app.static_folder, 'uploads', filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            file.save(full_path)

        db = get_db()
        cursor = db.cursor()
        print("Проверка текста:", body)

        cursor.execute(
            "INSERT INTO materials (topic_id, content, body, file_path) VALUES (%s, %s, %s, %s)",
            (topic_id, content, body, file_path)
        )
        print("Контроль:", topic_id, content, body, file_path)
        db.commit()
        cursor.close()

        return redirect(url_for('admin_topics'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM topics WHERE id = %s", (topic_id,))
    topic = cursor.fetchone()
    cursor.close()

    return render_template('admin_add_material.html', topic=topic)

@app.route('/admin/invited_users')
def invited_users():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, email, full_name, is_confirmed, invite_token FROM users WHERE role = 'user'")
    users = cursor.fetchall()
    cursor.close()

    return render_template('admin_invited_users.html', users=users)

@app.route('/admin/staff')
def admin_staff():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_staff.html')

@app.route('/admin/delete_topic/<int:topic_id>', methods=['POST'])
def delete_topic(topic_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    # Сначала удалим связанные материалы и вопросы, если нужно
    cursor.execute("DELETE FROM materials WHERE topic_id = %s", (topic_id,))
    cursor.execute("DELETE FROM questions WHERE topic_id = %s", (topic_id,))
    cursor.execute("DELETE FROM topics WHERE id = %s", (topic_id,))
    db = get_db()
    db.commit()
    cursor.close()

    return redirect(url_for('admin_topics'))

@app.route('/admin/edit_topic/<int:topic_id>', methods=['GET', 'POST'])
def edit_topic(topic_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    if request.method == 'POST':
        new_title = request.form['title']
        cursor.execute("UPDATE topics SET title = %s WHERE id = %s", (new_title, topic_id))
        db = get_db()
        db.commit()
        cursor.close()
        return redirect(url_for('admin_topics'))

    cursor.execute("SELECT * FROM topics WHERE id = %s", (topic_id,))
    topic = cursor.fetchone()
    cursor.close()

    if not topic:
        return "Тема не найдена"
    return render_template('admin_edit_topic.html', topic=topic)

@app.route('/admin/delete_material/<int:material_id>', methods=['POST'])
def delete_material(material_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM materials WHERE id = %s", (material_id,))
    db = get_db()
    db.commit()
    cursor.close()

    return redirect(url_for('admin_materials'))

@app.route('/admin/delete_invited_user/<int:user_id>', methods=['POST'])
def delete_invited_user(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s AND is_confirmed = FALSE", (user_id,))
    db = get_db()
    db.commit()
    cursor.close()

    return redirect(url_for('invited_users'))

@app.route('/admin/add_question/<int:topic_id>', methods=['GET', 'POST'])
def add_question(topic_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM topics WHERE id = %s", (topic_id,))
    topic = cursor.fetchone()

    if not topic:
        return "Тема не найдена", 404

    if request.method == 'POST':
        question_text = request.form['question']
        answers = [
            request.form['answer1'],
            request.form['answer2'],
            request.form['answer3'],
            request.form['answer4']
        ]
        correct = int(request.form['correct'])

        # Сохраняем вопрос
        cursor.execute("INSERT INTO questions (topic_id, question_text) VALUES (%s, %s)", (topic_id, question_text))
        question_id = cursor.lastrowid

        # Сохраняем варианты ответа
        for i in range(4):
            is_correct = 1 if (i + 1) == correct else 0
            cursor.execute(
                "INSERT INTO answers (question_id, answer_text, is_correct) VALUES (%s, %s, %s)",
               (question_id, answers[i], is_correct)
            )

        db.commit()
        cursor.close()
        return redirect(url_for('course_topics', course_id=topic['course_id']))

    return render_template('admin_add_question.html', topic=topic)

@app.route('/admin/topics/<int:topic_id>/questions')
@require_admin
def view_questions(topic_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id, title, course_id FROM topics WHERE id = %s", (topic_id,))
    topic_row = cursor.fetchone()
    if not topic_row:
        return "Тема не найдена", 404

    topic = {
        "id": topic_row["id"],
        "title": topic_row["title"],
        "course_id": topic_row["course_id"]
    }

    cursor.execute("SELECT id, question_text FROM questions WHERE topic_id = %s", (topic_id,))
    questions = []
    for row in cursor.fetchall():
        q_id = row["id"]
        q_text = row["question_text"]

        cursor.execute("SELECT answer_text, is_correct FROM answers WHERE question_id = %s", (q_id,))
        answers = [{"text": a["answer_text"], "is_correct": a["is_correct"]} for a in cursor.fetchall()]

        questions.append({"id": q_id, "text": q_text, "answers": answers})

    return render_template("admin_view_questions.html", topic=topic, questions=questions)

@app.route('/admin/delete_question/<int:question_id>', methods=['POST'])
@require_admin
def delete_question(question_id):
    db = get_db()
    cursor = db.cursor()

    # Получаем topic_id для возврата обратно
    cursor.execute("SELECT topic_id FROM questions WHERE id = %s", (question_id,))
    row = cursor.fetchone()
    if not row:
        return "Вопрос не найден", 404

    topic_id = row["topic_id"]

    # Удаляем ответы, потом вопрос
    cursor.execute("DELETE FROM answers WHERE question_id = %s", (question_id,))
    cursor.execute("DELETE FROM questions WHERE id = %s", (question_id,))
    db.commit()

    return redirect(url_for('view_questions', topic_id=topic_id))

    
@app.route('/dashboard')
def user_dashboard():  # ← новое имя функции
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('user_dashboard.html')

@app.route('/user/courses')
def user_courses():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM courses")
    courses = cursor.fetchall()

    for course in courses:
        cursor.execute("SELECT * FROM topics WHERE course_id = %s", (course['id'],))
        course['topics'] = cursor.fetchall()

    return render_template('user_courses.html', courses=courses)

@app.route('/user/test/<int:topic_id>', methods=['GET', 'POST'])
def user_test(topic_id):
    db = get_db()
    cursor = db.cursor()

    # Получаем вопросы по теме
    cursor.execute("SELECT id, question_text FROM questions WHERE topic_id = %s", (topic_id,))
    questions = cursor.fetchall()

    question_data = []
    for q in questions:
        cursor.execute("SELECT id, answer_text FROM answers WHERE question_id = %s", (q["id"],))
        raw_answers = cursor.fetchall()
        answers = [{"id": a["id"], "text": a["answer_text"]} for a in raw_answers]
        question_data.append({
            "id": q["id"],
            "question": q["question_text"],
            "answers": answers
        })

    # Обработка отправки теста
    if request.method == 'POST':
        score = 0
        total = 0

        for q in question_data:
            selected = request.form.get(f"question_{q['id']}")
            if not selected:
                continue

            cursor.execute("SELECT is_correct FROM answers WHERE id = %s", (selected,))
            result = cursor.fetchone()
            if result and result["is_correct"] == 1:
                score += 1
            total += 1

        percent = round(score / total * 100) if total > 0 else 0
        user_id = session.get("user_id")

    # Проверяем, есть ли уже запись по этому пользователю и теме
        cursor.execute("SELECT * FROM course_progress WHERE user_id = %s AND topic_id = %s", (user_id, topic_id))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("""
                UPDATE course_progress 
                SET passed_test = TRUE, test_score = %s 
                WHERE user_id = %s AND topic_id = %s
                """, (percent, user_id, topic_id))
        else:
            cursor.execute("""
                INSERT INTO course_progress (user_id, topic_id, passed_test, viewed_materials, test_score)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, topic_id, True, False, percent))


        db.commit()

        return render_template("user_result.html", score=percent)

    return render_template("user_test.html", questions=question_data)




@app.route('/user/topic/<int:topic_id>/materials')
def user_view_materials(topic_id):
    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)  # обязательно словарь

    cursor.execute("SELECT id, title, course_id FROM topics WHERE id = %s", (topic_id,))
    topic = cursor.fetchone()

    if not topic:
        return "Тема не найдена", 404

    cursor.execute("SELECT content, body, file_path FROM materials WHERE topic_id = %s", (topic_id,))
    materials = cursor.fetchall()

    return render_template("user_materials.html", materials=materials, topic=topic)

@app.route("/courses/<int:topic_id>/materials")
@require_login
def view_course_materials(topic_id):
    db = get_db()
    cursor = db.cursor()

    # Получаем тему
    cursor.execute("SELECT title FROM topics WHERE id = %s", (topic_id,))
    topic = cursor.fetchone()
    if not topic:
        return "Курс не найден", 404

    # 📌 Обновляем/добавляем прогресс
    user_id = session.get("user_id")
    cursor.execute("SELECT * FROM course_progress WHERE user_id = %s AND topic_id = %s", (user_id, topic_id))
    progress = cursor.fetchone()

    if progress:
        cursor.execute("UPDATE course_progress SET viewed_materials = TRUE WHERE user_id = %s AND topic_id = %s",
                       (user_id, topic_id))
    else:
        cursor.execute("INSERT INTO course_progress (user_id, topic_id, passed_test) VALUES (%s, %s, %s)", (user_id, topic_id, True)),
    db.commit()

    # Загружаем материалы
    cursor.execute("SELECT id, title, file_path FROM materials WHERE topic_id = %s", (topic_id,))
    materials = cursor.fetchall()

    return render_template("material_view.html", topic=topic, materials=materials)

    # Получаем тему для заголовка
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM topics WHERE id = %s", (topic_id,))
    topic = cursor.fetchone()
    cursor.close()

    return render_template('admin_add_question.html', topic=topic)

@app.route('/admin/update_full_name', methods=['POST'])
def update_full_name():
    user_id = request.form.get('user_id')
    full_name = request.form.get('full_name')

    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE users SET full_name = %s WHERE id = %s", (full_name, user_id))
    db.commit()
    cursor.close()

    return redirect(url_for('invited_users'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
