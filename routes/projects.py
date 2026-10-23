from flask import Blueprint, request, jsonify, abort
from sqlalchemy import select
from extensions import db
from models import Project, Skill, Education, Experience, Achievement, ProjectCategory, BlogPost
from services import listing, project_query, serialize_project, profile
bp=Blueprint('projects_api',__name__,url_prefix='/api')

@bp.get('/projects')
def projects():
    page=listing(request.args)
    return jsonify(data=[serialize_project(p) for p in page.items],pagination={'page':page.page,'pages':page.pages,'total':page.total,'per_page':page.per_page})

@bp.get('/projects/<slug>')
def detail(slug):
    p=db.session.scalar(project_query().where(Project.slug==slug))
    if not p: abort(404)
    return jsonify(data=serialize_project(p,True))

@bp.get('/profile')
def public_profile():
    p=profile()
    return jsonify(data={k:getattr(p,k) for k in ('name','headline','introduction','about','goals','email','contact_info','github_url','linkedin_url')})

@bp.get('/skills')
def public_skills():
    return jsonify(data=[{k:getattr(s,k) for k in ('id','name','category','description','level','display_order')} for s in db.session.scalars(select(Skill).order_by(Skill.category,Skill.display_order))])

@bp.get('/home')
def home():
    from flask import url_for
    p=profile()
    return jsonify(data={'profile':{k:getattr(p,k) for k in ('name','headline','introduction','about','goals','github_url','linkedin_url')},'featured_projects':[serialize_project(v) for v in db.session.scalars(project_query().where(Project.featured.is_(True)).order_by(Project.display_order).limit(3))]})

@bp.get('/categories')
def categories(): return jsonify(data=[{'id':c.id,'name':c.name} for c in db.session.scalars(select(ProjectCategory).order_by(ProjectCategory.display_order))])

@bp.get('/blog')
def posts():
    from services import integer
    query=select(BlogPost).where(BlogPost.status=='published')
    if request.args.get('category'): query=query.where(BlogPost.category==request.args['category'][:100])
    q=request.args.get('q','').strip()[:200]
    if q: query=query.where(BlogPost.title.icontains(q,autoescape=True))
    page=db.paginate(query.order_by(BlogPost.published_at.desc(),BlogPost.id.desc()),page=integer(request.args.get('page',1),'page',1),per_page=9,error_out=False)
    return jsonify(data=[{'id':p.id,'title':p.title,'slug':p.slug,'summary':p.summary,'category':p.category,'tags':p.tags,'published_at':p.published_at.isoformat() if p.published_at else None} for p in page.items],pagination={'page':page.page,'pages':page.pages,'total':page.total})

@bp.get('/blog/<slug>')
def post(slug):
    p=db.session.scalar(select(BlogPost).where(BlogPost.status=='published',BlogPost.slug==slug))
    if not p: abort(404)
    return jsonify(data={'title':p.title,'slug':p.slug,'summary':p.summary,'body':p.body,'category':p.category,'tags':p.tags,'published_at':p.published_at.isoformat() if p.published_at else None})
