"""
src/scheduler.py
규정 준수 최우선 스케줄러 (Strict Safety First)
"""
import pandas as pd
from ortools.sat.python import cp_model
from datetime import datetime, timedelta

class NurseScheduler:
    def __init__(self, sheets, start_date, end_date):
        self.df_nurse = sheets.get('nurses') if 'nurses' in sheets else sheets.get('Nurse')
        self.df_requests = sheets.get('requests') if 'requests' in sheets else sheets.get('Requests', pd.DataFrame())
        
        self.start_date = start_date
        self.end_date = end_date
        
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        self.date_list = [(start + timedelta(days=i)).strftime("%Y-%m-%d") 
                          for i in range((end - start).days + 1)]
        self.NUM_DAYS = len(self.date_list)
        self.NUM_NURSES = len(self.df_nurse)
        self.SHIFTS = ['D', 'E', 'N', 'OFF'] 

    def optimize(self, max_time_seconds=300):
        model = cp_model.CpModel()
        shifts = {}

        # 0. 간호사 특성
        charge_indices = []
        new_indices = []
        for idx, row in self.df_nurse.iterrows():
            level = str(row.get('Level', '')).lower()
            if 'charge' in level or '책임' in level: charge_indices.append(idx)
            if 'new' in level or '신규' in level: new_indices.append(idx)

        # 1. 변수 생성
        for n in range(self.NUM_NURSES):
            for d in range(self.NUM_DAYS):
                for s_idx, _ in enumerate(self.SHIFTS):
                    shifts[(n, d, s_idx)] = model.NewBoolVar(f'shift_{n}_{d}_{s_idx}')

        # [HC1] 하루 1근무
        for n in range(self.NUM_NURSES):
            for d in range(self.NUM_DAYS):
                model.Add(sum(shifts[(n, d, s)] for s in range(4)) == 1)

        # [HC2] 근무 간격 (8시간 휴식 & N-OFF)
        for n in range(self.NUM_NURSES):
            for d in range(self.NUM_DAYS - 1):
                model.Add(shifts[(n, d, 1)] + shifts[(n, d+1, 0)] <= 1) # E->D
                model.Add(shifts[(n, d, 2)] + shifts[(n, d+1, 0)] <= 1) # N->D
                model.Add(shifts[(n, d, 2)] + shifts[(n, d+1, 1)] <= 1) # N->E
                model.AddImplication(shifts[(n, d, 2)], shifts[(n, d+1, 3)]) # N->OFF

        # [HC3] 30시간 휴식 (N-OFF-D 금지)
        for n in range(self.NUM_NURSES):
            for d in range(self.NUM_DAYS - 2):
                model.Add(shifts[(n, d, 2)] + shifts[(n, d+2, 0)] <= 1)

        # [HC4] 최대 6일 연속 근무
        for n in range(self.NUM_NURSES):
            for d in range(self.NUM_DAYS - 6):
                model.Add(sum(shifts[(n, d+k, 3)] for k in range(7)) >= 1)

        # [HC5] 휴가 신청
        if not self.df_requests.empty:
            req_df = self.df_requests.copy()
            req_df.columns = [c.lower() for c in req_df.columns]
            nurse_ids = self.df_nurse.iloc[:, 0].astype(str).tolist()
            id_map = {nid: i for i, nid in enumerate(nurse_ids)}
            for _, row in req_df.iterrows():
                nid_col = next((c for c in row.index if 'id' in c and 'req' not in c), None)
                date_col = next((c for c in row.index if 'date' in c), None)
                type_col = next((c for c in row.index if 'type' in c), None)
                if nid_col and date_col and type_col:
                    nid = str(row[nid_col])
                    r_date = str(row[date_col]).split(' ')[0]
                    r_type = str(row[type_col])
                    if nid in id_map and r_date in self.date_list:
                        n_idx = id_map[nid]
                        d_idx = self.date_list.index(r_date)
                        if r_type == 'OFF':
                            model.Add(shifts[(n_idx, d_idx, 3)] == 1)

        # Soft Constraints
        penalties = []
        
        # (1) 커버리지 부족 (Soft)
        if self.NUM_NURSES < 10: base_req = {'D': 2, 'E': 2, 'N': 1}
        elif self.NUM_NURSES < 15: base_req = {'D': 2, 'E': 2, 'N': 2}
        else: base_req = {'D': 3, 'E': 3, 'N': 2}

        for d in range(self.NUM_DAYS):
            for s_idx, s_char in enumerate(['D', 'E', 'N']):
                req_val = base_req[s_char]
                actual = sum(shifts[(n, d, s_idx)] for n in range(self.NUM_NURSES))
                short = model.NewIntVar(0, self.NUM_NURSES, f'short_{d}_{s_char}')
                model.Add(short >= req_val - actual)
                penalties.append(short * 1000)

        # (2) 나이트 6회 초과 방지
        target_n = int(self.NUM_DAYS / 5)
        for n in range(self.NUM_NURSES):
            night_days = sum(shifts[(n, d, 2)] for d in range(self.NUM_DAYS))
            excess = model.NewIntVar(0, self.NUM_DAYS, f'ex_{n}')
            model.AddMaxEquality(excess, [night_days - 6, model.NewConstant(0)])
            penalties.append(excess * 5000)
            
            diff_n = model.NewIntVar(-self.NUM_DAYS, self.NUM_DAYS, f'nd_{n}')
            model.Add(diff_n == night_days - target_n)
            sq_n = model.NewIntVar(0, self.NUM_DAYS**2, f'nd_sq_{n}')
            model.AddMultiplicationEquality(sq_n, [diff_n, diff_n])
            penalties.append(sq_n * 20)

        # (3) 근무일수 평준화
        target_work = int(self.NUM_DAYS * 5 / 7)
        for n in range(self.NUM_NURSES):
            work_days = sum(shifts[(n, d, s)] for d in range(self.NUM_DAYS) for s in range(3))
            diff = model.NewIntVar(-self.NUM_DAYS, self.NUM_DAYS, f'wd_{n}')
            model.Add(diff == work_days - target_work)
            sq_diff = model.NewIntVar(0, self.NUM_DAYS**2, f'wd_sq_{n}')
            model.AddMultiplicationEquality(sq_diff, [diff, diff])
            penalties.append(sq_diff * 10)

        model.Minimize(sum(penalties))
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(max_time_seconds)
        solver.parameters.log_search_progress = True
        solver.parameters.num_search_workers = 8
        
        status = solver.Solve(model)

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            return self._format_result(solver, shifts, status, max_time_seconds)
        else:
            raise Exception("해를 찾을 수 없습니다. (인원 데이터 확인 필요)")

    def _format_result(self, solver, shifts, status, time_sec):
        res_nurses = []
        daily_cov = {d: {'D': 0, 'E': 0, 'N': 0} for d in range(self.NUM_DAYS)}
        daily_new = {d: {'D': 0, 'E': 0, 'N': 0} for d in range(self.NUM_DAYS)}
        daily_charge = {d: {'D': 0, 'E': 0, 'N': 0} for d in range(self.NUM_DAYS)}
        
        for n_idx, row in self.df_nurse.iterrows():
            name = row.get('Name') or row.get('이름') or f'N{n_idx}'
            raw_level = str(row.get('Level', 'Regular')).lower()
            if 'charge' in raw_level or '책임' in raw_level: level = 'Charge'
            elif 'new' in raw_level or '신규' in raw_level: level = 'New'
            else: level = 'Regular'
            
            schedule = []
            w_days = 0
            n_count = 0
            
            for d in range(self.NUM_DAYS):
                for s in range(4):
                    if solver.Value(shifts[(n_idx, d, s)]):
                        s_char = self.SHIFTS[s]
                        schedule.append(s_char)
                        if s < 3: 
                            w_days += 1
                            daily_cov[d][s_char] += 1
                            if level == 'New': daily_new[d][s_char] += 1
                            if level == 'Charge': daily_charge[d][s_char] += 1
                        if s == 2: n_count += 1
            
            res_nurses.append({
                "nurse_id": f"N{n_idx}", "name": name, "level": level,
                "schedule": schedule, "work_days": w_days, "night_count": n_count,
                "off_count": self.NUM_DAYS - w_days
            })
            
        dates_info = []
        for i, d_str in enumerate(self.date_list):
            dt = datetime.strptime(d_str, "%Y-%m-%d")
            dates_info.append({
                "date": d_str, 
                "day_of_week": ["월","화","수","목","금","토","일"][dt.weekday()],
                "coverage": daily_cov[i],
                "new_nurses": daily_new[i],
                "charge_nurses": daily_charge[i]
            })

        return {
            "schedule_id": f"SCH-{datetime.now().strftime('%Y%m%d-%H%M')}",
            "start_date": self.start_date, "end_date": self.end_date,
            "total_nurses": self.NUM_NURSES, "status": solver.StatusName(status),
            "optimization_time": time_sec, "nurses": res_nurses, "dates": dates_info
        }