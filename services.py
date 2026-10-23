import re
from urllib.parse import urlsplit
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload, joinedload
from email_validator import validate_email, EmailNotValidError
from flask import abort, request, url_for
from extensions import db
from models import Project, ProjectCategory, Technology, Profile

class ValidationError(ValueError): pass

def text(data, name, maximum=10000, required=False):
    value = data.get(name, '')
    if not isinstance(value, str): raise ValidationError(f'{name}: use text.')
    value = value.strip()
    if required and not value: raise ValidationError(f'{name} is required.')
    if len(value) > maximum: raise ValidationError(f'{name}: maximum {maximum} characters.')
    return value

def integer(value, label='value', minimum=-100000, maximum=100000):
    try:
        if isinstance(value, bool) or isinstance(value, float): raise ValueError()
        number = int(value)
    except (TypeError, ValueError): raise ValidationError(f'{label} must be an integer.')
    if not minimum <= number <= maximum: raise ValidationError(f'{label} is out of range.')
    return number

def boolean(value):
    if value in (True, 'true', 'on', '1', 1): return True
    if value in (False, 'false', '0', 0, '', None): return False
    raise ValidationError('Use a true or false value.')

def email(value, required=True):
    if not value and not required: return ''
    try: return validate_email(value, check_deliverability=False).normalized
    except EmailNotValidError: raise ValidationError('Enter a valid email address.')

def safe_url(value):
    if not value: return ''
    if len(value)>2048 or any(c.isspace() for c in value): raise ValidationError('Invalid URL.')
    try:
        p=urlsplit(value)
        if p.scheme not in ('https','http') or not p.hostname or p.username or p.password: raise ValueError()
        _=p.port
    except ValueError: raise ValidationError('Links must be full http:// or https:// URLs without credentials.')
    return value

def slug(value):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value or '') or len(value)>200:
        raise ValidationError('Slug must use lowercase letters, numbers, and single hyphens.')
    return value

def profile():
    value=db.session.get(Profile, 1)
    if value: return value
    return Profile(**{column.name:column.default.arg for column in Profile.__table__.columns if column.default is not None and column.default.is_scalar})

def project_query():
    return select(Project).where(Project.status=='published').options(joinedload(Project.category), joinedload(Project.thumbnail), selectinload(Project.technologies), selectinload(Project.images))

def listing(args):
    query=project_query()
    q=str(args.get('q','')).strip()[:200]
    if q:
        query=query.where(or_(Project.title.icontains(q, autoescape=True), Project.short_description.icontains(q, autoescape=True), Project.description.icontains(q, autoescape=True)))
    if args.get('category'): query=query.where(Project.category_id==integer(args['category'],'category',1))
    if args.get('technology'): query=query.where(Project.technologies.any(Technology.name==str(args['technology'])[:80]))
    sort=args.get('sort','newest')
    if sort not in ('newest','oldest','featured'): raise ValidationError('Unknown sort order.')
    ordering={'newest':(Project.created_at.desc(),),'oldest':(Project.created_at.asc(),),'featured':(Project.featured.desc(),Project.display_order.asc(),Project.created_at.desc())}
    query=query.order_by(*ordering[sort],Project.id.desc())
    page=integer(args.get('page',1),'page',1,100000)
    return db.paginate(query,page=page,per_page=9,error_out=False)

def serialize_project(p, detail=False):
    data=dict(id=p.id,title=p.title,slug=p.slug,short_description=p.short_description,category={'id':p.category.id,'name':p.category.name} if p.category else None,technologies=[t.name for t in p.technologies],thumbnail_url=url_for('main.media',asset_id=p.thumbnail_id) if p.thumbnail_id else None,featured=p.featured,display_order=p.display_order,status=p.status,github_url=p.github_url,demo_url=p.demo_url,created_at=p.created_at.isoformat(),updated_at=p.updated_at.isoformat(),url=url_for('main.project_detail',slug=p.slug))
    if detail:
        data.update({k:getattr(p,k) for k in ('description','problem','objectives','methodology','results','dataset_url','documentation_url')})
        data['images']=[{'id':i.id,'url':url_for('main.media',asset_id=i.asset_id),'alt':i.alt,'display_order':i.display_order} for i in p.images]
    return data

def payload():
    if request.is_json:
        value=request.get_json()
        if not isinstance(value,dict): raise ValidationError('A JSON object is required.')
        return value
    return request.form.to_dict()
