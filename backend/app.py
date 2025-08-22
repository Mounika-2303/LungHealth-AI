import os
import re
import requests
import librosa as lb
import librosa.display
import matplotlib
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import smtplib
from email.message import EmailMessage
import rdc_model
import json
from datetime import datetime
from flask import abort
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask import request

from flask import flash, abort, request



# ========== Utility Functions ==========

def load_users():
    if not os.path.exists("users.json"):
        return {}
    with open("users.json", "r") as f:
        return json.load(f)

def save_users(users):
    with open("users.json", "w") as f:
        json.dump(users, f, indent=4)

def log_event(event):
    with open("audit.log", "a") as f:
        f.write(f"{datetime.now()}: {event}\n")

# ========== Setup ==========

matplotlib.use('Agg')
load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')

root_folder = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(root_folder, "static", "uploads")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = SECRET_KEY

# ========== Routes ==========

@app.route("/")
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    # ✅ Check if logged-in user is admin
    if session.get('role') == 'admin':
        return render_template('admin_dashboard.html')
    else:
        return render_template('dashboard.html')

@app.route("/predict")
def predict():
    if 'user' in session:
        for f in os.listdir(UPLOAD_FOLDER):
            os.remove(os.path.join(UPLOAD_FOLDER, f))
        return render_template("index.html", ospf=1)
    return redirect(url_for('login'))

@app.route("/view_all_users")
def view_all_users():
    if session.get("role") != "admin":
        return redirect(url_for("dashboard"))

    users = load_users()
    return render_template("view_users.html", users=users)
@app.route("/admin_user_predictions")
def admin_user_predictions():
    if session.get("role") != "admin":
        return redirect(url_for("dashboard"))

    predictions = []
    history_dir = "user_history"

    if os.path.exists(history_dir):
        for file in os.listdir(history_dir):
            if file.endswith("_history.json"):
                with open(os.path.join(history_dir, file), "r") as f:
                    user_predictions = json.load(f)
                    predictions.append({
                        "user": file.replace("_history.json", ""),
                        "entries": user_predictions
                    })

    return render_template("admin_user_predictions.html", predictions=predictions)


@app.route("/", methods=['POST'])
def patient():
    if 'user' not in session:
        return redirect(url_for('login'))

    name = request.form["name"]
    lungSounds = request.files["lungSounds"]
    filename = secure_filename(lungSounds.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    lungSounds.save(filepath)

    relative_path = os.path.join("static", "uploads", filename)
    res_list = rdc_model.classificationResults(filepath)

    # Handle case: No disease or error
    if isinstance(res_list[0], str) and ("Error" in res_list[0] or "No respiratory disorder detected" in res_list[0]):
        return render_template("index.html", ospf=0, n=name, lungSounds=relative_path, res=res_list)

    try:
        audio1, sample_rate1 = lb.load(filepath, mono=True)
        librosa.display.waveshow(audio1, sr=sample_rate1, max_points=50000, x_axis='time')
        plt.savefig("./static/uploads/outSoundWave.png")

        mfccs = lb.feature.mfcc(y=audio1, sr=sample_rate1, n_mfcc=40)
        fig, ax = plt.subplots()
        img = librosa.display.specshow(mfccs, x_axis='time', ax=ax)
        fig.colorbar(img, ax=ax)
        plt.savefig("./static/uploads/outSoundMFCC.png")

        res_list.append(os.path.abspath("./static/uploads/outSoundWave.png"))
    except Exception as e:
        print(f"Error generating graphs: {e}")
        res_list.append("Error generating graphs")

    # ✅ Save prediction to user's history
    history_path = f"user_history/{session['user']}_history.json"
    history = []
    if os.path.exists(history_path):
        with open(history_path, "r") as f:
            history = json.load(f)

    entry = {
        "name": name,
        "result": res_list[0],
        "timestamp": str(datetime.now())
    }
    history.append(entry)

    os.makedirs("user_history", exist_ok=True)  # make sure folder exists
    with open(history_path, "w") as f:
        json.dump(history, f, indent=4)

    # ✅ Render result page
    return render_template("index.html", ospf=0, n=name, lungSounds=relative_path, res=res_list)
@app.route("/precautions/<disease>")
def precautions(disease):
    if 'user' not in session:
        return redirect(url_for('login'))

    videos_dict = {
    "Asthma": [
        {"title": "Asthma Management", "videoId": "DwLMEz3QoME"},
        {"title": "Understanding Asthma Triggers", "videoId": "4KX_kCskg3A"},
        {"title": "Asthma Inhaler Techniques", "videoId": "52Xu6u-FBqY"}
    ],
    "COPD": [
        {"title": "COPD Breathing Exercise", "videoId": "wymTsiFT8Lc"},
        {"title": "Living Well with COPD", "videoId": "Y29bTzKK_P8"},
        {"title": "Pulmonary Rehab for COPD", "videoId": "2zZSnTqvce0"}
    ],
    "Pneumonia": [
        {"title": "Pneumonia Recovery Tips", "videoId": "EV9nmvxRg-M"},
        {"title": "What to Eat During Pneumonia", "videoId": "LYRT5TzmiDk"},
        {"title": "Exercises After Pneumonia", "videoId": "IAQp2Zuqevc"}
    ],
    "Bronchiolitis": [
        {"title": "Bronchiolitis Care Tips", "videoId": "JaYKNB0_HxY"},
        {"title": "Bronchiolitis in Children", "videoId": "S_Ip23jwTsA"},
        {"title": "Managing Mild Bronchiolitis", "videoId": "9uquk0a0vck"}
    ],
    "Bronchiectasis": [
        {"title": "What is Bronchiectasis?", "videoId": "lIPkmpz81Co"},
        {"title": "Clearing Lungs in Bronchiectasis", "videoId": "MjsSIu8q3RQ"},
        {"title": "Bronchiectasis Lifestyle Guide", "videoId": "J50WxMcxMfg"}
    ],
    "URTI": [
        {"title": "Relieve URTI Symptoms", "videoId": "BIqGQhcsaIQ"},
        {"title": "URTI Natural Remedies", "videoId": "Fn-iNHMQddM"},
        {"title": "Preventing Upper Respiratory Infections", "videoId": "0To0jO8b7wQ"}
    ],
    "LRTI": [
        {"title": "LRTI Info", "videoId": "YhwZLg2sD9I"},
        {"title": "Lower Respiratory Infection Symptoms", "videoId": "eoGS0Ud1Iyg"},
        {"title": "Treatment Options for LRTI", "videoId": "REPLACE_ID_2"}
    ],
    "Healthy": [
        {"title": "Healthy Breathing", "videoId": "WlinbaOptz8"},
        {"title": "Lung Strengthening Exercises", "videoId": "CKuDzOPcX9k"},
        {"title": "Daily Tips for Healthy Lungs", "videoId": "v=K5TnfbvRvcs"}
    ]
}


    precautions_dict = {
    "Asthma": {
        "precautions": "Avoid allergens, use inhalers, follow your asthma action plan.",
        "routine": [
            {"activity": "Avoid triggers", "details": "Avoid triggers like smoke and dust."},
            {"activity": "Monitor condition", "details": "Use a peak flow meter to monitor your condition."},
            {"activity": "Take medications", "details": "Take prescribed medications regularly."}
        ],
        "exercises": [
            {"name": "Deep Breathing", "image": "deep_breathing.jpg"},
            {"name": "Diaphragmatic Breathing", "image": "diaphragmatic_breathing.jpg"},
            {"name": "Pursed-Lip Breathing", "image": "pursed_lip_breathing.jpg"}
        ]
    },
    "COPD": {
        "precautions": "Avoid smoking, regular exercise, pulmonary rehabilitation.",
        "routine": [
            {"activity": "Avoid Lung Irritants", "details": "Avoid exposure to lung irritants."},
            {"activity": "Healthy Diet", "details": "Follow a healthy diet."},
            {"activity": "Regular Exercises", "details": "Maintain an active lifestyle with regular exercises."}
        ],
        "exercises": [
            {"name": "Pursed-Lip Breathing", "image": "pursed_lip_breathing.jpg"},
            {"name": "Diaphragmatic Breathing", "image": "diaphragmatic_breathing.jpg"},
            {"name": "Controlled Coughing", "image": "controlled_coughing.jpg"}
        ]
    },
    "Pneumonia": {
        "precautions": "Stay hydrated, rest, complete the prescribed antibiotics course.",
        "routine": [
            {"activity": "Take Full Rest", "details": "Get enough sleep and avoid exertion."},
            {"activity": "Follow Antibiotics", "details": "Complete the full course of antibiotics."},
            {"activity": "Avoid Cold Environments", "details": "Stay warm and indoors when necessary."}
        ],
        "exercises": [
            {"name": "Incentive Spirometry", "image": "spirometry.jpg"},
            {"name": "Paced Breathing", "image": "paced_breathing.jpg"},
            {"name": "Postural Drainage", "image": "postural_drainage.jpg"}
        ]
    },
    "Bronchiolitis": {
        "precautions": "Ensure rest, hydration, and medical follow-up for infants and children.",
        "routine": [
            {"activity": "Keep Child Upright", "details": "Hold baby upright to ease breathing."},
            {"activity": "Hydration", "details": "Offer frequent fluids."},
            {"activity": "Humid Air", "details": "Use a humidifier to soothe airways."}
        ],
        "exercises": [
            {"name": "Gentle Tummy Time", "image": "tummy_time.jpg"},
            {"name": "Nasal Suction", "image": "nasal_suction.jpg"},
            {"name": "Steam Inhalation", "image": "steam_inhalation.jpg"}
        ]
    },
    "Bronchiectasis": {
        "precautions": "Clear airways daily, avoid infections, and follow medical therapy.",
        "routine": [
            {"activity": "Daily Chest Physiotherapy", "details": "Loosen mucus from lungs."},
            {"activity": "Avoid Air Pollutants", "details": "Stay away from smoke and allergens."},
            {"activity": "Vaccinations", "details": "Stay updated on flu and pneumonia vaccines."}
        ],
        "exercises": [
            {"name": "Active Cycle of Breathing", "image": "acbt.jpg"},
            {"name": "Postural Drainage", "image": "postural_drainage.jpg"},
            {"name": "Huff Coughing", "image": "huff_coughing.jpg"}
        ]
    },
    "URTI": {
        "precautions": "Get rest, stay hydrated, and avoid spreading infection.",
        "routine": [
            {"activity": "Frequent Handwashing", "details": "Wash hands to prevent spread."},
            {"activity": "Stay Home", "details": "Avoid going out when symptomatic."},
            {"activity": "Use Tissues", "details": "Cover coughs and sneezes."}
        ],
        "exercises": [
            {"name": "Steam Inhalation", "image": "steam_inhalation.jpg"},
            {"name": "Throat Gargling", "image": "gargle.jpg"},
            {"name": "Nasal Irrigation", "image": "nasal_irrigation.jpg"}
        ]
    },
    "LRTI": {
        "precautions": "Treat early, manage symptoms, and consult a doctor.",
        "routine": [
            {"activity": "Monitor Breathing", "details": "Watch for shortness of breath."},
            {"activity": "Complete Medication", "details": "Finish prescribed antibiotics or antivirals."},
            {"activity": "Avoid Smoke", "details": "No smoking or exposure to fumes."}
        ],
        "exercises": [
            {"name": "Pursed-Lip Breathing", "image": "pursed_lip_breathing.jpg"},
            {"name": "Controlled Cough", "image": "controlled_coughing.jpg"},
            {"name": "Seated Forward Bend", "image": "forward_bend.jpg"}
        ]
    },
    "Healthy": {
        "precautions": "Maintain a healthy lifestyle, eat balanced food, exercise daily.",
        "routine": [
            {"activity": "Balanced Diet", "details": "Eat fruits, vegetables, and stay hydrated."},
            {"activity": "Daily Exercise", "details": "Walk, stretch, or do yoga regularly."},
            {"activity": "Avoid Smoking", "details": "Stay away from tobacco and pollutants."}
        ],
        "exercises": [
            {"name": "Breathing for Relaxation", "image": "relaxation_breathing.jpg"},
            {"name": "Stretching", "image": "stretching.jpg"},
            {"name": "Walking", "image": "walking.jpg"}
        ]
    }
}


    videos = videos_dict.get(disease, [])
    return render_template("precautions.html", disease=disease, videos=videos, precautions_dict=precautions_dict)

@app.context_processor
def utility_processor():
    def is_active(*endpoints):
        """
        Usage in templates: class="{{ is_active('index', 'patient') }}"
        Returns 'active' if the current request.endpoint is in the list.
        """
        return 'active' if request.endpoint in endpoints else ''
    return dict(is_active=is_active)

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "user": session.get("user", "guest"),
            "name": name,
            "email": email,
            "subject": subject,
            "message": message
        }

        messages = load_messages()
        messages.append(entry)
        save_messages(messages)

        # Optional: log it in audit.log if you use that
        try:
            log_event(f"Contact form: {name} <{email}> | {subject}")
        except Exception:
            pass

        # Optional: also email to admin
        # send_email_notification(EMAIL_ADDRESS, f"Contact: {subject}", f"From: {name} <{email}>\n\n{message}")

        flash("Thanks! Your message has been received. We'll get back to you soon.")
        return redirect(url_for("contact"))

    return render_template("contact.html", active_page="contact")


@app.route("/admin/messages")
def admin_messages():
    admin_only()
    messages = load_messages()
    # Show newest first
    messages = sorted(messages, key=lambda m: m.get("timestamp",""), reverse=True)
    return render_template("admin_messages.html", messages=messages, active_page="admin")


@app.route("/admin")
def admin_panel():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    users = load_users()
    logs = []
    if os.path.exists("audit.log"):
        with open("audit.log", "r") as f:
            logs = f.readlines()

    return render_template("admin_panel.html", users=users, logs=logs)

@app.route("/history")
def history():
    if 'user' not in session:
        return redirect(url_for('login'))

    email = session['user']
    history_path = f"user_history/{email}_history.json"
    history = []
    if os.path.exists(history_path):
        with open(history_path, "r") as f:
            history = json.load(f)

    return render_template("history.html", history=history)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        users = load_users()
        if email in users:
            return render_template('register.html', error="Email already exists.")

        users[email] = {"password": password, "role": "user"}
        save_users(users)
        return redirect(url_for('login'))

    return render_template("register.html")

@app.route("/login", methods=['GET', 'POST'])
def login():
    users = load_users()

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = users.get(email)
        if user and user['password'] == password:
            user['last_login'] = str(datetime.now())
            save_users(users)

            session['user'] = email
            session['role'] = user.get('role', 'user')

            log_event(f"{email} logged in.")
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid email or password")

    return render_template("login.html")

@app.route("/logout")
def logout():
    if 'user' in session:
        log_event(f"{session['user']} logged out.")
    session.pop('user', None)
    session.pop('role', None)
    return redirect(url_for('login'))

@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        current = request.form['current']
        new = request.form['new']
        users = load_users()
        user = users.get(session['user'])
        if user and user['password'] == current:
            user['password'] = new
            save_users(users)
            flash("Password changed successfully.")
        else:
            flash("Incorrect current password.")
    return render_template("change_password.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/send_email_form")
def email_form():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template("send_email_form.html")

@app.route("/send_email", methods=['POST'])
def send_email():
    if 'user' not in session:
        return redirect(url_for('login'))

    name = request.form.get("name")
    email = request.form.get("email")
    disease = request.form.get("disease")

    try:
        send_email_notification(email, name, disease)
        return f'''<script>alert("Email sent successfully to {name}!"); window.location.href = "/";</script>'''
    except Exception as e:
        return f'''<script>alert("Error sending email: {e}"); window.location.href = "/";</script>'''

def send_email_notification(to_email, patient_name, disease):
    msg = EmailMessage()
    msg['Subject'] = 'Disease Report'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg.set_content(f"Hello {patient_name},\n\nIn the report, the detected disease is {disease}.\n\nTake care!")

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

# Helper: Only allow admin
def admin_only():
    if session.get('role') != 'admin':
        abort(403)

@app.route("/admin/view_users")
def view_users():
    admin_only()
    users = load_users()
    return render_template("admin_users.html", users=users)

@app.route("/admin/view_logs")
def view_logs():
    admin_only()
    logs = []
    if os.path.exists("audit.log"):
        with open("audit.log", "r") as f:
            logs = f.readlines()
    return render_template("admin_logs.html", logs=logs)

# Where to store admin‑readable data
DATA_DIR = os.path.join(root_folder, "data")
os.makedirs(DATA_DIR, exist_ok=True)
MESSAGES_FILE = os.path.join(DATA_DIR, "contact_messages.json")

def admin_only():
    if session.get('role') != 'admin':
        abort(403)

def load_messages():
    if not os.path.exists(MESSAGES_FILE):
        return []
    with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_messages(messages):
    with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)


@app.route("/admin/user_predictions")
def user_predictions():
    admin_only()
    predictions = {}

    if os.path.exists("user_history"):
        for filename in os.listdir("user_history"):
            if filename.endswith("_history.json"):
                user = filename.replace("_history.json", "")
                with open(os.path.join("user_history", filename), "r") as f:
                    predictions[user] = json.load(f)
    return render_template("admin_predictions.html", predictions=predictions)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
