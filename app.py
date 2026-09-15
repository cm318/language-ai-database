import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st

BASE=Path(__file__).parent; DB=BASE/'data'/'language_ai_cases.db'
st.set_page_config(page_title='“语言+人工智能”案例数据库｜专家验收版',page_icon='◈',layout='wide',initial_sidebar_state='collapsed')
@st.cache_data
def load(t):
    with sqlite3.connect(DB) as con: return pd.read_sql_query(f'select * from {t}',con)
T={t:load(t) for t in ['universities','programs','objectives','courses','faculty','practice','evaluation','organizations','sources']}
U=T['universities']; P=T['programs']
CSS='''<style>
.stApp{background:#f5f7fb}.block-container{padding-top:1.2rem;max-width:1450px}
.hero{padding:36px 42px;border-radius:20px;background:linear-gradient(120deg,#0d2f57,#174d7b 55%,#2574a9);color:white;box-shadow:0 14px 35px #17324d22}.hero h1{font-size:36px;margin:0 0 10px}.hero p{opacity:.9;font-size:16px;max-width:980px;line-height:1.8}.pill{display:inline-block;border:1px solid #ffffff55;background:#ffffff18;padding:5px 10px;border-radius:99px;margin-right:7px;font-size:12px}.sec{font-size:24px;font-weight:800;color:#16324f;margin:28px 0 10px}.sub{color:#667085}.card{background:white;border:1px solid #e4e9f0;border-radius:16px;padding:18px;box-shadow:0 4px 15px #2030400b;height:100%}.num{font-size:30px;font-weight:800;color:#164f7c}.cap{font-size:12px;color:#718096}.feature{font-weight:700;color:#173b5e;font-size:17px}.tag{display:inline-block;background:#eaf2f8;color:#18537d;border-radius:99px;padding:4px 9px;margin:2px;font-size:12px}
div[data-testid="stMetric"]{background:white;border:1px solid #e4e9f0;padding:14px;border-radius:14px} .stButton>button{border-radius:10px;font-weight:650}
</style>'''; st.markdown(CSS,unsafe_allow_html=True)

def uid_name(uid):
    r=U[U.university_id==uid].iloc[0]; return r.university_name_cn

def detail(uid):
    u=U[U.university_id==uid].iloc[0]; st.button('← 返回数据库首页',on_click=lambda:st.session_state.update(page='home'))
    st.markdown(f"<div class='hero'><span class='pill'>{u.country}</span><span class='pill'>{u.region}</span><h1>{u.university_name_cn}</h1><p>{u.university_name_en}｜{u.university_type}</p></div>",unsafe_allow_html=True)
    ps=P[P.university_id==uid]
    names=['学校概览','培养目标','课程体系','师资配置','实践环节','评价机制','组织架构','数据来源']; tabs=st.tabs(names)
    with tabs[0]:
        st.write(f"**数据状态：** {u.data_status}　 **数据完整度：** {u.completeness}　 **采集年份：** {u.collection_year}")
        for _,p in ps.iterrows():
            st.markdown(f"### {p.program_name_cn}"); st.caption(f"{p.level}｜{p.degree}｜{p.language_of_instruction}"); st.write(p.positioning); st.write('**招生/基础要求：**',p.admission_summary)
    with tabs[1]:
        for _,p in ps.iterrows():
            oo=T['objectives'][T['objectives'].program_id==p.program_id]
            if len(oo): st.markdown(f"#### {p.program_name_cn}")
            for _,o in oo.iterrows(): st.markdown(f"**{o.dimension}**　{o.description}")
    with tabs[2]:
        x=T['courses'][T['courses'].university_id==uid][['course_name','module','language_tag','practice_tag']]; st.dataframe(x,use_container_width=True,hide_index=True)
    with tabs[3]:
        x=T['faculty'][T['faculty'].university_id==uid][['name','organization','title','research_direction']]; st.dataframe(x,use_container_width=True,hide_index=True)
    with tabs[4]:
        for _,x in T['practice'][T['practice'].university_id==uid].iterrows(): st.markdown(f"**{x['name']}｜{x.practice_type}**  \n{x.content}  \n*时长：{x.duration}；评价：{x.assessment}*")
    with tabs[5]:
        es=T['evaluation'][T['evaluation'].university_id==uid]
        if es.empty: st.info('当前案例材料未提供可统一结构化的评价机制信息，数据库不作推断补录。')
        for _,x in es.iterrows(): st.markdown(f"**{x.evaluation_type}**  \n{x.method}。{x.criteria}  \n成果：{x.output}")
    with tabs[6]:
        for _,x in T['organizations'][T['organizations'].university_id==uid].iterrows(): st.markdown(f"**{x['name']}**　`{x.org_type}`  \n{x.description}")
    with tabs[7]:
        for _,x in T['sources'][T['sources'].university_id==uid].iterrows(): st.markdown(f"**{x.source_name}**  \n{x.note}  \n采集日期：{x.access_date}｜对应维度：{x.mapped_dimensions}")

def home():
    st.markdown("""<div class='hero'><span class='pill'>国家语委项目成果</span><span class='pill'>山东大学</span><span class='pill'>专家验收版</span><h1>世界一流大学“语言+人工智能”<br>复合型人才培养模式案例数据库</h1><p>围绕培养目标、课程体系、师资配置、实践环节、评价机制、组织架构六个维度，对国内外代表性高校案例进行结构化整理，实现高校检索、跨校比较、数据驾驶舱与来源追溯。</p></div>""",unsafe_allow_html=True)
    st.markdown("<div class='sec'>数据库成果概览</div>",unsafe_allow_html=True)
    a,b,c,d,e=st.columns(5)
    for col,label,val in [(a,'已结构化高校',len(U)),(b,'培养项目/路径',len(P)),(c,'课程/研究主题',len(T['courses'])),(d,'师资记录',len(T['faculty'])),(e,'组织/科研平台',len(T['organizations']))]: col.metric(label,val)
    st.caption('注：当前专家验收版先纳入4所已结构化示范高校；后续40余所案例可按同一数据标准持续追加，页面统计自动更新。')
    st.markdown("<div class='sec'>高校检索与比较</div><div class='sub'>无需了解数据库字段。先选择高校，后续项目和数据对象将自动联动。</div>",unsafe_allow_html=True)
    mode=st.radio('功能', ['高校检索','高校比较'],horizontal=True,label_visibility='collapsed')
    if mode=='高校检索':
        c1,c2,c3=st.columns([1.2,1,1])
        with c1: un=st.selectbox('① 选择高校',U.university_name_cn.tolist())
        uid=U[U.university_name_cn==un].university_id.iloc[0]; ps=P[P.university_id==uid]
        with c2: prog=st.selectbox('② 培养项目/路径',['全部']+ps.program_name_cn.tolist())
        with c3: module=st.selectbox('③ 查看模块',['学校概览','培养目标','课程体系','师资配置','实践环节','评价机制','组织架构','数据来源'])
        r=U[U.university_id==uid].iloc[0]
        st.markdown(f"<div class='card'><div class='feature'>{r.university_name_cn} · {prog}</div><p class='sub'>{r.country}｜{r.region}｜{r.university_type}</p><p>已收录培养项目/路径 {len(ps)} 个、课程/研究主题 {len(T['courses'][T['courses'].university_id==uid])} 条、师资 {len(T['faculty'][T['faculty'].university_id==uid])} 条、组织平台 {len(T['organizations'][T['organizations'].university_id==uid])} 个。</p></div>",unsafe_allow_html=True)
        if st.button('打开高校二级详情页 →',type='primary',use_container_width=True): st.session_state.page='detail';st.session_state.uid=uid;st.rerun()
    else:
        opts=U.university_name_cn.tolist(); chosen=st.multiselect('选择2—4所高校进行比较',opts,default=opts[:min(4,len(opts))],max_selections=4)
        if chosen:
            rows=[]
            for n in chosen:
                uid=U[U.university_name_cn==n].university_id.iloc[0]
                rows.append({'高校':n,'国家/地区':U[U.university_id==uid].iloc[0].country,'培养项目/路径':len(P[P.university_id==uid]),'课程/研究主题':len(T['courses'][T['courses'].university_id==uid]),'师资':len(T['faculty'][T['faculty'].university_id==uid]),'实践':len(T['practice'][T['practice'].university_id==uid]),'评价':len(T['evaluation'][T['evaluation'].university_id==uid]),'组织平台':len(T['organizations'][T['organizations'].university_id==uid])})
            st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
            st.caption('数量比较反映当前案例材料的结构化记录量，不代表高校办学水平或培养质量排名。')
    st.markdown("<div class='sec'>六维分析框架</div>",unsafe_allow_html=True)
    dims=[('01','培养目标','人才定位、知识—能力—素养'),('02','课程体系','语言、AI与交叉课程组织'),('03','师资配置','跨院系、跨学科师资结构'),('04','实践环节','科研、项目、实习与产学合作'),('05','评价机制','课程、项目、论文与成果评价'),('06','组织架构','研究中心、实验室与协同平台')]
    cols=st.columns(3)
    for i,(no,t,desc) in enumerate(dims): cols[i%3].markdown(f"<div class='card'><span class='cap'>{no}</span><div class='feature'>{t}</div><p class='sub'>{desc}</p></div>",unsafe_allow_html=True)
    st.markdown("<div class='sec'>数据驾驶舱</div>",unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1:
        x=U.groupby('region').size().reset_index(name='高校数').set_index('region'); st.markdown('#### 区域分布'); st.bar_chart(x)
    with c2:
        x=P.groupby('level').size().reset_index(name='项目数').set_index('level'); st.markdown('#### 培养层次/路径分布'); st.bar_chart(x)
    st.markdown('#### 高校结构化数据覆盖')
    rows=[]
    for _,u in U.iterrows():
        uid=u.university_id; rows.append({'高校':u.university_name_cn,'项目':len(P[P.university_id==uid]),'课程':len(T['courses'][T['courses'].university_id==uid]),'师资':len(T['faculty'][T['faculty'].university_id==uid]),'实践':len(T['practice'][T['practice'].university_id==uid]),'评价':len(T['evaluation'][T['evaluation'].university_id==uid]),'组织':len(T['organizations'][T['organizations'].university_id==uid])})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    st.markdown("<div class='sec'>典型案例入口</div>",unsafe_allow_html=True)
    cols=st.columns(4)
    for i,(_,u) in enumerate(U.iterrows()):
        with cols[i%4]:
            st.markdown(f"<div class='card'><div class='feature'>{u.university_name_cn}</div><p class='sub'>{u.university_name_en}<br>{u.country} · {u.region}</p></div>",unsafe_allow_html=True)
            if st.button('查看详情',key='go'+u.university_id,use_container_width=True): st.session_state.page='detail';st.session_state.uid=u.university_id;st.rerun()
    st.divider(); st.caption('数据说明｜本系统为项目成果的结构化展示与检索平台。数据来源于项目组整理的高校案例材料；对原材料未明确提供的信息不作主观补录。')

if 'page' not in st.session_state: st.session_state.page='home'
if st.session_state.page=='detail': detail(st.session_state.get('uid','U001'))
else: home()
