import os, logging, uuid
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename
import pandas as pd

from user_store import (bcrypt, find_by_username, find_by_id, create_user,
                        add_upload_record, get_user_uploads, get_all_uploads, get_all_users)
from forms import RegisterForm, LoginForm, UploadForm
from utils import (allowed_file, clean_dataframe, summarize_dataframe,
                   generate_plotly_chart, generate_matplotlib_chart,
                   get_data_preview, calculate_statistics)

app = Flask(__name__)
app.config["SECRET_KEY"]         = os.getenv("SECRET_KEY", "dev-secret")
app.config["UPLOAD_FOLDER"]      = os.getenv("UPLOAD_FOLDER", "uploads")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs("data", exist_ok=True)

bcrypt.init_app(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@login_manager.user_loader
def load_user(uid): return find_by_id(uid)


# ── Index ──────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("dashboard") if current_user.is_authenticated else url_for("login"))


# ── Auth ───────────────────────────────────────────────────────

@app.route("/register", methods=["GET","POST"])
def register():
    if current_user.is_authenticated: return redirect(url_for("dashboard"))
    form = RegisterForm()
    if form.validate_on_submit():
        user = create_user(form.username.data, form.password.data)
        if not user:
            flash("Username already taken.", "danger")
        else:
            logger.info("Registered: %s", form.username.data)
            flash("Account created — please log in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET","POST"])
def login():
    if current_user.is_authenticated: return redirect(url_for("dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = find_by_username(form.username.data)
        if user and user.check_password(form.password.data):
            login_user(user)
            logger.info("Login: %s", user.username)
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(request.args.get("next") or url_for("dashboard"))
        logger.warning("Bad login: %s", form.username.data)
        flash("Invalid username or password.", "danger")
    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# ── Admin ──────────────────────────────────────────────────────

@app.route("/admin")
@login_required
def admin():
    if current_user.role != "admin": abort(403)
    return render_template("admin.html",
                           users=get_all_users(), uploads=get_all_uploads())


# ── Dashboard ──────────────────────────────────────────────────

@app.route("/dashboard", methods=["GET","POST"])
@login_required
def dashboard():
    form = UploadForm()
    ctx  = dict(chart_html=None, chart_img=None, summary=None,
                preview_html=None, stats=None, error=None,
                uploads=get_user_uploads(current_user.id))

    if form.validate_on_submit():
        f            = form.csv_file.data
        original     = secure_filename(f.filename)

        if not allowed_file(original):
            flash("Only .csv files accepted.", "danger")
            return redirect(url_for("dashboard"))

        uid_name = f"{uuid.uuid4().hex}_{original}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], uid_name)
        f.save(filepath)
        add_upload_record(current_user.id, uid_name, original)
        logger.info("Upload: %s by %s", original, current_user.username)

        try:
            df              = pd.read_csv(filepath)
            df              = clean_dataframe(df)
            ctx["summary"]  = summarize_dataframe(df)
            ctx["stats"]    = calculate_statistics(df)
            ctx["preview_html"] = get_data_preview(df, rows=8)

            x = form.x_col.data or None
            y = form.y_col.data or None
            ct = form.chart_type.data

            ctx["chart_html"] = generate_plotly_chart(df, ct, x, y)
            ctx["chart_img"]  = generate_matplotlib_chart(df, ct, x, y)
            ctx["uploads"]    = get_user_uploads(current_user.id)
            flash(f"✅ '{original}' analysed successfully!", "success")

        except Exception as exc:
            logger.error("Error %s: %s", original, exc)
            ctx["error"] = str(exc)
            flash(f"Error: {exc}", "danger")

    return render_template("dashboard.html", form=form, **ctx)


# ── Errors ─────────────────────────────────────────────────────

@app.errorhandler(403)
def forbidden(e): return render_template("403.html"), 403

@app.errorhandler(404)
def not_found(e): return render_template("404.html"), 404

@app.errorhandler(413)
def too_large(e):
    flash("File too large (max 16 MB).", "danger")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True)
