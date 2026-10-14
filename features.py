import json
import os
import urllib.request
import urllib.error
from datetime import datetime
from flask import abort, flash, redirect, render_template, request, url_for, jsonify
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash


def install(app, db, User, Article, ClubEvent, ForumPost, ROLES):
    """Install Ushirika member accounts, Events Manager roles, AI studio and club chat."""
    MEMBER_ROLE = "member"
    EVENT_MANAGER_ROLE = "events_manager"
    VICE_EVENTS_MANAGER_ROLE = "vice_events_manager"
    EVENTS_MANAGER_NAME = "clara wanza"
    VICE_EVENTS_MANAGER_NAME = "jack denis rengo"

    class ChatMessage(db.Model):
        __tablename__ = "chat_message"
        id = db.Column(db.Integer, primary_key=True)
        sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        body = db.Column(db.Text, nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        sender = db.relationship("User")

    def approved_account():
        return current_user.is_authenticated and current_user.active and current_user.approved

    def role_allowed(*roles):
        if not approved_account() or current_user.role not in roles:
            abort(403)

    def normalize(value):
        return " ".join((value or "").lower().split())

    def gemini(prompt):
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            return None
        model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "system_instruction": {"parts": [{"text": (
                "You are Ushirika Journalism Club's event planning assistant. "
                "Create practical, inclusive, campus-appropriate plans and poster copy. "
                "Never invent official club policies, prices, contacts, or dates. "
                "Use clear headings and concise actionable bullets."
            )}]},
            "contents": [{"parts": [{"text": prompt}]}],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                result = json.loads(response.read().decode("utf-8"))
            parts = result.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            text = "\n".join(p.get("text", "") for p in parts if p.get("text"))
            return text.strip() or None
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, KeyError):
            return None

    @app.route("/member-account", methods=["GET", "POST"])
    def member_account():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")
            valid_email = email.count("@") == 1 and bool(email.split("@", 1)[0]) and "." in email.split("@", 1)[1]
            if not name or not valid_email:
                flash("Enter your full name and a valid email address.", "danger")
            elif len(password) < 12:
                flash("Use a password with at least 12 characters.", "danger")
            elif password != confirm:
                flash("The passwords do not match.", "danger")
            elif User.query.filter_by(email=email).first():
                flash("An account already uses that email address.", "danger")
            else:
                user = User(full_name=name, email=email, role=MEMBER_ROLE, approved=False)
                user.password_hash = generate_password_hash(password)
                db.session.add(user)
                db.session.commit()
                flash("Member account request received. A developer must approve it before you can sign in.", "success")
                return redirect(url_for("login"))
        return render_template("member_account.html")

    @app.route("/dashboard/ai", methods=["GET", "POST"])
    @login_required
    def ai_studio():
        role_allowed(MEMBER_ROLE, EVENT_MANAGER_ROLE, VICE_EVENTS_MANAGER_ROLE, "developer", "patron", "assistant_patron", "chairperson", "vice_chairperson", "secretary_general", "production_manager", "chief_editor", "communication_manager")
        result = ""
        mode = request.form.get("mode", "event_plan")
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            date = request.form.get("event_date", "").strip()
            venue = request.form.get("venue", "").strip()
            audience = request.form.get("audience", "members and students").strip()
            goal = request.form.get("goal", "").strip()
            if mode == "poster":
                prompt = f"Create polished poster copy for a club event. Event: {title}. Date/time: {date}. Venue: {venue}. Audience: {audience}. Goal: {goal}. Include a short headline, 1-sentence hook, key details and a call to action."
            else:
                prompt = f"Plan this journalism club event: {title}. Date/time: {date}. Venue: {venue}. Audience: {audience}. Goal: {goal}. Return a timeline, programme ideas, publicity checklist, staffing roles, materials, risk checks and follow-up plan."
            result = gemini(prompt)
            if not result:
                if mode == "poster":
                    result = (f"{title or 'USHIRIKA JOURNALISM CLUB EVENT'}\n\n"
                              f"{goal or 'Stories. Ideas. Community.'}\n\n"
                              f"DATE / TIME: {date or 'To be announced'}\n"
                              f"VENUE: {venue or 'To be announced'}\n"
                              f"FOR: {audience or 'Club members and students'}\n\n"
                              "JOIN US • SHARE • REPORT • CONNECT")
                else:
                    result = (f"EVENT PLAN — {title or 'Ushirika Club Event'}\n\n"
                              "1. Preparation: confirm venue, programme, speakers and permissions.\n"
                              "2. Publicity: publish a poster, website notice and member announcement.\n"
                              "3. Programme: opening, main activity, audience participation, Q&A and closing.\n"
                              "4. Staffing: event lead, registration desk, programme host, photographer and communications lead.\n"
                              "5. Safety: confirm venue capacity, accessibility, emergency contacts and responsible supervision.\n"
                              "6. Follow-up: publish highlights, thank participants and record lessons learned.")
                flash("AI key is not configured, so the built-in planning template was used. Add GEMINI_API_KEY in Render to enable Gemini generation.", "info")
        return render_template("ai_studio.html", result=result, mode=mode)

    @app.get("/chat")
    @login_required
    def chat():
        role_allowed(MEMBER_ROLE, EVENT_MANAGER_ROLE, VICE_EVENTS_MANAGER_ROLE, "developer", "patron", "assistant_patron", "chairperson", "vice_chairperson", "secretary_general", "treasurer", "production_manager", "chief_editor", "communication_manager")
        messages = ChatMessage.query.order_by(ChatMessage.created_at.asc()).limit(150).all()
        return render_template("chat.html", messages=messages)

    @app.post("/chat/send")
    @login_required
    def chat_send():
        role_allowed(MEMBER_ROLE, EVENT_MANAGER_ROLE, VICE_EVENTS_MANAGER_ROLE, "developer", "patron", "assistant_patron", "chairperson", "vice_chairperson", "secretary_general", "treasurer", "production_manager", "chief_editor", "communication_manager")
        body = request.form.get("body", "").strip()
        if body:
            db.session.add(ChatMessage(sender_id=current_user.id, body=body[:2000]))
            db.session.commit()
        return redirect(url_for("chat"))

    @app.get("/api/members")
    @login_required
    def api_members():
        role_allowed(MEMBER_ROLE, EVENT_MANAGER_ROLE, VICE_EVENTS_MANAGER_ROLE, "developer", "patron", "assistant_patron", "chairperson", "vice_chairperson", "secretary_general", "treasurer", "production_manager", "chief_editor", "communication_manager")
        users = User.query.filter_by(active=True, approved=True).order_by(User.full_name.asc()).all()
        return jsonify([{"id": u.id, "name": u.full_name, "role": u.role} for u in users])

    # Give the two Events Manager roles access to the existing event creator.
    original_new_event = app.view_functions.get("new_event")
    if original_new_event:
        @app.route("/dashboard/events/new", methods=["GET", "POST"], endpoint="events_manager_new_event")
        @login_required
        def events_manager_new_event():
            if not approved_account() or current_user.role not in {EVENT_MANAGER_ROLE, VICE_EVENTS_MANAGER_ROLE}:
                return original_new_event()
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
        app.view_functions["new_event"] = events_manager_new_event

    # Replace leadership registration while keeping public member registration separate.
    original_register = app.view_functions.get("register")
    def leadership_register():
        if request.method == "POST":
            name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            role = request.form.get("role", "").strip()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")
            normalized = normalize(name)
            valid_email = email.count("@") == 1 and bool(email.split("@", 1)[0]) and "." in email.split("@", 1)[1]
            restricted = {
                EVENT_MANAGER_ROLE: EVENTS_MANAGER_NAME,
                VICE_EVENTS_MANAGER_ROLE: VICE_EVENTS_MANAGER_NAME,
            }
            if not name or not valid_email or role not in ROLES or role == "developer":
                flash("Choose a valid leadership role and use a valid email address.", "danger")
            elif len(password) < 12:
                flash("Use a password with at least 12 characters.", "danger")
            elif password != confirm:
                flash("The passwords do not match.", "danger")
            elif User.query.filter_by(email=email).first():
                flash("An account already uses that email address.", "danger")
            elif role in restricted and normalized != restricted[role]:
                flash(f"The {ROLES[role]} role is restricted to {restricted[role]}.", "danger")
            elif role in restricted and User.query.filter_by(role=role).first():
                flash("That leadership role already has an account. Contact the developer for recovery.", "danger")
            else:
                user = User(full_name=name, email=email, role=role, approved=False)
                user.password_hash = generate_password_hash(password)
                db.session.add(user)
                db.session.commit()
                flash("Leadership account request received. A developer must approve it before you can sign in.", "success")
                return redirect(url_for("login"))
        return render_template("register.html")

    if original_register:
        app.view_functions["register"] = leadership_register

    @app.get("/dashboard", endpoint="dashboard_v2")
    @login_required
    def dashboard_v2():
        if not current_user.approved or not current_user.active:
            return redirect(url_for("login"))
        pending = Article.query.filter_by(status="pending").count() if current_user.role in {"developer", "chief_editor", "patron", "assistant_patron"} else 0
        return render_template("dashboard_v2.html", pending_articles=pending, is_events_manager=current_user.role in {EVENT_MANAGER_ROLE, VICE_EVENTS_MANAGER_ROLE})

    app.view_functions["dashboard"] = dashboard_v2

    @app.get("/health/features")
    def feature_health():
        return jsonify({"ok": True, "features": ["member-accounts", "club-chat", "events-ai", "poster-studio"]})

    app.extensions["ushirika_features"] = {
        "member_role": MEMBER_ROLE,
        "events_manager_role": EVENT_MANAGER_ROLE,
        "vice_events_manager_role": VICE_EVENTS_MANAGER_ROLE,
        "events_manager_name": EVENTS_MANAGER_NAME,
        "vice_events_manager_name": VICE_EVENTS_MANAGER_NAME,
        "chat_model": ChatMessage,
    }
    return app
