"""Cek: peringkat & skor model.json = rumus Bab III dihitung langsung dari data_careerai/bobot_skill_karier.csv.
Jalankan dari folder backend: python tools/cek_skor.py"""
import os; os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys,json,csv,random
sys.path.insert(0,'.')
from career_model.scoring import recommend
m=json.load(open('model.json'))
b=list(csv.DictReader(open('data_careerai/bobot_skill_karier.csv')))
W={}
for r in b: W.setdefault(r['karier'],{})[r['skill']]=float(r['w'])
idmap={s['name']:s['id'] for s in m['skills']}
soft={s['name_en'] for s in m['soft_skills']}
kat={r['karier']:set(r['area_minat'].split(';')) for r in csv.DictReader(open('data_careerai/katalog_karier.csv'))}
SL={'advanced':1,'intermediate':.67,'beginner':.33}
random.seed(1); names=list(idmap)
for t in range(500):
    lv={n:random.choice(list(SL)) for n in random.sample(names,random.randint(0,30))}
    prof={'skills':{idmap[n]:l for n,l in lv.items() if n not in soft},'soft_skills':{idmap[n]:l for n,l in lv.items() if n in soft},
          'interests':random.sample([i['id'] for i in m['interests']],random.randint(0,2))}
    res=recommend(prof,m)['all']
    ints={i['name_en'] for i in m['interests'] if i['id'] in prof['interests']}
    exp=sorted((-(100*(.5*K+.5*M)),-K,c) for c,ws in W.items() for K in [sum(w*SL.get(lv.get(s),0) for s,w in ws.items())/sum(ws.values())] for M in [1.0 if ints&kat[c] else 0.0])
    assert [e[2] for e in exp]==[r['name_en'] for r in res], t
    assert all(abs(-e[0]-r['fit'])<0.006 for e,r in zip(exp,res))
print('500 profil acak: urutan & skor identik dengan rumus bobot_skill_karier.csv')
