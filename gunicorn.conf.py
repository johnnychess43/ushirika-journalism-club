def on_starting(server):
    from app import app, db, User, Article, ClubEvent, ForumPost, ROLES, limiter
    from features import install
    ROLES.update({
        "events_manager": "Events Manager",
        "vice_events_manager": "Vice Events Manager",
    })
    install(app, db, User, Article, ClubEvent, ForumPost, ROLES, limiter=limiter)
    with app.app_context():
        db.create_all()
