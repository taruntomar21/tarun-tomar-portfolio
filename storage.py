from io import BytesIO
from pathlib import Path
from uuid import uuid4
import warnings
import boto3
from botocore.config import Config
from PIL import Image, ImageOps
from pypdf import PdfReader
from flask import current_app, g, has_request_context
from extensions import db
from models import Asset
from services import ValidationError

Image.MAX_IMAGE_PIXELS=20_000_000

def s3():
    c=current_app.config
    return boto3.client('s3', region_name=c['S3_REGION'], endpoint_url=c['S3_ENDPOINT_URL'], aws_access_key_id=c['S3_ACCESS_KEY_ID'], aws_secret_access_key=c['S3_SECRET_ACCESS_KEY'], config=Config(signature_version='s3v4'))

def save_upload(upload, purpose='image'):
    if not upload or not upload.filename: return None
    raw=upload.read(10*1024*1024+1)
    if len(raw)>10*1024*1024: raise ValidationError('Each upload must be 10 MB or smaller.')
    if purpose=='resume':
        if not upload.filename.lower().endswith('.pdf') or not raw.startswith(b'%PDF-'): raise ValidationError('Upload a valid PDF resume.')
        try:
            pdf=PdfReader(BytesIO(raw),strict=True)
            if pdf.is_encrypted or not len(pdf.pages): raise ValueError()
            root=pdf.trailer['/Root']
            if any(k in root for k in ('/OpenAction','/AA')) or '/JavaScript' in str(root.get('/Names','')): raise ValueError()
            for page in pdf.pages:
                if '/AA' in page: raise ValueError()
        except Exception: raise ValidationError('PDF must be readable, unencrypted, and free of active document actions.')
        extension='pdf'; mime='application/pdf'
    else:
        if Path(upload.filename).suffix.lower() not in ('.jpg','.jpeg','.png','.webp'): raise ValidationError('Use JPG, PNG, or WebP images.')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                im=Image.open(BytesIO(raw)); im.verify()
                im=ImageOps.exif_transpose(Image.open(BytesIO(raw))).convert('RGB')
                im.thumbnail((1800,1800))
                out=BytesIO(); im.save(out,'WEBP',quality=85); raw=out.getvalue()
        except Exception: raise ValidationError('Image is invalid or exceeds the safe pixel limit.')
        extension='webp'; mime='image/webp'
    key=f'portfolio/{uuid4().hex}.{extension}'
    if current_app.config['STORAGE_BACKEND']=='s3':
        s3().put_object(Bucket=current_app.config['S3_BUCKET'],Key=key,Body=raw,ContentType=mime)
    else:
        path=Path(current_app.config['UPLOAD_ROOT'])/key
        path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
    if has_request_context():
        if not hasattr(g,'uploaded_keys'): g.uploaded_keys=[]
        g.uploaded_keys.append(key)
    asset=Asset(key=key,filename=f'{purpose}.{extension}',mimetype=mime,size=len(raw),purpose=purpose)
    db.session.add(asset); db.session.flush()
    return asset

def delete_key(key):
    if current_app.config['STORAGE_BACKEND']=='s3': s3().delete_object(Bucket=current_app.config['S3_BUCKET'],Key=key)
    else: (Path(current_app.config['UPLOAD_ROOT'])/key).unlink(missing_ok=True)

def remove_blob(asset):
    delete_key(asset.key)
