import pytest
from app import app, db, User, Article


@pytest.fixture()
def client(tmp_path, monkeypatch):
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="test-secret", SESSION_COOKIE_SECURE=False)
    with app.app_context():
        db.drop_all()
        db.create_all()
        admin = User(full_name="Test Developer", email="dev@example.test", role="developer", approved=True, active=True)
        admin.set_password("test-password-long-enough")
        chair = User(full_name="Test Chairperson", email="chair@example.test", role="chairperson", approved=True, active=True)
        chair.set_password("chair-password-long-enough")
        db.session.add_all([admin, chair])
        db.session.commit()
    with app.test_client() as test_client:
        yield test_client
    with app.app_context():
        db.session.remove()
        db.drop_all()


def login(client, email, password):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


def test_homepage_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Ushirika Journalism Club" in response.data
    assert b"Stories that bring us closer" in response.data


def test_patron_role_rejects_other_names(client):
    response = client.post("/register", data={
        "full_name": "Someone Else",
        "email": "someone@example.test",
        "role": "patron",
        "password": "long-enough-password-123",
        "confirm_password": "long-enough-password-123",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"restricted to Victor" in response.data


def test_new_accounts_require_approval(client):
    response = client.post("/register", data={
        "full_name": "Victor J. Njogu",
        "email": "victor@example.test",
        "role": "patron",
        "password": "long-enough-password-123",
        "confirm_password": "long-enough-password-123",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"developer must approve" in response.data
    with app.app_context():
        user = User.query.filter_by(email="victor@example.test").one()
        assert user.approved is False
        assert user.password_hash != "long-enough-password-123"
        assert user.check_password("long-enough-password-123")


def test_unapproved_user_cannot_sign_in(client):
    with app.app_context():
        user = User(full_name="Pending Member", email="pending@example.test", role="chairperson", approved=False)
        user.set_password("long-enough-password-123")
        db.session.add(user)
        db.session.commit()
    response = client.post("/login", data={"email": "pending@example.test", "password": "long-enough-password-123"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"awaiting developer approval" in response.data


def test_editorial_roles_submit_pending_articles(client):
    login(client, "chair@example.test", "chair-password-long-enough")
    response = client.post("/dashboard/articles/new", data={
        "title": "A test article",
        "summary": "A short test summary",
        "body": "A responsible journalism test article.",
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        article = Article.query.filter_by(title="A test article").one()
        assert article.status == "pending"


def test_developer_tools_are_restricted(client):
    response = client.get("/admin/users", follow_redirects=False)
    assert response.status_code in (302, 401)
    login(client, "chair@example.test", "chair-password-long-enough")
    response = client.get("/admin/users")
    assert response.status_code == 403
    client.post("/logout")
    login(client, "dev@example.test", "test-password-long-enough")
    response = client.get("/admin/users")
    assert response.status_code == 200


def test_security_headers_are_present(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_feature_health_does_not_claim_email_delivery(client):
    response = client.get("/health/features")
    assert response.status_code == 200
    assert "password-recovery-no-email" in response.json["features"]
