import os
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from extensions import db,limiter
from models import AdminUser
from seed import seed_content

@pytest.fixture
def app(tmp_path):
    uri=os.getenv('TEST_DATABASE_URL')
    if uri and 'test' not in uri.rsplit('/',1)[-1]: raise RuntimeError('Use a dedicated database with test in its name. Tests destroy all tables.')
    application=create_app({'TESTING':True,'APP_ENV':'development','SECRET_KEY':'test-only-secret-long-enough-for-tests','SQLALCHEMY_DATABASE_URI':uri or 'sqlite:///'+str(tmp_path/'test.db'),'UPLOAD_ROOT':str(tmp_path/'uploads'),'WTF_CSRF_ENABLED':True,'RATELIMIT_ENABLED':False,'STORAGE_BACKEND':'local','TRUST_PROXY':False})
    with application.app_context():
        db.drop_all(); db.create_all(); seed_content()
        user=AdminUser(email='admin@example.com'); user.set_password('Testing-only-password-123'); db.session.add(user); db.session.commit()
    yield application
    with application.app_context(): db.session.remove(); db.drop_all()

@pytest.fixture
def client(app): return app.test_client()

def csrf(client): return client.get('/api/auth/session').json['csrf_token']

def signed(client,method,url,**kwargs):
    headers=kwargs.pop('headers',{}); headers['X-CSRFToken']=csrf(client)
    return client.open(url,method=method,headers=headers,**kwargs)

@pytest.fixture
def admin(client):
    response=signed(client,'POST','/api/auth/login',json={'email':'admin@example.com','password':'Testing-only-password-123'})
    assert response.status_code==200
    return client

@pytest.fixture
def project_data(): return dict(title='Integration test project',slug='integration-test-project',short_description='Test-only content, not a portfolio claim.',description='Detailed test analysis',status='draft',technologies=['Python','SQL'])
