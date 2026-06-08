'''
Feature Engineering Agent - Generate feature calculation code dynamically
'''

import json
import os
import sys
from typing import Dict, List, Tuple
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.llm_client import LLMClient


class FeatureEngineeringAgent:
    '''Feature Engineering Agent'''

    def __init__(self):
        self.feature_doc = None
        self.features = []
        self.llm_client = LLMClient()
        self.generated_code = None
        self.features_by_source = {'applist': [], 'fdc': [], 'base': []}

    def load_feature_design(self, design_path='outputs/feature_design/feature_design_doc.json'):
        with open(design_path, 'r', encoding='utf-8') as f:
            self.feature_doc = json.load(f)
        self.features = self.feature_doc.get('features', [])
        print(f"Loaded {len(self.features)} features")
        self._categorize_features()

    def _categorize_features(self):
        self.features_by_source = {'applist': [], 'fdc': [], 'base': []}
        for feature in self.features:
            source = feature.get('data_source', 'unknown')
            if source in self.features_by_source:
                self.features_by_source[source].append(feature)
        for source, feats in self.features_by_source.items():
            print(f"  {source}: {len(feats)}")

    def generate_code_with_llm(self):
        prompt = self._build_prompt()
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_client.chat(messages, temperature=0.1)
        code = self._extract_code(response)
        if code:
            print(f"Code generated ({len(code)} chars)")
            self.generated_code = code
            return code
        return None

    def _build_prompt(self):
        applist = self.features_by_source.get('applist', [])
        fdc = self.features_by_source.get('fdc', [])
        base = self.features_by_source.get('base', [])
        
        prompt = "# Task: Generate Python feature calculation code\n\n"
        prompt += f"Total features: {len(self.features)}\n\n"
        
        prompt += "## Features by Source\n\n"
        for source, feats in [('applist', applist), ('fdc', fdc), ('base', base)]:
            prompt += f"### {source.upper()} ({len(feats)} features):\n"
            for f in feats:
                prompt += f"- {f['feature_name']} ({f['feature_type']}): {f['calculation_logic']}\n"
            prompt += "\n"
        
        prompt += "## Requirements:\n"
        prompt += "1. Create FeatureCalculator class\n"
        prompt += "2. Implement anti-time-travel mechanism\n"
        prompt += "3. Handle division by zero\n"
        prompt += "4. Use Chinese comments\n"
        prompt += "5. Return dict format: {feature_name: value}\n\n"
        
        prompt += "Output complete Python code only.\n"
        return prompt

    def _extract_code(self, response):
        if '```python' in response:
            start = response.find('```python') + 9
            end = response.find('```', start)
            if end > start:
                return response[start:end].strip()
        return None

    def save_code(self, code, path='outputs/feature_code/features_calculator.py'):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code)
        print(f"Code saved: {path}")

    def run(self):
        print("=" * 70)
        print("Feature Engineering Agent - Starting")
        print("=" * 70)
        self.load_feature_design()
        code = self.generate_code_with_llm()
        if code:
            self.save_code(code)
            print(f"\nTotal: {len(self.features)} features, {len(code.splitlines())} lines")

if __name__ == '__main__':
    agent = FeatureEngineeringAgent()
    agent.run()
