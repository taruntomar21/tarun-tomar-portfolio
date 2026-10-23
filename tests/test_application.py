from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from PIL import Image
from pypdf import PdfWriter
from sqlalchemy import select
from flask_migrate import upgrade, downgrade
from app import create_app
from extensions import db,limiter
from models import *
from conftest import csrf,signed

PUBLIC=['/','/about','/projects','/skills','/experience','/resume','/blog','/contact','/robots.txt','/sitemap.xml','/healthz','/admin/login','/api/home','/api/projects','/api/profile','/api/skills','/api/categories','/api/blog']
@pytest.mark.parametrize('path',PUBLIC)
def test_public_routes(client,path): assert client.get(path).status_code==200

@pytest.mark.parametrize('path',['/admin','/admin/projects','/admin/profile','/admin/content/skills','/admin/content/education','/admin/content/experience','/admin/content/achievements','/admin/content/categories','/admin/messages','/admin/blog'])
def test_protected_pages(client,path): assert client.get(path).status_code==302

@pytest.mark.parametrize('path',['/admin','/admin/projects','/admin/projects/new','/admin/profile','/admin/content/skills','/admin/content/education','/admin/content/experience','/admin/content/achievements','/admin/content/categories','/admin/messages','/admin/blog','/admin/blog/new'])
def test_admin_pages_render(admin,path): assert admin.get(path).status_code==200

@pytest.mark.parametrize('method,path,body',[('GET','/api/admin/projects',None),('POST','/api/admin/projects',{}),('PATCH','/api/admin/projects/1',{}),('DELETE','/api/admin/projects/1',{'confirm':'delete'}),('PATCH','/api/admin/profile',{}),('POST','/api/admin/content/skills',{}),('GET','/api/admin/messages',None),('POST','/api/admin/blog',{})])
def test_admin_apis_require_auth(client,method,path,body): assert signed(client,method,path,json=body).status_code==401

def test_csrf_required(client): assert client.post('/api/contact',json={}).status_code==400

def test_wrong_password_and_logout(client):
    r=signed(client,'POST','/api/auth/login',json={'email':'admin@example.com','password':'wrong'})
    assert r.status_code==401
    assert signed(client,'POST','/api/auth/login',json={'email':'admin@example.com','password':'Testing-only-password-123'}).status_code==200
    assert signed(client,'POST','/api/auth/logout',json={}).status_code==200
    assert client.get('/api/admin/projects').status_code==401

def test_html_login(client):
    r=client.post('/admin/login',data={'csrf_token':csrf(client),'email':'admin@example.com','password':'Testing-only-password-123'})
    assert r.status_code==302 and r.location.endswith('/admin')
    assert client.get('/admin').status_code==200
    assert signed(client,'POST','/admin/logout',data={}).status_code==302

def test_project_lifecycle(admin,client,app,project_data):
    # client and admin refer to the same fixture client; use a separate public browser.
    public=app.test_client()
    r=signed(admin,'POST','/api/admin/projects',json=project_data); assert r.status_code==201, r.json
    pid=r.json['data']['id']
    assert public.get('/projects/integration-test-project').status_code==404
    assert public.get('/api/projects').json['pagination']['total']==0
    r=signed(admin,'PATCH',f'/api/admin/projects/{pid}',json={'status':'published','featured':True,'results':'Test result','title':'Updated test project'})
    assert r.status_code==200
    assert public.get('/projects/integration-test-project').status_code==200
    assert b'Updated test project' in public.get('/').data
    assert public.get('/api/projects/integration-test-project').json['data']['results']=='Test result'
    assert b'/projects/integration-test-project' in public.get('/sitemap.xml').data
    assert signed(admin,'DELETE',f'/api/admin/projects/{pid}',json={}).status_code==422
    assert signed(admin,'DELETE',f'/api/admin/projects/{pid}',json={'confirm':'delete'}).status_code==204
    assert public.get('/projects/integration-test-project').status_code==404
    with app.app_context(): assert db.session.get(Project,pid) is None

def test_search_filters_and_pagination(admin,app,project_data):
    cat=admin.get('/api/categories').json['data'][0]['id']
    for i in range(12):
        payload={**project_data,'slug':f'test-{i}','title':f'Analysis {i}','status':'published','category_id':cat,'featured':i==0,'technologies':['Python' if i<3 else 'SQL']}
        assert signed(admin,'POST','/api/admin/projects',json=payload).status_code==201
    public=app.test_client()
    assert public.get('/api/projects').json['pagination']['pages']==2
    assert len(public.get('/api/projects?page=2').json['data'])==3
    assert public.get('/api/projects?technology=Python').json['pagination']['total']==3
    assert public.get(f'/api/projects?category={cat}').json['pagination']['total']==12
    assert public.get('/api/projects?q=Analysis+11').json['pagination']['total']==1
    assert public.get('/api/projects?q=%25').json['pagination']['total']==0
    assert public.get('/api/projects?sort=featured').json['data'][0]['featured'] is True
    assert public.get('/api/projects?sort=oldest').json['data'][0]['slug']=='test-0'
    assert public.get('/projects?page=2').status_code==200
    assert public.get('/projects?sort=unknown').status_code==422
    assert public.get('/api/projects?page=-1').status_code==422
    assert public.get('/api/projects?q=%27%20OR%201=1--').json['pagination']['total']==0

def test_unique_slug_and_validation(admin,project_data):
    assert signed(admin,'POST','/api/admin/projects',json=project_data).status_code==201
    assert signed(admin,'POST','/api/admin/projects',json=project_data).status_code==409
    for patch in [{'slug':'Not valid!'},{'title':''},{'github_url':'javascript:alert(1)'},{'demo_url':'https://user:password@example.com'},{'status':'secret'},{'category_id':99999},{'display_order':'abc'},{'technologies':[1]}]:
        assert signed(admin,'POST','/api/admin/projects',json={**project_data,'slug':'another',**patch}).status_code==422,patch
    assert signed(admin,'POST','/api/admin/projects',json=[]).status_code==422

def test_safe_rendering(admin,app,project_data):
    malicious='<script>alert(1)</script>'
    r=signed(admin,'POST','/api/admin/projects',json={**project_data,'title':malicious,'description':malicious,'status':'published'})
    assert r.status_code==201
    page=app.test_client().get('/projects/integration-test-project')
    assert malicious.encode() not in page.data
    assert b'&lt;script&gt;' in page.data

def test_contact_and_inbox(client,app,admin):
    public=app.test_client()
    data={'name':'Test visitor','email':'visitor@example.com','subject':'Test subject','message':'A test message.'}
    assert signed(public,'POST','/api/contact',json=data).status_code==201
    assert signed(public,'POST','/api/contact',json={**data,'email':'bad-email'}).status_code==422
    assert signed(public,'POST','/api/contact',json={**data,'name':''}).status_code==422
    assert signed(public,'POST','/api/contact',json={**data,'website':'spam'}).status_code==201
    with app.app_context(): assert db.session.query(ContactMessage).count()==1
    mid=admin.get('/api/admin/messages').json['data'][0]['id']
    assert signed(admin,'PATCH',f'/api/admin/messages/{mid}',json={'archived':True,'read':True}).status_code==200
    assert b'Test subject' not in admin.get('/admin/messages').data
    assert b'Test subject' in admin.get('/admin/messages?archived=1').data
    assert signed(admin,'DELETE',f'/api/admin/messages/{mid}',json={'confirm':'delete'}).status_code==204

def test_profile_and_content_crud(admin,app):
    assert signed(admin,'PATCH','/api/admin/profile',json={'headline':'Editable headline','linkedin_url':'https://linkedin.com/in/example'}).status_code==200
    assert b'Editable headline' in app.test_client().get('/').data
    resources={'skills':{'name':'Test skill','category':'Programming Languages','level':'Learning'},'education':{'title':'Test degree','organization':'Test institution'},'experience':{'title':'Test experience','organization':'Test organization'},'achievements':{'title':'Test achievement'},'categories':{'name':'Test category'}}
    for resource,data in resources.items():
        r=signed(admin,'POST',f'/api/admin/content/{resource}',json={**data,'display_order':2}); assert r.status_code==201,r.json
        eid=r.json['data']['id']
        assert signed(admin,'PATCH',f'/api/admin/content/{resource}/{eid}',json={'display_order':1}).status_code==200
        assert admin.get(f'/admin/content/{resource}/{eid}/edit').status_code==200
        assert signed(admin,'DELETE',f'/api/admin/content/{resource}/{eid}',json={'confirm':'delete'}).status_code==204

def test_category_removal_keeps_project(admin,project_data):
    cat=signed(admin,'POST','/api/admin/content/categories',json={'name':'Temporary category'}).json['data']['id']
    pid=signed(admin,'POST','/api/admin/projects',json={**project_data,'category_id':cat}).json['data']['id']
    assert signed(admin,'DELETE',f'/api/admin/content/categories/{cat}',json={'confirm':'delete'}).status_code==204
    assert admin.get(f'/api/admin/projects/{pid}').json['data']['category'] is None

def test_blog_lifecycle(admin,app):
    data={'title':'Test article','slug':'test-article','summary':'A test note.','body':'Plain text body.','tags':['SQL'],'status':'draft'}
    r=signed(admin,'POST','/api/admin/blog',json=data); assert r.status_code==201
    pid=r.json['data']['id']; public=app.test_client()
    assert public.get('/blog/test-article').status_code==404
    assert public.get('/api/blog/test-article').status_code==404
    assert signed(admin,'PATCH',f'/api/admin/blog/{pid}',json={'status':'published'}).status_code==200
    assert public.get('/blog/test-article').status_code==200
    assert public.get('/api/blog/test-article').json['data']['tags']==['SQL']
    assert b'Test article' in public.get('/blog?category=').data
    assert admin.get('/admin/blog/'+str(pid)+'/edit').status_code==200
    assert signed(admin,'PATCH',f'/api/admin/blog/{pid}',json={'status':'draft'}).status_code==200
    assert public.get('/blog/test-article').status_code==404
    assert signed(admin,'DELETE',f'/api/admin/blog/{pid}',json={'confirm':'delete'}).status_code==204

def image():
    data=BytesIO(); Image.new('RGB',(400,240),'#087b65').save(data,'PNG'); data.seek(0); return data


def test_uploads_draft_privacy_and_restart(admin, app, project_data):
    data = {
        **project_data,
        'thumbnail': (image(), 'test.png'),
        'images': [(image(), 'gallery.png')],
    }

    r = signed(
        admin,
        'POST',
        '/api/admin/projects',
        data=data,
        content_type='multipart/form-data',
    )
    assert r.status_code == 201, r.json

    pid = r.json['data']['id']
    url = r.json['data']['thumbnail_url']
    gallery = r.json['data']['images']

    assert len(gallery) == 1

    # This client never sends cookies, so it remains anonymous.
    public = app.test_client(use_cookies=False)

    # Draft media must not be accessible to anonymous visitors.
    assert public.get(url).status_code == 404
    admin_response = admin.get(url)


    assert admin_response.status_code == 200, (
        f"Admin could not access draft media: "
        f"status={admin_response.status_code}, "
        f"content_type={admin_response.content_type}"
    )
    assert admin_response.mimetype == 'image/webp'

    # Publish the project; its media should now be publicly accessible.
    response = signed(
        admin,
        'PATCH',
        f'/api/admin/projects/{pid}',
        json={'status': 'published'},
    )
    assert response.status_code == 200, response.json

    assert public.get(url).status_code == 200
    assert public.get(gallery[0]['url']).status_code == 200

    # A new Flask app should access the same database and stored media.
    new_app = create_app({**app.config, 'TESTING': True})

    with new_app.test_client(use_cookies=False) as new_public:
        assert new_public.get(
            '/projects/integration-test-project'
        ).status_code == 200
        assert new_public.get(url).status_code == 200

    # Removing the thumbnail should make its media inaccessible again.
    response = signed(
        admin,
        'PATCH',
        f'/api/admin/projects/{pid}',
        json={
            'remove_image_ids': [gallery[0]['id']],
            'remove_thumbnail': True,
        },
    )
    assert response.status_code == 200, response.json

    assert public.get(url).status_code == 404


def test_invalid_upload_and_failed_upload_cleanup(admin,app,project_data):
    for data in [BytesIO(b'fake image'),BytesIO(b'<svg onload="alert(1)"></svg>')]:
        r=signed(admin,'POST','/api/admin/projects',data={**project_data,'thumbnail':(data,'bad.png')},content_type='multipart/form-data')
        assert r.status_code==422
    assert signed(admin,'POST','/api/admin/projects',json=project_data).status_code==201
    r=signed(admin,'POST','/api/admin/projects',data={**project_data,'thumbnail':(image(),'good.png')},content_type='multipart/form-data')
    assert r.status_code==409
    assert list(Path(app.config['UPLOAD_ROOT']).rglob('*.webp'))==[]

def test_resume_validation_and_replacement(admin,app):
    bad=signed(admin,'POST','/api/admin/profile',data={'resume':(BytesIO(b'not pdf'),'bad.pdf')},content_type='multipart/form-data'); assert bad.status_code==422
    writer=PdfWriter(); writer.add_blank_page(width=612,height=792); buf=BytesIO(); writer.write(buf); buf.seek(0)
    r=signed(admin,'POST','/api/admin/profile',data={'resume':(buf,'resume.pdf')},content_type='multipart/form-data'); assert r.status_code==200,r.json
    public=app.test_client(); response=public.get('/resume/download',follow_redirects=True)
    assert response.status_code==200 and response.data.startswith(b'%PDF-')
    assert 'attachment' in response.headers['Content-Disposition']
    assert signed(admin,'PATCH','/api/admin/profile',json={'remove_resume':True}).status_code==200
    assert public.get('/resume/download').status_code==404

def test_s3_storage_adapter(admin,app,monkeypatch,project_data):
    mock=MagicMock(); mock.generate_presigned_url.return_value='https://storage.example.com/signed-object'
    monkeypatch.setattr('storage.s3',lambda:mock); monkeypatch.setattr('routes.main.s3',lambda:mock)
    app.config.update(STORAGE_BACKEND='s3',S3_BUCKET='test-bucket')
    r=signed(admin,'POST','/api/admin/projects',data={**project_data,'status':'published','thumbnail':(image(),'test.png')},content_type='multipart/form-data'); assert r.status_code==201
    assert mock.put_object.call_count==1
    response=app.test_client().get(r.json['data']['thumbnail_url']); assert response.status_code==302
    assert response.location=='https://storage.example.com/signed-object'
    assert mock.generate_presigned_url.call_args.kwargs['ExpiresIn']==300

def test_security_headers_and_404(client):
    assert client.get('/does-not-exist').status_code==404
    assert client.get('/api/projects/nonexistent').json['error']['code']==404
    r=client.get('/')
    assert r.headers['X-Content-Type-Options']=='nosniff'
    assert "script-src 'self'" in r.headers['Content-Security-Policy']
    assert client.get('/admin/login').headers['Cache-Control']=='no-store'

def test_cli_admin_creation(app):
    runner=app.test_cli_runner()
    r=runner.invoke(args=['create-admin','--email','another@example.com'],input='A-new-strong-password-123\nA-new-strong-password-123\n')
    assert r.exit_code==0,r.output
    r=runner.invoke(args=['create-admin','--email','weak@example.com'],input='short\nshort\n')
    assert r.exit_code!=0
    with app.app_context():
        user=db.session.scalar(select(AdminUser).where(AdminUser.email=='another@example.com'))
        assert user.password_hash!='A-new-strong-password-123' and user.check_password('A-new-strong-password-123')

def test_production_rejects_sqlite():
    with pytest.raises(RuntimeError,match='PostgreSQL'):
        create_app({'APP_ENV':'production','SECRET_KEY':'long-enough-key-for-production-12345','SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:'})

def test_login_rate_limit(app):
    limited=create_app({**app.config,'RATELIMIT_ENABLED':True,'RATELIMIT_STORAGE_URI':'memory://'})
    client=limited.test_client()
    with limited.app_context(): limiter.reset()
    statuses=[signed(client,'POST','/api/auth/login',json={'email':'absent@example.com','password':'wrong'}).status_code for _ in range(6)]
    assert statuses[-1]==429

def test_html_project_editor_and_actions(admin,app,project_data):
    r=signed(admin,'POST','/admin/projects/new',data={**project_data,'technologies':'Python, SQL'})
    assert r.status_code==302
    pid=admin.get('/api/admin/projects').json['data'][0]['id']
    assert signed(admin,'POST',f'/admin/projects/{pid}/publish',data={}).status_code==302
    assert signed(admin,'POST',f'/admin/projects/{pid}/feature',data={}).status_code==302
    assert b'Integration test project' in app.test_client().get('/').data
    assert signed(admin,'POST',f'/admin/projects/{pid}/edit',data={**project_data,'title':'Edited using form','technologies':'Python','status':'published'}).status_code==302
    assert signed(admin,'POST',f'/admin/projects/{pid}/delete',data={'confirm':'delete'}).status_code==302
