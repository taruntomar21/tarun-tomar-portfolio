from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

def now():
    return datetime.now(timezone.utc)

class Timestamp:
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=now, onupdate=now, nullable=False)

class AdminUser(UserMixin, Timestamp, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

project_technology = db.Table('project_technology',
    db.Column('project_id', db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), primary_key=True),
    db.Column('technology_id', db.Integer, db.ForeignKey('technology.id', ondelete='CASCADE'), primary_key=True))

class ProjectCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)

class Technology(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

class Asset(Timestamp, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), unique=True, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    mimetype = db.Column(db.String(80), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    purpose = db.Column(db.String(30), nullable=False)

class Project(Timestamp, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(200), unique=True, index=True, nullable=False)
    short_description = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, default='', nullable=False)
    problem = db.Column(db.Text, default='', nullable=False)
    objectives = db.Column(db.Text, default='', nullable=False)
    methodology = db.Column(db.Text, default='', nullable=False)
    results = db.Column(db.Text, default='', nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('project_category.id', ondelete='SET NULL'))
    category = db.relationship(ProjectCategory)
    thumbnail_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    thumbnail = db.relationship(Asset)
    github_url = db.Column(db.String(2048), default='', nullable=False)
    demo_url = db.Column(db.String(2048), default='', nullable=False)
    dataset_url = db.Column(db.String(2048), default='', nullable=False)
    documentation_url = db.Column(db.String(2048), default='', nullable=False)
    featured = db.Column(db.Boolean, default=False, nullable=False)
    is_in_progress = db.Column(db.Boolean,default=False,nullable=False)
    status = db.Column(db.String(20), default='draft', index=True, nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    technologies = db.relationship(Technology, secondary=project_technology, lazy='selectin')
    images = db.relationship('ProjectImage', cascade='all, delete-orphan', lazy='selectin', order_by='ProjectImage.display_order')
    __table_args__ = (db.CheckConstraint("status IN ('draft', 'published')", name='project_valid_status'),)

class ProjectImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    asset = db.relationship(Asset)
    alt = db.Column(db.String(255), default='', nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)

class Profile(Timestamp, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), default='Tarun Tomar', nullable=False)
    headline = db.Column(db.String(300), default='Data Analyst | Aspiring Data Scientist | Data Engineering Enthusiast', nullable=False)
    introduction = db.Column(db.Text, default='B.Tech Biotechnology student at NIT Jalandhar, exploring how data can turn complex questions into clear, useful insights.', nullable=False)
    about = db.Column(db.Text, default='My interests connect biotechnology, analytical thinking, and technology. I am developing my skills in data analysis, visualization, machine learning, and data-driven applications.', nullable=False)
    goals = db.Column(db.Text, default='Seeking opportunities to learn and contribute in Data Analytics, Data Science, Machine Learning, and Data Engineering.', nullable=False)
    email = db.Column(db.String(254), default='', nullable=False)
    contact_info = db.Column(db.Text, default='', nullable=False)
    github_url = db.Column(db.String(2048), default='', nullable=False)
    linkedin_url = db.Column(db.String(2048), default='', nullable=False)
    photo_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    resume_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    photo = db.relationship(Asset, foreign_keys=[photo_id])
    resume = db.relationship(Asset, foreign_keys=[resume_id])
    seo_description = db.Column(db.String(300), default='Tarun Tomar — biotechnology student at NIT Jalandhar exploring data analytics, machine learning, and data engineering.', nullable=False)

class Skill(Timestamp, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='', nullable=False)
    level = db.Column(db.String(100), default='', nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)

class Education(Timestamp, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    organization = db.Column(db.String(180), nullable=False)
    period = db.Column(db.String(100), default='', nullable=False)
    description = db.Column(db.Text, default='', nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)

class Experience(Timestamp, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    organization = db.Column(db.String(180), default='', nullable=False)
    period = db.Column(db.String(100), default='', nullable=False)
    description = db.Column(db.Text, default='', nullable=False)
    kind = db.Column(db.String(100), default='Practical experience', nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)

class Achievement(Timestamp, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    organization = db.Column(db.String(180), default='', nullable=False)
    period = db.Column(db.String(100), default='', nullable=False)
    description = db.Column(db.Text, default='', nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)

class BlogPost(Timestamp, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(200), unique=True, index=True, nullable=False)
    summary = db.Column(db.String(500), default='', nullable=False)
    body = db.Column(db.Text, default='', nullable=False)
    category = db.Column(db.String(100), default='', nullable=False)
    tags = db.Column(db.JSON, default=list, nullable=False)
    thumbnail_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    thumbnail = db.relationship(Asset)
    status = db.Column(db.String(20), default='draft', index=True, nullable=False)
    published_at = db.Column(db.DateTime(timezone=True))
    __table_args__ = (db.CheckConstraint("status IN ('draft', 'published')", name='blog_valid_status'),)

class ContactMessage(Timestamp, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    subject = db.Column(db.String(180), nullable=False)
    message = db.Column(db.Text, nullable=False)
    archived = db.Column(db.Boolean, default=False, nullable=False)
    read = db.Column(db.Boolean, default=False, nullable=False)
