#DOCSTRING
Feature Engineering Agent - Generate feature calculation code dynamically

Based on feature design document (JSON), dynamically generates Python calculation code.
Implements anti-time-travel mechanism.
#DOCSTRING

import json
import os
import sys
from typing import Dict, List, Tuple
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.llm_client import LLMClient


class FeatureEngineeringAgent:
    #DOCSTRINGFeature Engineering Agent - Dynamically generate feature calculation code#DOCSTRING

    def __init__(self):
        self.feature_doc = None
        self.features = []
        self.llm_client = LLMClient()
        self.generated_code = None
        self.features_by_source = {'applist': [], 'fdc': [], 'base': []}

    def load_feature_design(self, design_path='outputs/feature_design/feature_design_doc.json'):
        #DOCSTRINGLoad feature design document#DOCSTRING
        print(f"Loading feature design: {design_path}")
        with open(design_path, 'r', encoding='utf-8') as f:
            self.feature_doc = json.load(f)

        self.features = self.feature_doc.get('features', [])
        print(f"   Loaded {len(self.features)} features")
        self._categorize_features()

    def _categorize_features(self):
        #DOCSTRINGCategorize features by data source#DOCSTRING
        self.features_by_source = {'applist': [], 'fdc': [], 'base': []}
        for feature in self.features:
            source = feature.get('data_source', 'unknown')
            if source in self.features_by_source:
                self.features_by_source[source].append(feature)

        print(f"   Feature distribution:")
        for source, feats in self.features_by_source.items():
            print(f"     - {source}: {len(feats)} features")

    def generate_code_with_llm(self) -> str:
        #DOCSTRINGGenerate feature calculation code using LLM#DOCSTRING
        print("\nGenerating feature calculation code...")
        prompt = self._build_engineering_prompt()
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_client.chat(messages, temperature=0.1)
        code = self._extract_code_from_response(response)

        if code:
            print(f"   Code generated ({len(code)} chars)")
            self.generated_code = code
            return code
        else:
            print(f"   Code extraction failed")
            print(f"   Response preview: {response[:1000]}...")
            return None

    def _build_engineering_prompt(self) -> str:
        #DOCSTRINGBuild the engineering prompt#DOCSTRING
        applist_features = self.features_by_source.get('applist', [])
        fdc_features = self.features_by_source.get('fdc', [])
        base_features = self.features_by_source.get('base', [])

        prompt = f#DOCSTRING# Task: Generate feature calculation code for Indonesian cash loan risk control

## 1. Feature Design Summary

**Total features**: {len(self.features)}

### 1.1 Applist Features ({len(applist_features)}):
#DOCSTRING
        for feat in applist_features:
            prompt += f#DOCSTRING
- **{feat['feature_name']}** ({feat['feature_type']})
  - Business: {feat['business_explanation_cn']}
  - Logic: {feat['calculation_logic']}
  - Correlation: {feat['expected_risk_correlation']}
#DOCSTRING

        prompt += f#DOCSTRING
### 1.2 FDC Features ({len(fdc_features)}):
#DOCSTRING
        for feat in fdc_features:
            prompt += f#DOCSTRING
- **{feat['feature_name']}** ({feat['feature_type']})
  - Business: {feat['business_explanation_cn']}
  - Logic: {feat['calculation_logic']}
  - Correlation: {feat['expected_risk_correlation']}
#DOCSTRING

        prompt += f#DOCSTRING
### 1.3 Base Features ({len(base_features)}):
#DOCSTRING
        for feat in base_features:
            prompt += f#DOCSTRING
- **{feat['feature_name']}** ({feat['feature_type']})
  - Business: {feat['business_explanation_cn']}
  - Logic: {feat['calculation_logic']}
  - Correlation: {feat['expected_risk_correlation']}
#DOCSTRING

        prompt += f#DOCSTRING
## 2. Data Structure

### 2.1 Order Data
```python
order_data = {{
    'order_id': 'id002luzt202603090951432723072',
    'apply_time': '2026-03-09 09:51:43',
    'base': {{
        'gender': 0,
        'birthday': '15-02-1973',
        'salary': 12000000,
        'job': '12',
        'workYears': 4,
        'marita': 1,
        'children': 0
    }},
    'applist': [
        {{
            'packagename': 'com.whatsapp.w4a',
            'appname': 'WhatsApp',
            'category': 'social_entertainment',
            'installDate': '2026-02-01 10:30:00',
            'updateDate': '2026-03-01 15:20:00',
        }},
        ...
    ]
}}
```

### 2.2 FDC Data
```python
fdc_data = {{
    'history_inquiry': {{
        'last_3days': 2,
        'last_7days': 5,
        'last_30days': 12
    }},
    'pinjaman': [
        {{
            'loan_amount': 5000000,
            'outstanding_balance': 2000000,
            'max_dpd': 45,
            'status': 'active',
            'disburse_date': '2026-02-01',
        }},
        ...
    ],
    'platform_aktif': {{
        'count': 3,
    }}
}}
```

## 3. Code Requirements

### 3.1 Class Structure
Generate a `FeatureCalculator` class with:
1. `__init__()`: Initialize, load app classification cache
2. `calculate_all(order_data, fdc_data, apply_time=None)`: Calculate all features
3. `_calculate_applist_features(order_data, apply_time)`: Calculate applist features
4. `_calculate_fdc_features(fdc_data, apply_time)`: Calculate FDC features
5. `_calculate_base_features(order_data, apply_time)`: Calculate base features
6. `_apply_anti_time_travel(order_data, fdc_data, apply_time)`: Anti-time-travel

### 3.2 Anti-Time-Travel Mechanism
**Core Principle**: All features can only use data **before apply_time**
- For applist: Only count apps where `installDate <= apply_time`
- For FDC: Only count records where query/disburse date `<= apply_time`
- For time windows (e.g., last 7 days): Calculate from `apply_time` backwards

### 3.3 Exception Handling
- Division by zero: Return 0 or default value when denominator is 0
- Missing data: Return -1 or 0 when data is missing
- Boundary conditions: Handle empty lists, empty dicts

### 3.4 Code Standards
- Use Chinese comments for business logic
- Each feature calculation function is independent
- Return unified dict format: `{{feature_name: value}}`

## 4. Output Format

Output complete Python code (no other text):

python
# Feature Calculator - Indonesian Cash Loan Risk Control
# Auto-generated code template

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


class FeatureCalculator:
     # Feature calculator class

    def __init__(self):
        self.app_classification_cache = self._load_app_cache()

    def _load_app_cache(self) -> Dict:
        #DOCSTRINGLoad app classification cache (11,850 known apps)#DOCSTRING
        cache_file = 'outputs/app_analysis/classification_complete_11850.json'
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('classifications', {})
        return {}

    def calculate_all(self, order_data: Dict, fdc_data: Dict,
                     apply_time: str = None) -> Dict:
        #DOCSTRING
        Calculate all features

        Args:
            order_data: Order data (contains base and applist)
            fdc_data: FDC credit report data
            apply_time: Application time (anti-time-travel baseline)

        Returns:
            Feature dict {{feature_name: value}}
        #DOCSTRING
        # Anti-time-travel processing
        order_data, fdc_data = self._apply_anti_time_travel(order_data, fdc_data, apply_time)

        # Calculate by module
        applist_features = self._calculate_applist_features(order_data, apply_time)
        fdc_features = self._calculate_fdc_features(fdc_data, apply_time)
        base_features = self._calculate_base_features(order_data, apply_time)

        # Merge all features
        all_features = {}
        all_features.update(applist_features)
        all_features.update(fdc_features)
        all_features.update(base_features)

        return all_features

    def _apply_anti_time_travel(self, order_data: Dict, fdc_data: Dict,
                                apply_time: str) -> Tuple[Dict, Dict]:
        #DOCSTRING
        Anti-time-travel: Filter out data after application time
        #DOCSTRING
        if not apply_time:
            return order_data, fdc_data

        apply_dt = datetime.strptime(apply_time, '%Y-%m-%d %H:%M:%S')

        # Filter applist
        if 'applist' in order_data:
            filtered_applist = []
            for app in order_data['applist']:
                install_date = app.get('installDate', '')
                if install_date:
                    try:
                        install_dt = datetime.strptime(install_date, '%Y-%m-%d %H:%M:%S')
                        if install_dt <= apply_dt:
                            filtered_applist.append(app)
                    except:
                        filtered_applist.append(app)
                else:
                    filtered_applist.append(app)
            order_data['applist'] = filtered_applist

        # Filter FDC loan records
        if 'pinjaman' in fdc_data:
            filtered_pinjaman = []
            for loan in fdc_data['pinjaman']:
                disburse_date = loan.get('disburse_date', '')
                if disburse_date:
                    try:
                        disburse_dt = datetime.strptime(disburse_date, '%Y-%m-%d')
                        if disburse_dt <= apply_dt:
                            filtered_pinjaman.append(loan)
                    except:
                        filtered_pinjaman.append(loan)
                else:
                    filtered_pinjaman.append(loan)
            fdc_data['pinjaman'] = filtered_pinjaman

        return order_data, fdc_data

    def _calculate_applist_features(self, order_data: Dict, apply_time: str) -> Dict:
        #DOCSTRINGCalculate applist features#DOCSTRING
        features = {}
        applist = order_data.get('applist', [])

        if not applist:
            for feat_name in self._get_applist_feature_names():
                features[feat_name] = 0
            return features

        # Load app categories
        app_categories = self._categorize_apps(applist)

        # [GENERATE CODE FOR EACH APPLIST FEATURE HERE]
        # Follow the calculation_logic from feature design document

        return features

    def _calculate_fdc_features(self, fdc_data: Dict, apply_time: str) -> Dict:
        #DOCSTRINGCalculate FDC features#DOCSTRING
        features = {}

        if not fdc_data:
            for feat_name in self._get_fdc_feature_names():
                features[feat_name] = 0
            return features

        inquiry_stats = fdc_data.get('history_inquiry', {})
        pinjaman = fdc_data.get('pinjaman', [])

        # [GENERATE CODE FOR EACH FDC FEATURE HERE]

        return features

    def _calculate_base_features(self, order_data: Dict, apply_time: str) -> Dict:
        #DOCSTRINGCalculate base features#DOCSTRING
        features = {}
        base = order_data.get('base', {})

        if not base:
            for feat_name in self._get_base_feature_names():
                features[feat_name] = 0
            return features

        # [GENERATE CODE FOR EACH BASE FEATURE HERE]

        return features

    def _categorize_apps(self, applist: List[Dict]) -> Dict[str, str]:
        #DOCSTRINGCategorize apps#DOCSTRING
        categorized = {}
        for app in applist:
            pkg = app.get('packagename', '')
            if pkg in self.app_classification_cache:
                categorized[pkg] = self.app_classification_cache[pkg].get('category', 'other')
            else:
                categorized[pkg] = 'other'
        return categorized

    def _get_applist_feature_names(self) -> List[str]:
        #DOCSTRINGGet applist feature names#DOCSTRING
        return [f['feature_name'] for f in self.features if f['data_source'] == 'applist']

    def _get_fdc_feature_names(self) -> List[str]:
        #DOCSTRINGGet FDC feature names#DOCSTRING
        return [f['feature_name'] for f in self.features if f['data_source'] == 'fdc']

    def _get_base_feature_names(self) -> List[str]:
        #DOCSTRINGGet base feature names#DOCSTRING
        return [f['feature_name'] for f in self.features if f['data_source'] == 'base']


# Test code
if __name__ == '__main__':
    calculator = FeatureCalculator()
    print("Feature Calculator initialized")
```

**IMPORTANT**:
1. Replace `[GENERATE CODE FOR EACH ... FEATURE HERE]` with actual calculation code for EACH feature
2. Follow the `calculation_logic` field from feature design document STRICTLY
3. Implement anti-time-travel mechanism correctly
4. Handle all division-by-zero cases
5. Use Chinese comments for business logic

Now generate the complete Python code:
#DOCSTRING
        return prompt

    def _extract_code_from_response(self, response: str) -> str:
        #DOCSTRINGExtract code from LLM response#DOCSTRING
        if '```python' in response:
            code_start = response.find('```python') + 9
            code_end = response.find('```', code_start)
            if code_end > code_start:
                return response[code_start:code_end].strip()

        if 'class FeatureCalculator' in response:
            code_start = response.find('class FeatureCalculator')
            return response[code_start:]

        return None

    def save_generated_code(self, code: str,
                           output_path='outputs/feature_code/features_calculator.py'):
        #DOCSTRINGSave generated code#DOCSTRING
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(code)
        print(f"\nCode saved: {output_path}")
        print(f"   Lines: {len(code.splitlines())}")

    def run(self):
        #DOCSTRINGMain execution#DOCSTRING
        print("=" * 70)
        print("Feature Engineering Agent - Starting")
        print("=" * 70)

        # 1. Load feature design
        self.load_feature_design()

        # 2. Generate code
        code = self.generate_code_with_llm()

        if not code:
            print("\nCode generation failed")
            return

        # 3. Save code
        self.save_generated_code(code)

        print("\n" + "=" * 70)
        print("Feature Engineering Agent - Complete")
        print("=" * 70)
        print(f"\nStatistics:")
        print(f"   Total features: {len(self.features)}")
        print(f"   Code lines: {len(code.splitlines())}")
        print(f"   Output: outputs/feature_code/features_calculator.py")


if __name__ == '__main__':
    agent = FeatureEngineeringAgent()
    agent.run()
