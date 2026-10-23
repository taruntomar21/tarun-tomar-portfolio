from datetime import datetime, timezone
from pathlib import Path
from flask import Blueprint, render_template, request, abort, redirect, url_for, current_app, send_from_directory, Response
from flask_login import current_user
from sqlalchemy import or_, select
from extensions import db
from models import *
from services import listing, project_query, profile, integer
from storage import s3
bp=Blueprint('main',__name__)

def entries(model): return db.session.scalars(select(model).order_by(model.display_order,model.id)).all()

@bp.get('/')
def index():
    featured=db.session.scalars(project_query().where(Project.featured.is_(True)).order_by(Project.display_order,Project.created_at.desc()).limit(3)).all()
    return render_template('index.html',title='Data, with purpose',featured=featured,skills=entries(Skill),experience=entries(Experience),achievements=entries(Achievement),project_count=db.session.query(Project).filter_by(status='published').count())

@bp.get('/about')
def about(): return render_template('about.html',title='About',education=entries(Education),achievements=entries(Achievement))

@bp.get('/projects')
def projects():
    return render_template('projects.html',title='Projects',pagination=listing(request.args),categories=entries(ProjectCategory),technologies=db.session.scalars(select(Technology).where(Technology.id.in_(select(project_technology.c.technology_id).join(Project,Project.id==project_technology.c.project_id).where(Project.status=='published'))).order_by(Technology.name)).all())

@bp.get('/projects/<slug>')
def project_detail(slug):
    p=db.session.scalar(project_query().where(Project.slug==slug))
    if not p: abort(404)
    return render_template('project_detail.html',title=p.title,meta_description=p.short_description,project=p)

@bp.get('/skills')
def skills(): return render_template('skills.html',title='Skills',skills=entries(Skill))

@bp.get('/experience')
def experience(): return render_template('experience.html',title='Experience',experience=entries(Experience),achievements=entries(Achievement),education=entries(Education))

@bp.get('/resume')
def resume(): return render_template('resume.html',title='Resume')

@bp.get('/resume/download')
def resume_download():
    p=profile()
    if not p.resume_id: abort(404,description='A resume has not been uploaded yet.')
    return redirect(url_for('main.media',asset_id=p.resume_id,download=1))

@bp.get('/contact')
def contact(): return render_template('contact.html',title='Contact')

@bp.get('/blog')
def blog():
    query=select(BlogPost).where(BlogPost.status=='published')
    q=request.args.get('q','').strip()[:200]; category=request.args.get('category','')[:100]
    if q:
        query=query.where(or_(BlogPost.title.icontains(q,autoescape=True),BlogPost.summary.icontains(q,autoescape=True)))
    if category: query=query.where(BlogPost.category==category)
    pagination=db.paginate(query.order_by(BlogPost.published_at.desc(),BlogPost.id.desc()),page=integer(request.args.get('page',1),'page',1,100000),per_page=9,error_out=False)
    categories=db.session.scalars(select(BlogPost.category).where(BlogPost.status=='published',BlogPost.category!='').distinct().order_by(BlogPost.category)).all()
    return render_template('blog.html',title='Notes & ideas',pagination=pagination,categories=categories)

@bp.get('/blog/<slug>')
def blog_detail(slug):
    post=db.session.scalar(select(BlogPost).where(BlogPost.slug==slug,BlogPost.status=='published'))
    if not post: abort(404)
    return render_template('blog_detail.html',title=post.title,meta_description=post.summary,post=post)

@bp.get('/media/<int:asset_id>')
def media(asset_id):
    asset=db.session.get(Asset,asset_id)
    if not asset: abort(404)
    # A guessed media ID must not reveal draft-project or draft-blog attachments.
    public=bool(db.session.scalar(select(Project.id).where(Project.status=='published',Project.thumbnail_id==asset_id).limit(1)) or db.session.scalar(select(ProjectImage.id).join(Project).where(Project.status=='published',ProjectImage.asset_id==asset_id).limit(1)) or db.session.scalar(select(BlogPost.id).where(BlogPost.status=='published',BlogPost.thumbnail_id==asset_id).limit(1)) or db.session.scalar(select(Profile.id).where(or_(Profile.photo_id==asset_id,Profile.resume_id==asset_id)).limit(1)))
    if not public and not current_user.is_authenticated: abort(404)
    download=asset.purpose=='resume' or request.args.get('download')=='1'
    if current_app.config['STORAGE_BACKEND']=='s3':
        params={'Bucket':current_app.config['S3_BUCKET'],'Key':asset.key,'ResponseContentType':asset.mimetype,'ResponseContentDisposition':('attachment' if download else 'inline')+'; filename="'+asset.filename+'"'}
        return redirect(s3().generate_presigned_url('get_object',Params=params,ExpiresIn=300))
    return send_from_directory(current_app.config['UPLOAD_ROOT'],asset.key,mimetype=asset.mimetype,as_attachment=download,download_name=asset.filename)

@bp.get('/robots.txt')
def robots():
    return Response('User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api/\nDisallow: /media/\nSitemap: '+current_app.config['SITE_URL']+'/sitemap.xml\n',mimetype='text/plain')

@bp.get('/sitemap.xml')
def sitemap():
    from xml.sax.saxutils import escape
    base=current_app.config['SITE_URL']
    paths=['/','/about','/projects','/skills','/experience','/resume','/blog','/contact']
    paths += ['/projects/'+s for s in db.session.scalars(select(Project.slug).where(Project.status=='published'))]
    paths += ['/blog/'+s for s in db.session.scalars(select(BlogPost.slug).where(BlogPost.status=='published'))]
    xml='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+escape(base+p)+'</loc></url>' for p in paths)+'</urlset>'
    return Response(xml,mimetype='application/xml')
