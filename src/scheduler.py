import pandas as pd
import io

class DataLoader:
    @staticmethod
    def load_excel(uploaded_file):
        """엑셀 파일을 로드하여 시트별로 분리"""
        if uploaded_file is None:
            return None
        
        try:
            # 엑셀 파일 읽기
            xl = pd.ExcelFile(uploaded_file)
            sheets = {sheet_name: xl.parse(sheet_name) for sheet_name in xl.sheet_names}
            
            # 컬럼명 공백 제거 및 소문자 변환 (유연성 확보)
            for name, df in sheets.items():
                if not df.empty:
                    # 문자열 컬럼만 공백 제거
                    df.columns = df.columns.astype(str).str.strip()
            
            return sheets
        except Exception as e:
            raise Exception(f"데이터 로딩 중 오류가 발생했습니다: {str(e)}")

    @staticmethod
    def get_nurse_summary(sheets):
        """간호사 정보 요약"""
        # 시트 이름이 'Nurse' 또는 'nurses' 등으로 다양할 수 있음
        df = sheets.get('nurses') if 'nurses' in sheets else sheets.get('Nurse')
        
        if df is None:
            return {"total": 0, "charge": 0, "regular": 0, "new": 0}
        
        total = len(df)
        
        # Level 컬럼 확인
        if 'Level' in df.columns:
            levels = df['Level'].astype(str).str.lower()
            charge = levels.str.contains('charge|책임|head').sum()
            new = levels.str.contains('new|신규').sum()
        else:
            charge = 0
            new = 0
            
        return {
            "total": total,
            "charge": charge,
            "regular": total - charge - new,
            "new": new
        }

    @staticmethod
    def get_date_range(sheets):
        """근무 기간 추출 (Daily_Coverage 기준)"""
        # Daily_Coverage 시트 찾기
        df = None
        for key in sheets.keys():
            if 'daily' in key.lower() or 'coverage' in key.lower():
                df = sheets[key]
                break
        
        if df is None:
            # 없으면 오늘부터 30일 뒤로 임의 설정
            from datetime import datetime, timedelta
            today = datetime.now()
            return today.strftime("%Y-%m-%d"), (today + timedelta(days=30)).strftime("%Y-%m-%d")
        
        # 날짜 컬럼 찾기
        date_col = None
        for col in df.columns:
            if 'date' in col.lower() or '날짜' in col:
                date_col = col
                break
        
        if date_col:
            dates = pd.to_datetime(df[date_col]).dt.date
            return str(dates.min()), str(dates.max())
            
        return "2024-01-01", "2024-01-31"
