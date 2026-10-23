from extensions import db
from models import Profile, AdminUser
from conftest import signed


def test_homepage_before_profile_seed(app):
    with app.app_context():
        profile=db.session.get(Profile,1)
        db.session.delete(profile); db.session.commit()
    response=app.test_client().get('/')
    assert response.status_code==200
    assert b'Tarun Tomar' in response.data


def test_password_whitespace_preserved_and_cli_email_case(app):
    password='  A-test-password-with-edge-spaces-123  '
    with app.app_context():
        user=AdminUser(email='spaces@example.com'); user.set_password(password)
        db.session.add(user); db.session.commit()
    client=app.test_client()
    response=signed(client,'POST','/api/auth/login',json={'email':'spaces@example.com','password':password})
    assert response.status_code==200
    runner=app.test_cli_runner()
    result=runner.invoke(args=['create-admin','--email','MixedCase@Example.com'],input='Unique-test-password-123\nUnique-test-password-123\n')
    assert result.exit_code==0,result.output
    with app.app_context():
        assert db.session.scalar(db.select(AdminUser).where(AdminUser.email=='mixedcase@example.com')) is not None
