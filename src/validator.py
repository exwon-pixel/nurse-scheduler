"""
src/validator.py
스케줄 검증 모듈
"""
from typing import Dict, List

class ScheduleValidator:
    def __init__(self, result: Dict):
        self.result = result
        self.nurses = result['nurses']
        self.dates = result['dates']
        self.NUM_DAYS = len(self.dates)
        
        self.violations = {
            'HC1': [], 'HC2': [], 'HC3': [], 'HC4': [], 'HC6': [], 'STF': []
        }
        self.fairness = {}
        self.coverage_analysis = {}
    
    def validate_all(self) -> Dict:
        self._check_constraints()
        self._analyze_fairness()
        self._check_coverage_and_staffing()
        
        return {
            'violations': self.violations,
            'total_violations': sum(len(v) for v in self.violations.values()),
            'fairness': self.fairness,
            'coverage': self.coverage_analysis
        }
    
    def _check_constraints(self):
        for nurse in self.nurses:
            sch = nurse['schedule']
            name = nurse['name']
            
            for d in range(self.NUM_DAYS - 1):
                if sch[d] == 'E' and sch[d+1] == 'D':
                    self.violations['HC2'].append(f"{name} {self.dates[d]['date']} E→D")
                if sch[d] == 'N' and sch[d+1] in ['E', 'D']:
                    self.violations['HC2'].append(f"{name} {self.dates[d]['date']} N→{sch[d+1]}")
                if sch[d] == 'N' and sch[d+1] != 'OFF':
                    self.violations['HC4'].append(f"{name} {self.dates[d]['date']} N후 근무")

            for d in range(self.NUM_DAYS - 2):
                if sch[d] == 'N' and sch[d+1] == 'OFF' and sch[d+2] == 'D':
                    self.violations['HC3'].append(f"{name} {self.dates[d]['date']} N-OFF-D")
            
            for d in range(self.NUM_DAYS - 6):
                if 'OFF' not in sch[d:d+7]:
                    self.violations['HC6'].append(f"{name} {self.dates[d]['date']}부터 7일 연속")

    def _analyze_fairness(self):
        if not self.nurses:
            self.fairness = {'work_days': {'deviation': 0}, 'night_shifts': {'deviation': 0}}
            return

        work_days = [n['work_days'] for n in self.nurses]
        night_counts = [n['night_count'] for n in self.nurses]
        
        self.fairness = {
            'work_days': {
                'min': min(work_days), 'max': max(work_days), 'avg': sum(work_days)/len(work_days),
                'deviation': max(work_days) - min(work_days)
            },
            'night_shifts': {
                'min': min(night_counts), 'max': max(night_counts), 'avg': sum(night_counts)/len(night_counts),
                'deviation': max(night_counts) - min(night_counts)
            }
        }

    def _check_coverage_and_staffing(self):
        if not self.dates: return
        
        d_cnt = [d['coverage']['D'] for d in self.dates]
        e_cnt = [d['coverage']['E'] for d in self.dates]
        n_cnt = [d['coverage']['N'] for d in self.dates]
        
        denom = len(self.dates) if self.dates else 1
        self.coverage_analysis = {
            'D': sum(d_cnt)/denom, 'E': sum(e_cnt)/denom, 'N': sum(n_cnt)/denom
        }
        
        for date in self.dates:
            d_str = date['date']
            for s in ['D', 'E', 'N']:
                if date['charge_nurses'][s] == 0:
                    self.violations['STF'].append(f"{d_str} {s} Charge 부재")
                if date['new_nurses'][s] > 3:
                    self.violations['STF'].append(f"{d_str} {s} 신규 과다")
