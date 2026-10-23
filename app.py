import os
import secrets
from pathlib import Path
import click
from flask import Flask, render_template, jsonify, request
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import HTTPException
from config import Config
from extensions import db, migrate, csrf, login, limiter
from models import AdminUser
from services import ValidationError, profile, email

def create_app(test_config=None):
    app=Flask(__name__)
    app.config.from_object(Config)
    app.config.update(test_config or {})
    production=app.config['APP_ENV']=='production'
    if not app.config['SECRET_KEY']:
        if production: raise RuntimeError('SECRET_KEY is required in production.')
        app.config['SECRET_KEY']=secrets.token_hex(32)
        app.logger.warning('Development-only ephemeral secret; set SECRET_KEY for stable sessions.')
    if production:
        app.config.update(SESSION_COOKIE_SECURE=True, REMEMBER_COOKIE_SECURE=True, DEBUG=False)
        if len(app.config['SECRET_KEY'])<32: raise RuntimeError('SECRET_KEY must contain at least 32 random characters.')
        if not app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql'): raise RuntimeError('Production requires PostgreSQL.')
        if app.config['STORAGE_BACKEND']!='s3': raise RuntimeError('Production requires persistent S3-compatible storage.')
        if not all(app.config.get(k) for k in ('S3_BUCKET','S3_ACCESS_KEY_ID','S3_SECRET_ACCESS_KEY')): raise RuntimeError('Configure S3 credentials and bucket.')
        if not app.config['RATELIMIT_STORAGE_URI'].startswith(('redis://','rediss://')): raise RuntimeError('Production rate limiting requires shared Redis storage.')
        if not app.config['SITE_URL'].startswith('https://'): raise RuntimeError('SITE_URL must use HTTPS in production.')
    if app.config['TRUST_PROXY']: app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1,x_host=1)
    app.config.setdefault('UPLOAD_ROOT',str(Path(app.instance_path)/'uploads'))
    Path(app.instance_path).mkdir(exist_ok=True)
    db.init_app(app); migrate.init_app(app,db); csrf.init_app(app); login.init_app(app); limiter.init_app(app)
    login.login_view='admin.login_view'
    login.session_protection='strong'
    @login.user_loader
    def load_user(uid):
        try: return db.session.get(AdminUser,int(uid))
        except (TypeError,ValueError): return None
    @login.unauthorized_handler
    def unauthorized():
        if request.path.startswith('/api/'): return jsonify(error={'code':401,'message':'Authentication required.'}),401
        from flask import redirect, url_for
        return redirect(url_for('admin.login_view'))
    from routes.main import bp as main
    from routes.projects import bp as projects
    from routes.contact import bp as contact
    from routes.admin import bp as admin
    app.register_blueprint(main); app.register_blueprint(projects); app.register_blueprint(contact); app.register_blueprint(admin)
    @app.context_processor
    def globals_():
        from urllib.parse import urlencode
        def page_url(page):
            args=request.args.to_dict(); args['page']=page
            return request.path+'?'+urlencode(args)
        return dict(site=profile(),canonical=app.config['SITE_URL']+request.path,page_url=page_url)
    @app.template_filter('date')
    def format_date(value): return value.strftime('%d %b %Y') if value else ''
    @app.after_request
    def security(response):
        from flask import g
        if response.status_code>=400:
            from storage import delete_key
            for key in getattr(g,'uploaded_keys',[]):
                try: delete_key(key)
                except Exception: app.logger.exception('Could not clean up failed upload %s',key)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='SAMEORIGIN'
        response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
        response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https: data: blob:; font-src 'self'; connect-src 'self'; frame-src 'self' https:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
        if production: response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
        if request.path.startswith(('/admin','/api/admin','/api/auth','/media','/resume/download')):
            response.headers['Cache-Control']='no-store'
            response.headers['X-Robots-Tag']='noindex, nofollow'
        return response
    def error_response(message,code):
        if request.path.startswith('/api/'): return jsonify(error={'code':code,'message':message}),code
        return render_template('error.html',title=str(code),code=code,message=message),code
    @app.errorhandler(ValidationError)
    def validation(e):
        db.session.rollback(); return error_response(str(e),422)
    @app.errorhandler(CSRFError)
    def csrf_error(e): return error_response('Your security token is missing or expired. Reload the page and try again.',400)
    @app.errorhandler(IntegrityError)
    def conflict(e):
        db.session.rollback(); return error_response('A unique value is already in use, or this record is still referenced.',409)
    @app.errorhandler(HTTPException)
    def http_error(e): return error_response(e.description,e.code)
    @app.errorhandler(Exception)
    def unexpected(e):
        db.session.rollback(); app.logger.exception('Unhandled request error')
        return error_response('Something went wrong. Please try again later.',500)
    @app.get('/healthz')
    def health():
        try: db.session.execute(text('SELECT 1')); return jsonify(status='ok')
        except SQLAlchemyError:
            db.session.rollback(); return jsonify(status='unhealthy'),503
    from seed import seed_content
    @app.cli.command('seed-content')
    def seed_command():
        """Insert only missing starter profile, skills, education and categories."""
        seed_content(); click.echo('Starter content initialized; no invented projects or achievements added.')
    @app.cli.command('create-admin')
    @click.option('--email','address',prompt=True)
    @click.password_option(confirmation_prompt=True)
    def create_admin(address,password):
        """Create an admin interactively. No public registration route exists."""
        address=email(address).lower()
        if len(password)<14: raise click.ClickException('Use a unique password of at least 14 characters.')
        if db.session.scalar(db.select(AdminUser).where(AdminUser.email==address)): raise click.ClickException('Admin already exists.')
        user=AdminUser(email=address); user.set_password(password); db.session.add(user); db.session.commit(); click.echo('Admin created.')
    @app.cli.command('reset-admin-password')
    @click.option('--email','address',prompt=True)
    @click.password_option(confirmation_prompt=True)
    def reset_admin(address,password):
        user=db.session.scalar(db.select(AdminUser).where(AdminUser.email==email(address).lower()))
        if not user or len(password)<14: raise click.ClickException('Admin missing or password too short (14 minimum).')
        user.set_password(password); db.session.commit(); click.echo('Password changed. Revoke existing sessions by rotating SECRET_KEY if needed.')
    @app.cli.command('cleanup-assets')
    @click.option('--apply',is_flag=True,help='Actually delete unreferenced assets older than 24 hours.')
    def cleanup_assets(apply):
        from datetime import datetime,timedelta,timezone
        from models import Asset,Project,ProjectImage,Profile,BlogPost
        from storage import remove_blob
        used=set()
        for model,fields in ((Project,['thumbnail_id']),(ProjectImage,['asset_id']),(Profile,['photo_id','resume_id']),(BlogPost,['thumbnail_id'])):
            for field in fields: used.update(v for v in db.session.scalars(db.select(getattr(model,field))) if v)
        for asset in db.session.scalars(db.select(Asset).where(Asset.created_at<datetime.now(timezone.utc)-timedelta(days=1))):
            if asset.id not in used:
                click.echo(('Deleting ' if apply else 'Unreferenced: ')+asset.key)
                if apply: remove_blob(asset); db.session.delete(asset)
        if apply: db.session.commit()
    return app
