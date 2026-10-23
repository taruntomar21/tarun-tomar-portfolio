"""Rebuild exact-text social preview and favicon; no external image assets needed."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[1]
# DejaVu is available on most Linux systems; use fallback on other platforms.
def font(size,bold=False):
    try: return ImageFont.truetype('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf',size)
    except OSError: return ImageFont.load_default(size=size)
canvas=Image.new('RGB',(1200,630),'#101c20'); draw=ImageDraw.Draw(canvas)
draw.text((80,70),'TARUN TOMAR',fill='#71d8b5',font=font(24,True))
draw.text((75,180),'Finding meaning',fill='#e6eee9',font=font(72,True))
draw.text((75,275),'in the data.',fill='#71d8b5',font=font(72,True))
draw.text((80,425),'Biotechnology | Data Analytics | Machine Learning',fill='#a0b2ac',font=font(24))
draw.line((80,530,1120,530),fill='#38514e',width=2)
draw.text((80,558),'Curiosity meets data.',fill='#a0b2ac',font=font(20))
(root/'static/images').mkdir(parents=True,exist_ok=True)
canvas.save(root/'static/images/og-card.png',optimize=True)
icon=Image.new('RGB',(128,128),'#101c20'); d=ImageDraw.Draw(icon); d.text((35,9),'t',font=font(90,True),fill='#71d8b5'); d.ellipse((88,91,101,104),fill='#e6eee9')
icon.save(root/'static/favicon.ico',sizes=[(16,16),(32,32),(48,48),(64,64)])
