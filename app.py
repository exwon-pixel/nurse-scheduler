"""
app.py
간호사 스케줄링 AI Agent (Final Ver.)
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from utils.data_loader import DataLoader
    from src.scheduler import NurseScheduler
    from src.validator import ScheduleValidator
    from src.visualizer import ScheduleVisualizer
except ImportError:
    try:
        from src.utils.data_loader import DataLoader
        from src.scheduler import NurseScheduler
        from src.validator import ScheduleValidator
        from src.visualizer import ScheduleVisualizer
    except ImportError:
        st.error("모듈 로딩 실패: src 폴더를 확인하세요.")
        st.stop()

st.set_page_config(page_title="AI Nurse Scheduler", layout="wide", page_icon="🏥")

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/en/thumb/f/f7/Yonsei_University_logo.svg/1200px-Yonsei_University_logo.svg.png", width=120)
    st.title("🏥 AI 스케줄러")
    menu = st.radio("메뉴", ["1. 데이터 업로드", "2. 스케줄 생성", "3. 결과 대시보드"])

if menu == "1. 데이터 업로드":
    st.title("📤 데이터 업로드")
    file = st.file_uploader("엑셀 파일 업로드", type=['xlsx'])
    if file:
        sheets = DataLoader.load_excel(file)
        if 'Nurse' in sheets or 'nurses' in sheets:
            st.session_state.sheets = sheets
            st.success("데이터 로드 완료")
            st.dataframe(list(sheets.values())[0].head())
        else:
            st.error("Nurse 시트가 없습니다.")

elif menu == "2. 스케줄 생성":
    st.title("⚙️ 스케줄 생성")
    if not st.session_state.get('sheets'):
        st.warning("데이터를 먼저 업로드하세요.")
        st.stop()
        
    c1, c2 = st.columns(2)
    with c1:
        s_str, e_str = DataLoader.get_date_range(st.session_state.sheets)
        s_date = st.date_input("시작일", datetime.strptime(s_str, "%Y-%m-%d"))
    with c2:
        e_date = st.date_input("종료일", datetime.strptime(e_str, "%Y-%m-%d"))
        
    max_time = st.slider("최적화 시간 (초)", 60, 600, 250)
    
    if st.button("🚀 AI 스케줄링 시작", type="primary"):
        with st.spinner("규정 준수 여부 및 인력 배치를 계산 중입니다..."):
            scheduler = NurseScheduler(
                st.session_state.sheets, 
                s_date.strftime("%Y-%m-%d"), 
                e_date.strftime("%Y-%m-%d")
            )
            result = scheduler.optimize(max_time_seconds=max_time)
            st.session_state.result = result
            st.success("✅ 스케줄 생성 완료!")

elif menu == "3. 결과 대시보드":
    st.title("📊 결과 대시보드")
    if not st.session_state.get('result'):
        st.info("스케줄을 먼저 생성해주세요.")
        st.stop()
        
    res = st.session_state.result
    validator = ScheduleValidator(res)
    val = validator.validate_all()
    viols = val['violations']
    
    # 목표치 설정
    total_nurses = res['total_nurses']
    if total_nurses < 10: target = {'D': 2, 'E': 2, 'N': 1}
    elif total_nurses < 15: target = {'D': 2, 'E': 2, 'N': 2}
    else: target = {'D': 3, 'E': 3, 'N': 2}
    
    # 부족 인원 계산
    shortage_list = []
    total_short = 0
    for d_idx, date_info in enumerate(res['dates']):
        cov = date_info['coverage']
        for shift in ['D', 'E', 'N']:
            if cov[shift] < target[shift]:
                missing = target[shift] - cov[shift]
                shortage_list.append({
                    "날짜": date_info['date'],
                    "근무조": shift,
                    "목표": target[shift],
                    "실제": cov[shift],
                    "부족": f"-{missing}명"
                })
                total_short += missing

    st.subheader("✅ 핵심 지표")
    c1, c2, c3, c4 = st.columns(4)
    
    total_viol = sum(len(viols[k]) for k in ['HC1', 'HC2', 'HC3', 'HC4', 'HC6'])
    c1.metric("규정 위반 (Hard)", f"{total_viol}건", delta="완벽 준수" if total_viol==0 else "조정 필요", delta_color="inverse")
    c2.metric("인력 부족 누적", f"{total_short}명분", delta="충원 필요" if total_short>0 else "충분", delta_color="inverse")
    
    dev = val['fairness']['work_days']['deviation']
    c3.metric("근무일수 편차", f"{dev}일", delta="양호" if dev<=3 else "보통", delta_color="inverse")
    
    v_hc3 = len(viols['HC3'])
    c4.metric("30시간 휴식 준수", "Pass" if v_hc3==0 else "Fail", delta_color="normal" if v_hc3==0 else "inverse")
    
    st.markdown("---")

    if shortage_list:
        st.error(f"🚨 **총 {len(shortage_list)}개 근무조에서 인력 부족이 발생했습니다.** (법적 규정 준수를 위해 배정을 제한함)")
        with st.expander("🔻 부족 상세 내역 (충원 근거 자료)"):
            st.dataframe(pd.DataFrame(shortage_list))
    else:
        st.success("✅ 모든 근무조에 인원이 충분히 배치되었습니다.")

    st.markdown("---")

    t1, t2, t3 = st.tabs(["📅 근무표", "⚖️ 공정성/부하", "💾 다운로드"])
    
    with t1:
        st.plotly_chart(ScheduleVisualizer.create_calendar_view(res), use_container_width=True)
        st.plotly_chart(ScheduleVisualizer.create_coverage_chart(res), use_container_width=True)
        
    with t2:
        c1, c2 = st.columns(2)
        c1.plotly_chart(ScheduleVisualizer.create_workload_chart(res), use_container_width=True)
        c2.plotly_chart(ScheduleVisualizer.create_fairness_chart(val), use_container_width=True)
        
    with t3:
        rows = []
        for n in res['nurses']:
            for d, s in enumerate(n['schedule']):
                rows.append({'Date': res['dates'][d]['date'], 'Name': n['name'], 'Shift': s})
        csv = pd.DataFrame(rows).to_csv(index=False).encode('utf-8-sig')
        st.download_button("CSV 다운로드", csv, "schedule.csv", "text/csv")