from extensions import db
from models import Profile, Skill, Education, ProjectCategory

def seed_content():
    if not db.session.get(Profile,1): db.session.add(Profile(id=1))
    if not db.session.scalar(db.select(Education.id).limit(1)):
        db.session.add(Education(title='B.Tech Biotechnology',organization='NIT Jalandhar',period='Dates to be added',description='Biotechnology student pursuing interests in data and technology.'))
    categories=['Data Analytics','Data Science','Machine Learning','Deep Learning','Data Engineering','Dashboard Development','SQL Projects','Web Applications','Other']
    for i,name in enumerate(categories):
        if not db.session.scalar(db.select(ProjectCategory).where(ProjectCategory.name==name)): db.session.add(ProjectCategory(name=name,display_order=i))
    if not db.session.scalar(db.select(Skill.id).limit(1)):
        groups={'Programming Languages':['Python','SQL'],'Data Analysis':['Pandas','NumPy','Excel','Exploratory data analysis'],'Statistics':['Statistics'],'Data Visualization':['Tableau','Matplotlib','Seaborn','Plotly'],'Machine Learning':['scikit-learn','Model evaluation','Feature engineering','Supervised learning'],'Deep Learning':['TensorFlow','Keras','CNNs','Transfer learning'],'Data Engineering':['ETL','Data cleaning','Data warehousing','Azure Data Factory'],'Databases':['MySQL','PostgreSQL','SQL databases'],'Tools and Platforms':['Streamlit','Flask','Git','GitHub','Jupyter Notebook','Google Colab']}
        for category,names in groups.items():
            for i,name in enumerate(names): db.session.add(Skill(name=name,category=category,level='Learning' if name=='Azure Data Factory' else '',description='',display_order=i))
    db.session.commit()
