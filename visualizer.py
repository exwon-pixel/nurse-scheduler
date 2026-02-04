"""
src/visualizer.py
스케줄 시각화 모듈 (Stacked Bar & Enhanced Fairness)
"""
import plotly.graph_objects as go

class ScheduleVisualizer:
    
    @staticmethod
    def create_calendar_view(result):
        nurses = result['nurses']
        dates = result['dates']
        nurse_names = [n['name'] for n in nurses]
        date_labels = [f"{d['date']}<br>({d['day_of_week']})" for d in dates]
        
        shift_map = {'D': 1, 'E': 2, 'N': 3, 'OFF': 0}
        z = [[shift_map[s] for s in n['schedule']] for n in nurses]
        # 텍스트가 너무 많으면 지저분하므로, 이니셜만 표시하거나 그대로 표시
        text = [[s for s in n['schedule']] for n in nurses]
        
        fig = go.Figure(data=go.Heatmap(
            z=z, x=date_labels, y=nurse_names,
            text=text, texttemplate='%{text}',
            # 색상: OFF(회색), D(노랑), E(주황), N(파랑)
            colorscale=[
                [0.0, '#eeeeee'], [0.25, '#eeeeee'], # OFF
                [0.25, '#FFD700'], [0.5, '#FFD700'], # D
                [0.5, '#FF8C00'], [0.75, '#FF8C00'], # E
                [0.75, '#4169E1'], [1.0, '#4169E1']  # N
            ],
            showscale=False, xgap=1, ygap=1
        ))
        fig.update_layout(
            title="📅 월간 근무표 (Heatmap)", 
            height=max(400, len(nurses)*40),
            xaxis_nticks=len(dates)
        )
        return fig

    @staticmethod
    def create_workload_chart(result):
        """
        [개선] 단순 총량 비교 -> 근무 유형별(D/E/N) 누적 막대 그래프
        누가 힘든 근무(N)를 많이 했는지 한눈에 파악 가능
        """
        nurses = result['nurses']
        names = [n['name'] for n in nurses]
        
        # 근무별 카운트 집계
        d_counts = []
        e_counts = []
        n_counts = []
        
        for n in nurses:
            sch = n['schedule']
            d_counts.append(sch.count('D'))
            e_counts.append(sch.count('E'))
            n_counts.append(sch.count('N'))
            
        fig = go.Figure()
        
        # 스택(Stack) 형태로 추가
        fig.add_trace(go.Bar(name='Day', x=names, y=d_counts, marker_color='#FFD700'))
        fig.add_trace(go.Bar(name='Evening', x=names, y=e_counts, marker_color='#FF8C00'))
        fig.add_trace(go.Bar(name='Night', x=names, y=n_counts, marker_color='#4169E1'))
        
        fig.update_layout(
            title="📊 간호사별 근무 구성 (누적 막대)", 
            barmode='stack', 
            yaxis_title="근무 횟수",
            legend_title="근무 형태",
            hovermode="x unified" # 마우스 올리면 합계까지 같이 보임
        )
        return fig

    @staticmethod
    def create_fairness_chart(validation):
        """
        [개선] 편차가 0일 때도 시각적으로 잘 보이도록 수정
        """
        d_work = validation['fairness']['work_days']['deviation']
        d_night = validation['fairness']['night_shifts']['deviation']
        
        x = ['총 근무일수 편차', '나이트 횟수 편차']
        y = [d_work, d_night]
        
        # 값이 0이어도 막대가 조금은 보이게(0.1) 처리하고 텍스트로 0 표시
        plot_y = [v if v > 0 else 0.05 for v in y]
        text = [f"{v} (Perfect!)" if v == 0 else f"{v}일/회 차이" for v in y]
        colors = ['#2ca02c' if v == 0 else '#d62728' for v in y] # 0이면 초록, 아니면 빨강
        
        fig = go.Figure(go.Bar(
            x=x, y=plot_y, 
            text=text, textposition='auto', 
            marker_color=colors
        ))
        
        fig.update_layout(
            title="⚖️ 공정성 지표 (낮을수록 좋음)", 
            yaxis_title="최대-최소 격차",
            yaxis_range=[0, max(max(y)*1.5, 1)] # Y축 범위 넉넉하게
        )
        return fig

    @staticmethod
    def create_coverage_chart(result):
        dates = [d['date'] for d in result['dates']]
        d_c = [d['coverage']['D'] for d in result['dates']]
        e_c = [d['coverage']['E'] for d in result['dates']]
        n_c = [d['coverage']['N'] for d in result['dates']]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dates, y=d_c, name='Day', line=dict(color='#FFD700', width=3)))
        fig.add_trace(go.Scatter(x=dates, y=e_c, name='Evening', line=dict(color='#FF8C00', width=3)))
        fig.add_trace(go.Scatter(x=dates, y=n_c, name='Night', line=dict(color='#4169E1', width=3)))
        
        fig.update_layout(
            title="📉 일별 투입 인원 현황", 
            yaxis_title="인원(명)",
            hovermode="x unified"
        )
        return fig