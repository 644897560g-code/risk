"""
Feature Engineering Agent - Correct version based on raw data structure
Generates feature calculation code from feature design document
"""

import json
import os
import sys
from typing import Dict, List
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.llm_client import LLMClient


class FeatureEngineeringAgent:
    """Feature Engineering Agent - Generates correct feature calculation code"""

    def __init__(self):
        self.feature_doc = None
        self.features = []
        self.llm_client = LLMClient()
        self.app_classification_cache = {}
        self.review_feedback = None  # 存储审核反馈

    def load_feature_design(self, path='outputs/feature_design/feature_design_doc.json'):
        """Load feature design document"""
        print(f"Loading feature design...")
        with open(path, 'r', encoding='utf-8') as f:
            self.feature_doc = json.load(f)
        self.features = self.feature_doc.get('features', [])
        print(f"   Loaded {len(self.features)} features")

    def load_app_classification_cache(self):
        """Load the 11,850 app classification cache"""
        cache_file = 'outputs/app_analysis/classification_complete_11850.json'
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.app_classification_cache = data.get('classifications', {})
                print(f"   Loaded {len(self.app_classification_cache)} app classifications")

    def generate_code_with_llm(self) -> str:
        """Generate feature calculation code using LLM"""
        print(f"\nGenerating feature calculation code...")

        # Build prompt with correct data structure info
        prompt = self._build_prompt_with_raw_data_info()

        messages = [{"role": "user", "content": prompt}]
        response = self.llm_client.chat(messages, temperature=0.1)

        # Extract code
        code = self._extract_code(response)
        if code:
            print(f"   Code generated ({len(code)} chars, {len(code.splitlines())} lines)")
            return code
        else:
            print(f"   Code extraction failed")
            print(f"   Response preview: {response[:500]}...")
            return None

    def _build_prompt_with_raw_data_info(self) -> str:
        """Build prompt with correct raw data structure information"""

        # Feature list by source
        applist = [f for f in self.features if f['data_source'] == 'applist']
        fdc = [f for f in self.features if f['data_source'] == 'fdc']
        base = [f for f in self.features if f['data_source'] == 'base']

        prompt = """# Task: Generate correct feature calculation code for Indonesian cash loan

## IMPORTANT: Raw Data Structure (from short URL JSON)

### applyTime (申请时间 - Anti-time-travel baseline)
- **Field**: `data['applyTime']` or `data['params']['base']['applyTime']`
- **Format**: Millisecond timestamp (e.g., 1773025791000 = 2026-03-09)
- **Usage**: Convert to datetime, filter all data AFTER this time

### applist Data Structure
```python
app_list = data['params']['appList']  # List of apps
for app in app_list:
    app['inTime']      # Install time (millisecond timestamp)
    app['upTime']      # Update time (millisecond timestamp)
    app['appName']     # App name (Chinese/Indonesian)
    app['appType']     # App type (integer)
    app['packageX']    # Package name (e.g., 'com.whatsapp.w4a')
    app['versionName'] # Version string
```

**App Classification**: Use `app_classification_cache[packageX]` to get category
**17 Standard Categories**: gambling, cash_loan, fintech_lending, banking, ewallet,
installment, app_store, fake_gps, clone_app, shopping, food_delivery, transportation,
utility, productivity, religious, social_entertainment, other

### FDC Data Structure
```python
fdc = data['params']['FDC']
fdc['history_inquiry']['last_3days']   # Last 3 days query count
fdc['history_inquiry']['last_7days']
fdc['history_inquiry']['last_30days']

# Loan records (pinjaman)
fdc['pinjaman'] = [
    {
        'tgl_penyaluran_dana': '2026-01-20',  # Disburse date (YYYY-MM-DD)
        'tgl_perjanjian_borrower': '2026-01-20',  # Agreement date
        'tgl_pelaporan_data': '2026-03-06',  # Report date
        'nilai_pendanaan': 1000000,  # Loan amount
        'sisa_pinjaman_berjalan': 1000000,  # Outstanding balance
        'dpd_max': 0,  # Max DPD
        'dpd_terakhir': 0,  # Last DPD
        'status_pinjaman': 'O',  # 'O'=Outstanding, 'C'=Closed
        'status_pinjaman_ket': 'Outstanding',
        'kualitas_pinjaman_ket': 'Lancar',  # Quality description
        'jenis_pengguna_ket': 'Individual',
        ...
    },
    ...
]

# Active platforms
fdc['platform_aktif']['count']  # Number of active platforms
```

### base Data Structure
```python
base = data['params']['base']
base['gender']       # 0=Male, 1=Female
base['birthday']     # 'DD-MM-YYYY' format (e.g., '15-02-1973')
base['salary']       # Monthly income (e.g., 12000000)
base['job']         # Occupation code (e.g., '12')
base['workYears']   # Years of work (e.g., 4)
base['marita']      # 1=Married, 2=Unmarried
base['children']    # Number of children
base['applyTime']   # Same as data['applyTime']
```

## Features to Generate ({len(self.features)} total)

### Applist Features ({len(applist)}):
"""
        for f in applist:
            prompt += f"- **{f['feature_name']}** ({f['feature_type']})\n"
            prompt += f"  Logic: {f['calculation_logic']}\n\n"

        prompt += f"""### FDC Features ({len(fdc)}):
"""
        for f in fdc:
            prompt += f"- **{f['feature_name']}** ({f['feature_type']})\n"
            prompt += f"  Logic: {f['calculation_logic']}\n\n"

        prompt += f"""### Base Features ({len(base)}):
"""
        for f in base:
            prompt += f"- **{f['feature_name']}** ({f['feature_type']})\n"
            prompt += f"  Logic: {f['calculation_logic']}\n\n"

        prompt += """
## Code Requirements

### CRITICAL: Anti-Time-Travel Implementation
1. **applyTime extraction**: `apply_time_ms = data.get('applyTime', 0)`
2. **Convert to datetime**: `apply_time = datetime.fromtimestamp(apply_time_ms / 1000)`
3. **Filter applist**: Only use apps where `inTime <= apply_time_ms`
4. **Filter FDC loans**: Only use loans where `tgl_penyaluran_dana_date <= apply_time.date()`
5. **Time windows**: Calculate from `apply_time` backwards (e.g., last 7 days = apply_time - timedelta(days=7))

### CRITICAL: App Classification
Use the 11,850 app classification cache:
```python
app_categories = {}
for app in filtered_applist:
    pkg = app.get('packageX', '')
    if pkg in self.app_classification_cache:
        app_categories[pkg] = self.app_classification_cache[pkg].get('category', 'other')
    else:
        app_categories[pkg] = 'other'
```

### CRITICAL: 17 Standard Categories (DO NOT use other names)
gambling, cash_loan, fintech_lending, banking, ewallet, installment,
app_store, fake_gps, clone_app, shopping, food_delivery, transportation,
utility, productivity, religious, social_entertainment, other

## Output Format

Generate COMPLETE Python code for FeatureCalculator class:

```python
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List


class FeatureCalculator:
    def __init__(self):
        self.app_classification_cache = self._load_app_cache()

    def _load_app_cache(self) -> Dict:
        cache_file = 'outputs/app_analysis/classification_complete_11850.json'
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('classifications', {})
        return {}

    def calculate_all(self, data: Dict, apply_time: str = None) -> Dict:
        # Extract apply time
        if not apply_time:
            apply_time_ms = data.get('applyTime', 0)
            if apply_time_ms:
                apply_time_dt = datetime.fromtimestamp(apply_time_ms / 1000)
            else:
                apply_time_dt = datetime.now()
        else:
            apply_time_dt = datetime.strptime(apply_time, '%Y-%m-%d %H:%M:%S')

        # Filter data (anti-time-travel)
        filtered_applist = self._filter_applist(data, apply_time_dt)
        filtered_fdc = self._filter_fdc(data, apply_time_dt)

        # Calculate features by module
        features = {}
        features.update(self._calc_applist_features(filtered_applist, apply_time_dt))
        features.update(self._calc_fdc_features(filtered_fdc, data, apply_time_dt))
        features.update(self._calc_base_features(data, apply_time_dt))

        return features

    def _filter_applist(self, data: Dict, apply_time_dt: datetime) -> List[Dict]:
        app_list = data.get('params', {}).get('appList', [])
        apply_time_ms = apply_time_dt.timestamp() * 1000
        filtered = [app for app in app_list if app.get('inTime', 0) <= apply_time_ms]
        return filtered

    def _filter_fdc(self, data: Dict, apply_time_dt: datetime) -> Dict:
        import copy
        fdc = copy.deepcopy(data.get('params', {}).get('FDC', {}))

        # Filter pinjaman records
        if 'pinjaman' in fdc:
            filtered_pinjaman = []
            for loan in fdc['pinjaman']:
                disburse_str = loan.get('tgl_penyaluran_dana', '')
                if disburse_str:
                    try:
                        disburse_date = datetime.strptime(disburse_str, '%Y-%m-%d')
                        if disburse_date <= apply_time_dt:
                            filtered_pinjaman.append(loan)
                    except:
                        filtered_pinjaman.append(loan)
                else:
                    filtered_pinjaman.append(loan)
            fdc['pinjaman'] = filtered_pinjaman

        return fdc

    def _calc_applist_features(self, filtered_applist: List[Dict], apply_time_dt: datetime) -> Dict:
        features = {}
        if not filtered_applist:
            return {f['feature_name']: 0 for f in self.features if f['data_source'] == 'applist'}

        # Categorize apps
        app_categories = {}
        for app in filtered_applist:
            pkg = app.get('packageX', '')
            if pkg in self.app_classification_cache:
                app_categories[pkg] = self.app_classification_cache[pkg].get('category', 'other')
            else:
                app_categories[pkg] = 'other'

        # [GENERATE CODE FOR EACH APPLIST FEATURE]

        return features

    def _calc_fdc_features(self, filtered_fdc: Dict, original_data: Dict, apply_time_dt: datetime) -> Dict:
        features = {}
        # [GENERATE CODE FOR EACH FDC FEATURE]
        return features

    def _calc_base_features(self, data: Dict, apply_time_dt: datetime) -> Dict:
        features = {}
        base = data.get('params', {}).get('base', {})
        # [GENERATE CODE FOR EACH BASE FEATURE]
        return features
```

**IMPORTANT**: Replace `[GENERATE CODE FOR EACH ...]` with actual calculation code for ALL 20 features.
Follow calculation_logic precisely. Handle division by zero. Use Chinese comments.

Now generate the complete code:
"""
        return prompt

    def _extract_code(self, response: str) -> str:
        """Extract Python code from LLM response"""
        if '```python' in response:
            start = response.find('```python') + 9
            end = response.find('```', start)
            if end > start:
                return response[start:end].strip()

        if 'class FeatureCalculator' in response:
            return response[response.find('class FeatureCalculator'):]

        return None

    def save_code(self, code: str, path='outputs/feature_code/features_calculator.py'):
        """Save generated code"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code)
        print(f"Code saved: {path}")
        print(f"   Lines: {len(code.splitlines())}")

    def run(self):
        """Main execution"""
        print("=" * 70)
        print("Feature Engineering Agent - Starting")
        print("=" * 70)

        # 1. Load feature design
        self.load_feature_design()

        # 2. Load app classification cache
        self.load_app_classification_cache()

        # 3. Generate code
        code = self.generate_code_with_llm()

        if not code:
            print("\nCode generation failed")
            return

        # 4. Save code
        self.save_code(code)

        print("\n" + "=" * 70)
        print("Feature Engineering Agent - Complete")
        print("=" * 70)
        print(f"Total features: {len(self.features)}")
        print(f"Code lines: {len(code.splitlines())}")


    def load_review_feedback(self, feedback_file: str = 'outputs/feature_code/review_result.json'):
        """加载审核反馈"""
        if os.path.exists(feedback_file):
            with open(feedback_file, 'r', encoding='utf-8') as f:
                self.review_feedback = json.load(f)
            print(f"Loaded review feedback from {feedback_file}")
            return True
        else:
            print(f"No review feedback found at {feedback_file}")
            return False

    def regenerate_with_feedback(self, existing_code: str) -> str:
        """使用审核反馈重新生成代码"""
        if not self.review_feedback:
            print("No review feedback available, using normal generation")
            return self.generate_code_with_llm()

        print(f"\nRegenerating code with review feedback...")

        # 提取审核问题和anomal
        logic_issues = self.review_feedback.get('logic_check', {}).get('issues', [])
        llm_suggestions = self.review_feedback.get('llm_review', {}).get('suggestions', [])
        syntax_errors = self.review_feedback.get('syntax_check', {}).get('errors', [])

        prompt = self._build_regeneration_prompt(existing_code, syntax_errors, logic_issues, llm_suggestions)

        messages = [{"role": "user", "content": prompt}]
        response = self.llm_client.chat(messages, temperature=0.1)

        code = self._extract_code(response)
        if code:
            print(f"   Regenerated code ({len(code)} chars, {len(code.splitlines())} lines)")
        else:
            print(f"   Regeneration failed")

        return code

    def _build_regeneration_prompt(self, existing_code: str, syntax_errors: List,
                                    logic_issues: List, llm_suggestions: List) -> str:
        """构建带反馈的代码生成prompt"""
        prompt = f"""# Task: Fix Feature Calculation Code Based on Review Feedback

## Original Code

```python
{existing_code}
```

## Review Feedback - Issues Found

### Syntax Errors
"""
        for err in syntax_errors:
            prompt += f"- {err}\n"

        prompt += f"""
### Logic Issues
"""
        for issue in logic_issues:
            prompt += f"- {issue}\n"

        prompt += f"""
### LLM Suggestions
"""
        for suggestion in llm_suggestions:
            prompt += f"- {suggestion}\n"

        prompt += f"""
## Fixing Requirements

1. **Fix all syntax errors** listed above
2. **Address all logic issues** listed above
3. **Implement LLM suggestions** where appropriate
4. **Keep existing correct logic** - only fix the reported issues
5. **Maintain code structure** - don't rewrite everything
6. **Ensure anti-time-travel** - still use applyTime correctly

## Output Format

Output complete Python code with all fixes applied. Use ```python ... ``` markdown block.

Now fix the code:
"""
        return prompt


if __name__ == '__main__':
    agent = FeatureEngineeringAgent()
    agent.run()
