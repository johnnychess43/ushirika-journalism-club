import csv
import io
import os
import secrets
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, url_for, Response
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = Path(os.environ.get("INSTANCE_DIR", BASE_DIR / "instance"))
UPLOAD_DIR = INSTANCE_DIR / "uploads"
GALLERY_DIR = UPLOAD_DIR / "gallery"
DOCS_DIR = UPLOAD_DIR / "treasurer"
for folder in (INSTANCE_DIR, UPLOAD_DIR, GALLERY_DIR, DOCS_DIR):
    folder.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, instance_path=str(INSTANCE_DIR), instance_relative_config=True)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///" + str(INSTANCE_DIR / "ushirika.db")).replace("postgres://", "postgresql://", 1).replace("postgresql://", "postgresql+psycopg://", 1),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "true").lower() == "true",
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "true").lower() == "true",
)
db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to access that page."
login_manager.login_message_category = "info"

ROLES = {
    "developer": "Developer",
    "patron": "Club Patron",
    "assistant_patron": "Assistant Patron",
    "chairperson": "Chairperson / President",
    "vice_chairperson": "Vice Chairperson",
    "secretary_general": "Secretary General",
    "treasurer": "Treasurer",
    "production_manager": "Production Manager",
    "chief_editor": "Chief Editor",
    "communication_manager": "Communication Manager",
}
PATRON_NAMES = {"victor j. njogu", "victor njogu"}
ASSISTANT_PATRON_NAMES = {"meshack m.ngangi", "meshack m. ngangi", "meshack m.ngangi", "meshack m. ngangI".lower()}
TREASURER_NAME = "john chesiro cheptai"
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
DOC_EXTENSIONS = {"csv", "xlsx", "pptx", "accdb", "pbix", "pdf", "docx"}
PAYMENT_NUMBER = os.environ.get("MPESA_RECIPIENT_NUMBER", "0140415653")


def allowed_file(filename, extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in extensions


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(40), nullable=False, default="chairperson")
    approved = db.Column(db.Boolean, nullable=False, default=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    summary = db.Column(db.String(500), default="")
    body = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    author = db.relationship("User", backref="articles")


class ClubEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    description = db.Column(db.Text, nullable=False)
    venue = db.Column(db.String(180), default="")
    event_date = db.Column(db.DateTime, nullable=True)
    fee = db.Column(db.Integer, default=0, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    creator = db.relationship("User")


class ForumPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    body = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    author = db.relationship("User")


class MeetingMinute(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    meeting_date = db.Column(db.Date, nullable=True)
    content = db.Column(db.Text, nullable=False)
    file_name = db.Column(db.String(255), default="")
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    author = db.relationship("User")


class GalleryPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    caption = db.Column(db.String(220), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    uploader = db.relationship("User")


class Contribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_name = db.Column(db.String(120), nullable=False)
    member_email = db.Column(db.String(180), default="")
    amount = db.Column(db.Integer, nullable=False)
    reference = db.Column(db.String(100), default="")
    payment_type = db.Column(db.String(100), default="Registration fee")
    verified = db.Column(db.Boolean, default=False, nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    recorder = db.relationship("User")


class TreasurerFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    uploader = db.relationship("User")


class SiteSetting(db.Model):
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, default="")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if not current_user.active or not current_user.approved:
                logout_user()
                flash("Your account is awaiting approval or has been disabled.", "warning")
                return redirect(url_for("login"))
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def can_publish():
    return current_user.is_authenticated and current_user.approved and current_user.role in {
        "developer", "patron", "assistant_patron", "chairperson", "vice_chairperson",
        "secretary_general", "production_manager", "chief_editor", "communication_manager"
    }


def setting(key, default=""):
    item = db.session.get(SiteSetting, key)
    return item.value if item else default


@app.context_processor
def inject_globals():
    return {"ROLES": ROLES, "payment_number": PAYMENT_NUMBER, "site_setting": setting, "can_publish": can_publish}


@app.get("/CUK-logo.png")
def cuk_logo():
    return send_from_directory(BASE_DIR, "CUK-logo.png")


@app.get("/")
def home():
    articles = Article.query.filter_by(status="published").order_by(Article.created_at.desc()).limit(3).all()
    events = ClubEvent.query.order_by(ClubEvent.event_date.asc().nullslast(), ClubEvent.created_at.desc()).limit(3).all()
    photos = GalleryPhoto.query.order_by(GalleryPhoto.created_at.desc()).limit(6).all()
    return render_template("home.html", articles=articles, events=events, photos=photos)


@app.get("/articles")
def articles():
    items = Article.query.filter_by(status="published").order_by(Article.created_at.desc()).all()
    return render_template("articles.html", articles=items)


@app.get("/articles/<int:article_id>")
def article_detail(article_id):
    item = Article.query.filter_by(id=article_id, status="published").first_or_404()
    return render_template("article_detail.html", article=item)


@app.get("/gallery")
def gallery():
    photos = GalleryPhoto.query.order_by(GalleryPhoto.created_at.desc()).all()
    return render_template("gallery.html", photos=photos)


@app.get("/events")
def events():
    items = ClubEvent.query.order_by(ClubEvent.event_date.asc().nullslast(), ClubEvent.created_at.desc()).all()
    return render_template("events.html", events=items)


@app.get("/forums")
def forums():
    posts = ForumPost.query.order_by(ForumPost.created_at.desc()).all()
    return render_template("forums.html", posts=posts)


@app.get("/minutes")
@login_required
def minutes():
    if not current_user.approved:
        abort(403)
    items = MeetingMinute.query.order_by(MeetingMinute.meeting_date.desc().nullslast(), MeetingMinute.created_at.desc()).all()
    return render_template("minutes.html", minutes=items)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        normalized = " ".join(name.lower().split())
        if not name or not email or role not in ROLES or role == "developer":
            flash("Please provide your name, email and a valid club role.", "danger")
        elif len(password) < 12:
            flash("Use a password with at least 12 characters.", "danger")
        elif password != confirm:
            flash("The passwords do not match.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("An account already uses that email address.", "danger")
        elif role == "patron" and normalized not in PATRON_NAMES:
            flash("The Patron role is restricted to Victor J. Njogu / Victor Njogu. Use your correct role or contact the developer.", "danger")
        elif role == "assistant_patron" and normalized not in ASSISTANT_PATRON_NAMES:
            flash("The Assistant Patron role is restricted to Meshack M. Ngangi. Use your correct role or contact the developer.", "danger")
        elif role == "treasurer" and normalized != TREASURER_NAME:
            flash("The Treasurer role is restricted to John Chesiro Cheptai.", "danger")
        elif role == "treasurer" and User.query.filter_by(role="treasurer").first():
            flash("A Treasurer account already exists. Contact the developer if it needs recovery.", "danger")
        else:
            user = User(full_name=name, email=email, role=role, approved=False)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Account request received. A developer must approve it before you can sign in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated and current_user.approved:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email, active=True).first()
        if user and user.check_password(password):
            if not user.approved:
                flash("Your account is awaiting developer approval.", "warning")
            else:
                login_user(user, remember=False, fresh=True)
                flash("Welcome back.", "success")
                return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.post("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("home"))


@app.get("/dashboard")
@login_required
def dashboard():
    if not current_user.approved or not current_user.active:
        logout_user()
        flash("Your account is awaiting approval or has been disabled.", "warning")
        return redirect(url_for("login"))
    pending_articles = Article.query.filter_by(status="pending").count() if current_user.role in {"developer", "chief_editor", "patron", "assistant_patron"} else 0
    pending_article_items = Article.query.filter_by(status="pending").order_by(Article.created_at.desc()).all() if current_user.role in {"developer", "chief_editor", "patron", "assistant_patron"} else []
    users_pending = User.query.filter_by(approved=False).count() if current_user.role == "developer" else 0
    return render_template("dashboard.html", pending_articles=pending_articles, pending_article_items=pending_article_items, users_pending=users_pending)


@app.route("/dashboard/articles/new", methods=["GET", "POST"])
@role_required("developer", "patron", "assistant_patron", "chairperson", "vice_chairperson", "secretary_general", "treasurer", "production_manager", "chief_editor", "communication_manager")
def new_article():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        summary = request.form.get("summary", "").strip()
        status = "pending" if current_user.role not in {"developer", "chief_editor", "patron", "assistant_patron"} else "published"
        if title and body:
            item = Article(title=title, summary=summary, body=body, author_id=current_user.id, status=status)
            db.session.add(item)
            db.session.commit()
            flash("Article saved for review." if status == "pending" else "Article published.", "success")
            return redirect(url_for("dashboard"))
        flash("Title and article text are required.", "danger")
    return render_template("editor.html", page_title="Write an article", submit_label="Save article", kind="article")


@app.route("/dashboard/events/new", methods=["GET", "POST"])
@role_required("developer", "patron", "assistant_patron", "chairperson", "vice_chairperson", "secretary_general", "production_manager", "chief_editor", "communication_manager")
def new_event():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("body", "").strip()
        venue = request.form.get("venue", "").strip()
        date_text = request.form.get("event_date", "").strip()
        fee_text = request.form.get("fee", "0").strip()
        try:
            event_date = datetime.fromisoformat(date_text) if date_text else None
            fee = int(fee_text or 0)
            if fee < 0:
                raise ValueError
        except ValueError:
            flash("Enter a valid date and a non-negative whole-number fee.", "danger")
            return render_template("editor.html", page_title="Create an event", submit_label="Save event", kind="event")
        if title and description:
            db.session.add(ClubEvent(title=title, description=description, venue=venue, event_date=event_date, fee=fee, created_by=current_user.id))
            db.session.commit()
            flash("Event published.", "success")
            return redirect(url_for("events"))
        flash("Event title and description are required.", "danger")
    return render_template("editor.html", page_title="Create an event", submit_label="Save event", kind="event")


@app.route("/dashboard/forums/new", methods=["GET", "POST"])
@role_required("developer", "patron", "assistant_patron", "chairperson", "vice_chairperson", "secretary_general", "production_manager", "chief_editor", "communication_manager")
def new_forum():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if title and body:
            db.session.add(ForumPost(title=title, body=body, author_id=current_user.id))
            db.session.commit()
            flash("Forum topic posted.", "success")
            return redirect(url_for("forums"))
        flash("Title and post are required.", "danger")
    return render_template("editor.html", page_title="Start a forum topic", submit_label="Post topic", kind="forum")


@app.route("/dashboard/minutes/new", methods=["GET", "POST"])
@role_required("developer", "secretary_general", "patron", "assistant_patron")
def new_minutes():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("body", "").strip()
        date_text = request.form.get("meeting_date", "").strip()
        try:
            meeting_date = datetime.strptime(date_text, "%Y-%m-%d").date() if date_text else None
        except ValueError:
            meeting_date = None
        if title and content:
            db.session.add(MeetingMinute(title=title, content=content, meeting_date=meeting_date, author_id=current_user.id))
            db.session.commit()
            flash("Meeting minutes saved.", "success")
            return redirect(url_for("minutes"))
        flash("Meeting title and minutes are required.", "danger")
    return render_template("editor.html", page_title="Add meeting minutes", submit_label="Save minutes", kind="minutes")


@app.route("/dashboard/gallery/new", methods=["GET", "POST"])
@role_required("developer", "production_manager", "patron", "assistant_patron")
def new_photo():
    if request.method == "POST":
        file = request.files.get("photo")
        caption = request.form.get("caption", "").strip()
        if not file or not file.filename or not allowed_file(file.filename, IMAGE_EXTENSIONS):
            flash("Choose a JPG, PNG, WEBP or GIF image.", "danger")
        elif not caption:
            flash("Please add a caption.", "danger")
        else:
            safe_name = secure_filename(file.filename)
            stored = secrets.token_hex(12) + "_" + safe_name
            file.save(GALLERY_DIR / stored)
            db.session.add(GalleryPhoto(caption=caption, filename=stored, uploaded_by=current_user.id))
            db.session.commit()
            flash("Photo added to the gallery.", "success")
            return redirect(url_for("gallery"))
    return render_template("editor.html", page_title="Upload gallery photo", submit_label="Upload photo", kind="photo")


@app.get("/gallery/image/<int:photo_id>")
def gallery_image(photo_id):
    photo = db.session.get(GalleryPhoto, photo_id)
    if not photo:
        abort(404)
    return send_from_directory(GALLERY_DIR, photo.filename)


@app.route("/dashboard/treasurer/contributions", methods=["GET", "POST"])
@role_required("developer", "treasurer")
def contributions():
    if request.method == "POST":
        name = request.form.get("member_name", "").strip()
        email = request.form.get("member_email", "").strip()
        reference = request.form.get("reference", "").strip()
        payment_type = request.form.get("payment_type", "Registration fee").strip()
        try:
            amount = int(request.form.get("amount", "0"))
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash("Enter a valid contribution amount in KSh.", "danger")
        else:
            db.session.add(Contribution(member_name=name, member_email=email, amount=amount, reference=reference, payment_type=payment_type, recorded_by=current_user.id, verified=False))
            db.session.commit()
            flash("Contribution recorded as unverified. Confirm the M-PESA reference before marking it verified.", "success")
            return redirect(url_for("contributions"))
    records = Contribution.query.order_by(Contribution.created_at.desc()).all()
    total = db.session.query(func.sum(Contribution.amount)).filter_by(verified=True).scalar() or 0
    return render_template("contributions.html", records=records, total=total)


@app.post("/dashboard/treasurer/contributions/<int:record_id>/verify")
@role_required("developer", "treasurer")
def verify_contribution(record_id):
    record = db.session.get(Contribution, record_id) or abort(404)
    record.verified = not record.verified
    db.session.commit()
    flash("Contribution verification status updated.", "success")
    return redirect(url_for("contributions"))


@app.get("/dashboard/treasurer/export.csv")
@role_required("developer", "treasurer")
def export_contributions():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Member", "Email", "Amount KSh", "Payment type", "M-PESA reference", "Verified", "Date"])
    for row in Contribution.query.order_by(Contribution.created_at.desc()).all():
        writer.writerow([row.member_name, row.member_email, row.amount, row.payment_type, row.reference, "Yes" if row.verified else "No", row.created_at.isoformat()])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=ushirika-contributions.csv"})


@app.route("/dashboard/treasurer/files", methods=["GET", "POST"])
@role_required("developer", "treasurer")
def treasurer_files():
    if request.method == "POST":
        file = request.files.get("document")
        if not file or not file.filename or not allowed_file(file.filename, DOC_EXTENSIONS):
            flash("Allowed formats: CSV, XLSX, PPTX, ACCDB, PBIX, PDF and DOCX.", "danger")
        else:
            safe_name = secure_filename(file.filename)
            stored = secrets.token_hex(12) + "_" + safe_name
            file.save(DOCS_DIR / stored)
            db.session.add(TreasurerFile(original_name=safe_name, stored_name=stored, uploaded_by=current_user.id))
            db.session.commit()
            flash("File uploaded to the protected treasurer workspace.", "success")
            return redirect(url_for("treasurer_files"))
    files = TreasurerFile.query.order_by(TreasurerFile.created_at.desc()).all()
    return render_template("treasurer_files.html", files=files)


@app.get("/dashboard/treasurer/files/<int:file_id>")
@role_required("developer", "treasurer")
def download_treasurer_file(file_id):
    item = db.session.get(TreasurerFile, file_id) or abort(404)
    return send_from_directory(DOCS_DIR, item.stored_name, as_attachment=True, download_name=item.original_name)


@app.route("/payment", methods=["GET", "POST"])
def payment():
    if request.method == "POST" and current_user.is_authenticated and current_user.role in {"developer", "treasurer"}:
        event_name = request.form.get("event_name", "").strip()
        amount = request.form.get("amount", "").strip()
        if event_name and amount.isdigit() and int(amount) > 0:
            db.session.add(SiteSetting(key="payment_prompt", value="Pay KSh " + amount + " for " + event_name + " to M-PESA number " + PAYMENT_NUMBER + ". Use the event name as your payment account/reference and retain your M-PESA confirmation message."))
            db.session.commit()
            flash("Payment instructions updated.", "success")
            return redirect(url_for("payment"))
        flash("Enter an event name and a valid amount.", "danger")
    return render_template("payment.html", payment_prompt=setting("payment_prompt"))


@app.route("/dashboard/articles/<int:article_id>/edit", methods=["GET", "POST"])
@role_required("developer", "chief_editor", "patron", "assistant_patron")
def edit_article(article_id):
    item = db.session.get(Article, article_id) or abort(404)
    if request.method == "POST":
        item.title = request.form.get("title", "").strip()
        item.summary = request.form.get("summary", "").strip()
        item.body = request.form.get("body", "").strip()
        db.session.commit()
        flash("Article updated.", "success")
        return redirect(url_for("dashboard"))
    return render_template("editor.html", page_title="Edit article", submit_label="Save changes", kind="article", item=item)


@app.post("/dashboard/articles/<int:article_id>/publish")
@role_required("developer", "chief_editor", "patron", "assistant_patron")
def publish_article(article_id):
    item = db.session.get(Article, article_id) or abort(404)
    item.status = "published"
    db.session.commit()
    flash("Article approved and published.", "success")
    return redirect(url_for("dashboard"))


@app.get("/admin/users")
@role_required("developer")
def admin_users():
    users = User.query.order_by(User.approved.asc(), User.created_at.desc()).all()
    return render_template("admin_users.html", users=users)


@app.post("/admin/users/<int:user_id>/approve")
@role_required("developer")
def approve_user(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.role == "developer":
        abort(400)
    if user.role == "treasurer" and " ".join(user.full_name.lower().split()) != TREASURER_NAME:
        abort(400)
    user.approved = True
    db.session.commit()
    flash("Account approved.", "success")
    return redirect(url_for("admin_users"))


@app.post("/admin/users/<int:user_id>/disable")
@role_required("developer")
def disable_user(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.role == "developer":
        abort(400)
    user.active = not user.active
    db.session.commit()
    flash("Account status updated.", "success")
    return redirect(url_for("admin_users"))



@app.route("/admin/settings", methods=["GET", "POST"])
@role_required("developer")
def admin_settings():
    fields = {
        "hero_title": "Homepage headline",
        "hero_text": "Homepage introduction",
        "about_text": "About the club",
        "contact_email": "Public club contact email",
    }
    if request.method == "POST":
        for key in fields:
            value = request.form.get(key, "").strip()
            item = db.session.get(SiteSetting, key)
            if item is None:
                item = SiteSetting(key=key, value=value)
                db.session.add(item)
            else:
                item.value = value
        db.session.commit()
        flash("Website content settings saved.", "success")
        return redirect(url_for("admin_settings"))
    return render_template("admin_settings.html", fields=fields)


@app.get("/admin/content")
@role_required("developer")
def admin_content():
    return render_template(
        "admin_content.html",
        articles=Article.query.order_by(Article.created_at.desc()).all(),
        events=ClubEvent.query.order_by(ClubEvent.created_at.desc()).all(),
        forums=ForumPost.query.order_by(ForumPost.created_at.desc()).all(),
        minutes=MeetingMinute.query.order_by(MeetingMinute.created_at.desc()).all(),
        photos=GalleryPhoto.query.order_by(GalleryPhoto.created_at.desc()).all(),
    )


@app.post("/admin/content/<string:kind>/<int:item_id>/delete")
@role_required("developer")
def delete_content(kind, item_id):
    models = {
        "article": Article,
        "event": ClubEvent,
        "forum": ForumPost,
        "minutes": MeetingMinute,
        "photo": GalleryPhoto,
    }
    model = models.get(kind)
    if model is None:
        abort(404)
    item = db.session.get(model, item_id) or abort(404)
    if kind == "photo":
        try:
            (GALLERY_DIR / item.filename).unlink(missing_ok=True)
        except OSError:
            app.logger.warning("Could not remove gallery file %s", item.filename)
    db.session.delete(item)
    db.session.commit()
    flash("Content item deleted.", "success")
    return redirect(url_for("admin_content"))

@app.get("/health")
def health():
    return {"status": "ok"}


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="You do not have permission to access this area."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="That page could not be found."), 404


def bootstrap_developer():
    """Create the first developer account only from deployment environment secrets."""
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    name = os.environ.get("BOOTSTRAP_ADMIN_NAME", "John Chesiro Cheptai").strip()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not email or not password:
        return
    existing = User.query.filter_by(role="developer").first()
    if existing:
        return
    admin = User(full_name=name, email=email, role="developer", approved=True, active=True)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()


with app.app_context():
    db.create_all()
    bootstrap_developer()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
