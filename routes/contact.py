from flask import Blueprint, jsonify, redirect, url_for, flash, request
from extensions import db, limiter
from models import ContactMessage
from services import payload, text, email
bp=Blueprint('contact_api',__name__)

@bp.post('/api/contact')
@limiter.limit('5 per hour; 2 per minute')
def submit():
    data=payload()
    # Bots receive the same generic response but create no record.
    if text(data,'website',500): return jsonify(message='Thank you. Your message has been received.'),201
    m=ContactMessage(name=text(data,'name',120,True),email=email(text(data,'email',254,True)),subject=text(data,'subject',180,True),message=text(data,'message',5000,True))
    db.session.add(m); db.session.commit()
    if request.is_json or request.accept_mimetypes.best=='application/json': return jsonify(message='Thank you. Your message has been received.'),201
    flash('Thank you. Your message has been received.','success'); return redirect(url_for('main.contact'))
