"""
Feature Orchestrator - 特征工程主协调Agent (v2.0 - 合并架构)

流程：
    特征开发Agent(设计+工程+self-review) → 特征评估Agent → 反馈聚合

变更：
    - 2026-05-29: 合并特征设计和特征工程为"特征开发Agent"
    - 2026-05-29: 移除特征审核Agent（由self-review替代）
    - 2026-05-29: 新增IV/PSI反馈回路
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from agents.feature_development_agent import FeatureDevelopmentAgent, create_feature_development_agent
from agents.feature_evaluation_agent import FeatureEvaluator
from agents.feature_deployment_agent import FeatureDeploymentAgent
from backend.app.database import SessionLocal
from backend.services.template_library import ACTIVE_STATUS, list_templates
from backend.services.project_service import list_project_templates


class DataFlowRegistry:
    """数据流注册表 - 管理Agent之间的输入输出文件依赖关系"""

    def __init__(self):
        self.registry_file = 'outputs/feature_code/data_flow_registry.json'
        self.registry = self._load()

    def _load(self) -> Dict:
        """加载数据流注册表"""
        if os.path.exists(self.registry_file):
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'agent_executions': [],
            'latest_outputs': {}
        }

    def save(self):
        """保存数据流注册表"""
        os.makedirs(os.path.dirname(self.registry_file), exist_ok=True)
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(self.registry, f, ensure_ascii=False, indent=2)

    def register_execution(self, agent_name: str, inputs: Dict[str, str], outputs: Dict[str, str], metadata: Dict = None):
        """注册一次Agent执行"""
        execution = {
            'agent_name': agent_name,
            'timestamp': datetime.now().isoformat(),
            'inputs': inputs,
            'outputs': outputs,
            'metadata': metadata or {}
        }
        self.registry['agent_executions'].append(execution)
        for output_name, output_path in outputs.items():
            self.registry['latest_outputs'][output_name] = output_path
        self.save()

    def get_latest_output(self, output_name: str, default: str = None) -> Optional[str]:
        """获取某个Agent的最新输出文件路径"""
        return self.registry['latest_outputs'].get(output_name, default)

    def get_execution_history(self, agent_name: str = None) -> List[Dict]:
        """获取执行历史"""
        if agent_name:
            return [e for e in self.registry['agent_executions'] if e['agent_name'] == agent_name]
        return self.registry['agent_executions']

    def get_inputs_for_next_agent(self, current_agent: str) -> Dict[str, str]:
        """获取current_agent的输出作为下一个Agent的输入"""
        history = self.get_execution_history(current_agent)
        if not history:
            return {}
        return history[-1]['outputs']


class FeatureOrchestrator:
    """特征工程主协调Agent (v2.0)"""

    def __init__(self):
        self.state_file = 'outputs/feature_code/orchestrator_state.json'
        self.log_file = 'outputs/feature_code/orchestrator.log'
        self.state = self._load_state()

        # 数据流注册表
        self.data_flow = DataFlowRegistry()

        # 子Agent
        self.development_agent = create_feature_development_agent()
        self.evaluation_agent = FeatureEvaluator()
        self.deployment_agent = FeatureDeploymentAgent()

        # 流程控制
        self.current_round = self._get_next_round()

    def _get_next_round(self) -> int:
        """获取下一轮编号"""
        feedback_dir = 'outputs/evaluation'
        if not os.path.exists(feedback_dir):
            return 1
        existing = [f for f in os.listdir(feedback_dir)
                    if f.startswith('iv_psi_feedback_r') and f.endswith('.json')]
        if not existing:
            return 1
        max_r = 0
        for f in existing:
            try:
                r = int(f.replace('iv_psi_feedback_r', '').replace('.json', ''))
                max_r = max(max_r, r)
            except:
                pass
        return max_r + 1

    def _load_state(self) -> Dict:
        """加载流程状态"""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'current_step': 'data_analysis',
            'completed_steps': [],
            'status': 'not_started',
            'start_time': None,
            'last_update': None
        }

    def _save_state(self):
        """保存流程状态"""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _log(self, message: str):
        """记录执行日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        print(log_entry.strip())

        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)

    def _update_state(self, completed_step: str, status: str, next_step: str = None):
        """更新流程状态"""
        self.state['current_step'] = next_step or completed_step
        self.state['status'] = status
        self.state['last_update'] = datetime.now().isoformat()
        if completed_step not in self.state['completed_steps']:
            self.state['completed_steps'].append(completed_step)
        self._save_state()

    def _prepare_for_next_round(self):
        """为下一轮重置状态，但保留已完成的步骤标记以便反馈读取"""
        # 只重置完成标记，让每轮都能重新执行所有步骤
        # 但不清除已有反馈文件（多轮反馈由 load_iv_psi_feedback 自动读取）
        self.state['completed_steps'] = []
        self.state['current_step'] = 'data_analysis'
        self.state['status'] = 'ready'
        self.state['start_time'] = datetime.now().isoformat()
        self.state['last_update'] = None
        self._save_state()

        # 同时累加已通过特征到累计记录
        self._accumulate_passed_features()

    def _accumulate_passed_features(self):
        """将当前轮的通过特征累加到累计记录中"""
        passed_path = 'outputs/evaluation/passed_features.json'
        accumulated_path = 'outputs/evaluation/accumulated_passed_features.json'

        if not os.path.exists(passed_path):
            return

        with open(passed_path, 'r', encoding='utf-8') as f:
            current = json.load(f)

        current_passed = current.get('passed_features', [])
        current_names = {f.get('feature_name', f.get('name', '')) for f in current_passed}

        # 加载已有累计记录
        all_passed = []
        all_names = set()
        if os.path.exists(accumulated_path):
            with open(accumulated_path, 'r', encoding='utf-8') as f:
                acc = json.load(f)
            all_passed = acc.get('passed_features', [])
            all_names = {f.get('feature_name', f.get('name', '')) for f in all_passed}

        # 合并新通过的特征（去重）
        new_count = 0
        for feat in current_passed:
            name = feat.get('feature_name', feat.get('name', ''))
            if name and name not in all_names:
                all_passed.append(feat)
                all_names.add(name)
                new_count += 1

        # 保存累计结果
        with open(accumulated_path, 'w', encoding='utf-8') as f:
            json.dump({
                'total_rounds': self.current_round,
                'total_passed': len(all_passed),
                'passed_features': all_passed,
                'thresholds': current.get('thresholds', {})
            }, f, ensure_ascii=False, indent=2)

        self._log(f"  累计通过特征: {len(all_passed)}个（本轮新增{new_count}个）")

    def run_full_pipeline(self, start_from_step: str = None,
                          max_rounds: int = 1):
        """
        运行完整的特征工程流程 (v2.0)，支持多轮迭代

        Args:
            start_from_step: 从哪个步骤开始
            max_rounds: 最大轮数（>1时自动多轮迭代，每轮生成不同参数组合的特征）

        Returns:
            是否全部成功
        """
        overall_success = True
        total_passed_features = 0

        for round_idx in range(max_rounds):
            round_num = self.current_round + round_idx

            self._log("=" * 80)
            self._log(f"开始执行特征工程全流程 (第{round_num}轮, 共{max_rounds}轮)")
            self._log("=" * 80)

            # 每轮重置development_agent为全新实例（确保不携带之前轮次的特征）
            if round_idx > 0:
                self.development_agent = create_feature_development_agent()

            self.state['start_time'] = datetime.now().isoformat()
            self._save_state()

            try:
                # 步骤1: 数据分析（简化，使用已有结果）
                if not start_from_step or start_from_step == 'data_analysis':
                    if 'data_analysis' not in self.state['completed_steps']:
                        self._log("\n【步骤1/5】数据分析Agent")
                        result = self._run_data_analysis()
                        if not result:
                            self._log("❌ 数据分析失败，流程终止")
                            return False
                        self._update_state('data_analysis', 'data_analysis_completed', next_step='feature_development')
                        start_from_step = None

                # 步骤2: 特征开发（设计+工程+self-review）
                if start_from_step in ['feature_development', None]:
                    if 'feature_development' not in self.state['completed_steps']:
                        self._log("\n【步骤2/5】特征开发Agent（设计+工程+self-review）")
                        result = self._run_feature_development()
                        if not result:
                            self._log("❌ 特征开发失败，流程终止")
                            overall_success = False
                            break
                        self._update_state('feature_development', 'feature_development_completed', next_step='feature_evaluation')
                        start_from_step = None

                # 步骤3: 特征评估
                if start_from_step in ['feature_evaluation', None]:
                    if 'feature_evaluation' not in self.state['completed_steps']:
                        self._log("\n【步骤3/5】特征评估Agent")
                        result = self._run_feature_evaluation()
                        if not result:
                            self._log("❌ 特征评估失败，流程终止")
                            overall_success = False
                            break
                        self._update_state('feature_evaluation', 'feature_evaluation_completed', next_step='feedback_aggregation')
                        start_from_step = None

                # 步骤4: 反馈聚合（IV/PSI总结）
                if start_from_step in ['feedback_aggregation', None]:
                    if 'feedback_aggregation' not in self.state['completed_steps']:
                        self._log("\n【步骤4/5】反馈聚合（IV/PSI总结）")
                        result = self._run_feedback_aggregation()
                        if not result:
                            self._log("⚠️ 反馈聚合失败（不影响整体流程）")
                        self._update_state('feedback_aggregation', 'feedback_aggregation_completed', next_step='feature_deployment')
                        start_from_step = None

                # 步骤5: 特征部署
                if start_from_step in ['feature_deployment', None]:
                    if 'feature_deployment' not in self.state['completed_steps']:
                        self._log("\n【步骤5/5】特征部署Agent")
                        result = self._run_feature_deployment()
                        if not result:
                            self._log("❌ 特征部署失败，流程终止")
                            overall_success = False
                            break
                        self._update_state('feature_deployment', 'all_completed', next_step='completed')

                # 完成单轮
                self._log(f"\n✅ 第{round_num}轮执行完成！")
                self.state['status'] = 'completed'
                self.state['end_time'] = datetime.now().isoformat()
                self._save_state()

                # 累加已通过特征
                self._accumulate_passed_features()

                # 更新总计数
                acc_path = 'outputs/evaluation/accumulated_passed_features.json'
                if os.path.exists(acc_path):
                    with open(acc_path, 'r', encoding='utf-8') as f:
                        acc = json.load(f)
                    total_passed_features = acc.get('total_passed', 0)
                    self._log(f"  累计通过特征总数: {total_passed_features}")

                # 准备下一轮
                if round_idx < max_rounds - 1:
                    self._log(f"\n准备第{round_num + 1}轮...")
                    self._prepare_for_next_round()
                    # 更新 current_round 到下一轮
                    self.current_round = self._get_next_round()

            except Exception as e:
                self._log(f"\n❌ 流程执行出错: {str(e)}")
                import traceback
                traceback.print_exc()
                self.state['status'] = 'error'
                self.state['error'] = str(e)
                self._save_state()
                overall_success = False
                break

        # 全部轮次完成
        self._log("\n" + "=" * 80)
        self._log(f"{'='*80}")
        self._log(f"🏆 全部 {max_rounds} 轮执行完成！")
        self._log(f"累计通过特征: {total_passed_features}个")
        self._log(f"{'='*80}")

        return overall_success

    def _build_generation_param_combos(self, project_id: int = None) -> Dict[str, List[Dict]]:
        """Build the template combo set for this run.

        T001-T016 are built-in. T017+ are included only when the current project
        explicitly enables the active platform template.
        """
        from agents.feature_mass_producer import build_param_combos

        extra_templates = []
        if project_id:
            db = SessionLocal()
            try:
                rows = list_project_templates(db, project_id, enabled=True)
                extra_templates = [
                    row.template
                    for row in rows
                    if row.template and row.template.status == ACTIVE_STATUS
                ]
                enabled_ids = [t.template_id for t in extra_templates]
                self._log(f"  项目 {project_id} 已启用模板: {enabled_ids}")
            finally:
                db.close()
        else:
            self._log("  未指定项目，使用内置模板 T001-T016")

        param_combos = build_param_combos(extra_templates=extra_templates)
        dynamic_ids = [
            tid for tid in sorted(param_combos)
            if tid.startswith('T') and tid[1:].isdigit() and int(tid[1:]) > 16
        ]
        if dynamic_ids:
            self._log(f"  本次纳入项目动态模板: {dynamic_ids}")
        return param_combos

    def run_mass_production(self, short_url_file: str = None, labels_excel: str = None, project_id: int = None):
        """批量生产模式：单轮一次性生成333个特征

        作为FeatureOrchestrator的正式阶段，与run_full_pipeline()平级。
        通过 --mode mass-produce 触发。

        流程（5个正式步骤）:
        1. mass_production:   确定性枚举所有参数组合→生成特征代码
        2. reference_computation: 加载样本→划分→Pass1参考分布计算
        3. feature_evaluation:   Pass2: 评估所有特征（IV/PSI/覆盖率）
        4. feature_deployment:   打包部署v23
        5. feedback_aggregation: 汇总评估结果

        Args:
            short_url_file: 短链URL文件路径（None=使用默认）
            labels_excel: 好坏标签Excel文件路径（None=使用默认）
        """
        # Use defaults if not provided
        if short_url_file is None:
            short_url_file = '0421全样本短链.txt'
        if labels_excel is None:
            labels_excel = '印尼模型分_2026_04_21_建模样本aiagent.xlsx'
        self._mass_total = 0
        self._mass_passed_count = 0
        self._mass_passed = []

        self._log("=" * 80)
        self._log("批量特征生产模式 (orchestrator正式阶段)")
        self._log("=" * 80)

        self.state['start_time'] = datetime.now().isoformat()
        self._save_state()

        try:
            # ---- Step 1: 批量生成特征代码 ----
            if 'mass_production' not in self.state['completed_steps']:
                self._log("\n【步骤1/5】批量特征生产")
                from agents.feature_mass_producer import produce_all_features, save_feature_calculator
                param_combos = self._build_generation_param_combos(project_id)
                code = produce_all_features(param_combos=param_combos)
                save_feature_calculator(code, param_combos=param_combos)
                total_features = sum(len(combos) for combos in param_combos.values())
                self._log(f"  ✅ 特征代码已生成（{total_features}个特征）")

                self.data_flow.register_execution(
                    agent_name='feature_mass_producer',
                    inputs={
                        'builtin_param_combos': 'agents/feature_mass_producer.py::_build_param_combos',
                        'project_templates': f'project_id={project_id}' if project_id else 'builtin_only',
                    },
                    outputs={
                        'features_calculator': 'outputs/feature_code/features_calculator_v2.py',
                        'feature_metadata': 'outputs/feature_code/feature_metadata.json',
                    },
                    metadata={'total_features': total_features,
                              'project_id': project_id,
                              'mode': 'deterministic'}
                )
                self._update_state('mass_production', 'mass_production_completed', next_step='reference_computation')

            # ---- Step 2: 参考分布计算 ----
            if 'reference_computation' not in self.state['completed_steps']:
                self._log("\n【步骤2/5】参考分布预计算")
                self._log("  [step2] 创建 FeatureEvaluator...")
                eval_agent = FeatureEvaluator()
                self._log("  [step2] 加载本地样本（self._log）...")
                import sys as _sys
                print("  [step2] 加载本地样本（print to stderr）...", flush=True, file=_sys.stderr)
                n_samples = eval_agent.load_sample_data_local(
                    short_url_file=short_url_file,
                    labels_excel=labels_excel,
                    data_dir='data/all_samples'
                )
                self._log(f"  加载 {n_samples} 个样本")
                self._log("  [step2] 划分数据集...")
                eval_agent.split_data(oot_ratio=0.2)
                n_train = len(eval_agent.train_data)
                n_oot = len(eval_agent.oot_data)
                self._log(f"  训练集: {n_train}, OOT: {n_oot}")
                self._log("  [step2] 计算参考分布...")
                refs = eval_agent.compute_reference_distributions()
                from agents.feature_mass_producer import save_reference_distributions
                save_reference_distributions(refs)
                self._log(f"  参考分布已保存")

                # 重建特征代码（注入参考分布）
                self._log("  [step2] 重建特征代码...")
                from agents.feature_mass_producer import produce_all_features
                param_combos = self._build_generation_param_combos(project_id)
                code = produce_all_features(ref_distributions=refs, param_combos=param_combos)
                save_feature_calculator(code, param_combos=param_combos)
                self._log(f"  ✅ 特征代码已重建（T010-T012带参考分布）")

                self._log("  [step2] 加载特征计算器...")
                eval_agent.ref_distributions = refs
                eval_agent.load_feature_calculator('outputs/feature_code/features_calculator_v2.py')

                # 保存到self以供后续步骤使用
                self._mass_eval_agent = eval_agent

                self.data_flow.register_execution(
                    agent_name='reference_computation',
                    inputs={'train_data': f'{n_train} samples', 'code': 'features_calculator_v2.py'},
                    outputs={'reference_distributions': 'outputs/feature_code/reference_distributions.json'},
                    metadata={'train_size': n_train, 'oot_size': n_oot}
                )
                self._update_state('reference_computation', 'reference_computation_completed', next_step='feature_evaluation')

            # ---- Step 3: 特征评估 ----
            if 'feature_evaluation' not in self.state['completed_steps']:
                self._log("\n【步骤3/5】批量特征评估（Pass 2）")
                eval_agent = self._mass_eval_agent

                self._log("  计算训练集特征...")
                df_train = eval_agent.calculate_features_on_dataset(eval_agent.train_data)
                self._log("  计算OOT集特征...")
                df_oot = eval_agent.calculate_features_on_dataset(eval_agent.oot_data)

                self._log("  评估IV/PSI/覆盖率...")
                feature_names = [c for c in df_train.columns if c not in ('target', 'sample_index')]
                self._log(f"  评估 {len(feature_names)} 个特征")

                feature_metadata = {}
                metadata_path = 'outputs/feature_code/feature_metadata.json'
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata_payload = json.load(f)
                        feature_metadata = metadata_payload.get('features', metadata_payload)
                        self._log(f"  已加载特征元数据: {metadata_path}")
                    except Exception as e:
                        self._log(f"  ⚠ 特征元数据文件读取失败，评估结果仅保存指标: {e}")
                else:
                    self._log(f"  ⚠ 特征元数据文件不存在: {metadata_path}")
                design_doc_path = 'outputs/feature_design/feature_design_doc.json'
                if os.path.exists(design_doc_path):
                    try:
                        with open(design_doc_path, 'r', encoding='utf-8') as f:
                            design_doc = json.load(f)
                        design_features = design_doc.get('features', [])
                        for feat in design_features:
                            feat_name = feat.get('feature_name')
                            if not feat_name:
                                continue
                            metadata = {
                                k: feat.get(k)
                                for k in (
                                    'feature_name',
                                    'template_id',
                                    'data_source',
                                    'data_sources',
                                    'calculation_logic',
                                    'formula_template',
                                    'formula',
                                )
                                if feat.get(k) not in (None, '')
                            }
                            feature_metadata[feat_name] = {
                                **feature_metadata.get(feat_name, {}),
                                **metadata,
                            }
                    except Exception as e:
                        self._log(f"  ⚠ 设计文档元数据加载失败: {e}")

                passed = []
                failed = []
                for feat_name in feature_names:
                    iv = eval_agent.calculate_iv(df_train, feat_name)
                    psi = eval_agent.calculate_psi(df_train, df_oot, feat_name)
                    cov = eval_agent.calculate_coverage(df_train, feat_name)
                    result = {
                        'feature_name': feat_name, 'iv': round(iv, 6),
                        'psi': round(psi, 6), 'coverage': round(cov, 6),
                        'status': 'passed' if iv >= 0.02 and psi <= 0.25 and cov > 0.05 else 'failed'
                    }
                    result.update(feature_metadata.get(feat_name, {}))
                    icon = '✅' if result['status'] == 'passed' else '❌'
                    self._log(f"  {icon} {feat_name:<45s} IV={iv:<8.4f} PSI={psi:<8.4f} Cov={cov*100:>6.2f}%")
                    if result['status'] == 'passed':
                        passed.append(result)
                    else:
                        failed.append(result)

                passed_count = len(passed)
                total = passed_count + len(failed)
                self._log(f"\n  通过: {passed_count}/{total}")

                # 设置 evaluation_results 供 HTML 报告使用
                eval_results_for_report = []
                for r in passed:
                    eval_results_for_report.append({
                        'feature_name': r['feature_name'], 'iv': r['iv'],
                        'psi': r['psi'], 'coverage': r['coverage'], 'passed': True
                    })
                for r in failed:
                    eval_results_for_report.append({
                        'feature_name': r['feature_name'], 'iv': r['iv'],
                        'psi': r['psi'], 'coverage': r['coverage'], 'passed': False
                    })
                eval_agent.evaluation_results = {
                    'results': eval_results_for_report, 'total_features': total,
                    'passed_features': passed_count,
                    'thresholds': {'iv': 0.02, 'psi': 0.25, 'coverage': 0.05}
                }

                # 保存评估结果
                os.makedirs('outputs/evaluation', exist_ok=True)
                eval_result = {
                    'timestamp': datetime.now().isoformat(), 'total_features': total,
                    'passed': passed_count, 'failed': total - passed_count,
                    'passed_features': passed, 'failed_features': failed,
                }
                with open('outputs/evaluation/passed_features.json', 'w') as f:
                    json.dump(eval_result, f, ensure_ascii=False, indent=2)
                self._log(f"  ✅ 评估结果已保存")

                # 生成HTML报告
                try:
                    eval_agent.generate_html_report('outputs/evaluation/feature_evaluation_report.html')
                    self._log(f"  ✅ HTML报告已生成")
                except Exception as e:
                    self._log(f"  ⚠ HTML报告生成失败: {e}")

                self._mass_passed = passed
                self._mass_passed_count = passed_count
                self._mass_total = total

                self.data_flow.register_execution(
                    agent_name='feature_evaluation',
                    inputs={'features_calculator': 'features_calculator_v2.py', 'reference_distributions': 'reference_distributions.json'},
                    outputs={'passed_features': 'outputs/evaluation/passed_features.json', 'report': 'outputs/evaluation/feature_evaluation_report.html'},
                    metadata={'total': total, 'passed': passed_count, 'failed': total - passed_count}
                )
                self._update_state('feature_evaluation', 'feature_evaluation_completed', next_step='feature_deployment')

            # ---- Step 4: 部署 ----
            if 'feature_deployment' not in self.state['completed_steps']:
                self._log("\n【步骤4/5】特征部署")
                deployment_agent = FeatureDeploymentAgent()
                deployment_agent.run()
                self._log("  ✅ 部署完成")

                self.data_flow.register_execution(
                    agent_name='feature_deployment',
                    inputs={'passed_features': 'outputs/evaluation/passed_features.json', 'code': 'features_calculator_v2.py'},
                    outputs={'deployment_package': 'outputs/deployment/v23/'},
                    metadata={'version': 'v23'}
                )
                self._update_state('feature_deployment', 'feature_deployment_completed', next_step='feedback_aggregation')

            # ---- Step 5: 反馈聚合 ----
            if 'feedback_aggregation' not in self.state['completed_steps']:
                self._log("\n【步骤5/5】反馈聚合")
                self._accumulate_passed_features()

                # 读取累计总数
                acc_path = 'outputs/evaluation/accumulated_passed_features.json'
                if os.path.exists(acc_path):
                    with open(acc_path) as f:
                        acc = json.load(f)
                    total_passed = acc.get('total_passed', 0)
                else:
                    total_passed = self._mass_passed_count

                self.data_flow.register_execution(
                    agent_name='feedback_aggregation',
                    inputs={'passed_features': 'outputs/evaluation/passed_features.json', 'accumulated': 'accumulated_passed_features.json'},
                    outputs={'accumulated_passed': acc_path},
                    metadata={'total_accumulated': total_passed}
                )
                self._update_state('feedback_aggregation', 'all_completed', next_step='completed')

            # Ensure total_passed is available even if feedback_aggregation was already completed
            try:
                _tmp = total_passed
            except NameError:
                try:
                    total_passed = self._mass_passed_count
                except AttributeError:
                    total_passed = 0

            # 完成
            self.state['status'] = 'completed'
            self.state['end_time'] = datetime.now().isoformat()
            self._save_state()

            self._log("\n" + "=" * 80)
            self._log("批量生产完成！")
            try:
                self._log(f"  总特征: {self._mass_total}")
                self._log(f"  通过: {self._mass_passed_count} ({self._mass_passed_count/self._mass_total*100:.1f}%)")
            except (AttributeError, ZeroDivisionError):
                # 当特征评估步骤已在之前完成时，从保存的passed_features读取
                _pf_path = 'outputs/evaluation/passed_features.json'
                if os.path.exists(_pf_path):
                    with open(_pf_path) as _f:
                        _pf_data = json.load(_f)
                    pf_items = _pf_data.get('passed_features', _pf_data) if isinstance(_pf_data, dict) else _pf_data
                    saved_total = _pf_data.get('total_features', len(pf_items)) if isinstance(_pf_data, dict) else len(pf_items)
                    saved_passed = sum(1 for f in pf_items if isinstance(f, dict) and f.get('status') == 'passed')
                else:
                    saved_total = self._mass_total
                    saved_passed = self._mass_passed_count
                self._log(f"  总特征: {saved_total}")
                self._log(f"  通过: {saved_passed} ({saved_passed/saved_total*100:.1f}%)")
                self._mass_total = saved_total
                self._mass_passed_count = saved_passed
            self._log(f"  累计通过: {total_passed}")
            self._log("=" * 80)

            return total_passed >= 300

        except Exception as e:
            self._log(f"\n❌ 批量生产出错: {str(e)}")
            import traceback
            traceback.print_exc()
            self.state['status'] = 'error'
            self.state['error'] = str(e)
            self._save_state()
            return False

    def _run_data_analysis(self) -> bool:
        """运行数据分析Agent"""
        self._log("  开始数据分析...")
        self._log("  ✅ 数据分析完成（使用已有分类结果）")
        return True

    def _run_feature_development(self) -> bool:
        """运行特征开发Agent（合并设计+工程+self-review）"""
        self._log("  开始特征开发（三阶段风险驱动框架 + 代码生成 + self-review）...")

        try:
            # 特征开发Agent已内置IV/PSI反馈加载和self-review
            result = self.development_agent.run()
            if not result:
                self._log(f"  ⚠️ development_agent.run() 返回 False (features={len(self.development_agent.features)}, code={'有' if self.development_agent.generated_code else '无'})")
                return False

            # 注册数据流
            self.data_flow.register_execution(
                agent_name='feature_development',
                inputs={
                    'fdc_variables': 'FDC4710变量.xlsx',
                    'app_classification': 'outputs/app_analysis/classification_complete_11850.json',
                    'iv_psi_feedback': 'outputs/evaluation/iv_psi_feedback_r*.json'
                },
                outputs={
                    'feature_design_doc': 'outputs/feature_design/feature_design_doc.json',
                    'features_calculator': 'outputs/feature_code/features_calculator_v2.py',
                    'phase3_template_system': 'outputs/feature_design/stepwise/phase3_template_system.json',
                },
                metadata={
                    'status': 'completed',
                    'method': 'stepwise_risk_driven_with_codegen',
                    'self_review_passed': self.development_agent.self_review_passed,
                    'total_features': len(self.development_agent.features)
                }
            )

            self._log(f"  ✅ 特征开发完成（{len(self.development_agent.features)}个特征, "
                       f"self-review: {'通过' if self.development_agent.self_review_passed else '需关注'}）")
            return True

        except Exception as e:
            self._log(f"  ❌ 特征开发失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _run_feature_evaluation(self) -> bool:
        """运行特征评估Agent"""
        self._log("  开始特征评估...")

        try:
            code_file = self.data_flow.get_latest_output(
                'features_calculator',
                'outputs/feature_code/features_calculator_v2.py'
            )

            short_url_file = '0421全样本短链.txt'
            labels_excel = '印尼模型分_2026_04_21_建模样本aiagent.xlsx'
            sample_size = 2105  # 本地加载全部2105个样本（原HTTP方式只能采~500条）

            self.evaluation_agent.run(
                code_path=code_file,
                short_url_file=short_url_file,
                labels_excel=labels_excel,
                sample_size=sample_size,
                oot_ratio=0.2,
                use_local=True,
                data_dir='data/all_samples'
            )

            self.data_flow.register_execution(
                agent_name='feature_evaluation',
                inputs={
                    'features_calculator': code_file,
                    'short_urls': short_url_file,
                    'labels': labels_excel
                },
                outputs={
                    'evaluation_report': 'outputs/evaluation/feature_evaluation_report.html',
                    'passed_features': 'outputs/evaluation/passed_features.json'
                },
                metadata={'status': 'completed', 'sample_size': sample_size}
            )

            self._log("  ✅ 特征评估完成")
            self._log(f"     报告: outputs/evaluation/feature_evaluation_report.html")
            return True

        except Exception as e:
            self._log(f"  ❌ 特征评估失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _run_feedback_aggregation(self) -> bool:
        """聚合IV/PSI评估结果为结构化反馈"""
        self._log("  聚合IV/PSI评估结果...")

        try:
            # 1. 加载通道1模板映射（获取template_id→名称/维度映射）
            template_map = {}
            db = SessionLocal()
            try:
                for t in list_templates(db, status=ACTIVE_STATUS):
                    template_map[t.template_id] = {
                        'template_name': t.template_name,
                        'template_name_cn': t.template_name_cn or '',
                        'dimension': t.dimension.dimension_code if t.dimension else '',
                        'channel': 'channel1'
                    }
            finally:
                db.close()

            # 2. 构建特征名→template_id映射表（从特征设计文档中读取）
            design_doc_path = 'outputs/feature_design/feature_design_doc.json'
            feature_template_map = {}
            if os.path.exists(design_doc_path):
                with open(design_doc_path, 'r', encoding='utf-8') as f:
                    doc = json.load(f)
                for feat in doc.get('features', []):
                    fname = feat.get('feature_name', '')
                    tid = feat.get('template_id', '')
                    if fname and tid:
                        feature_template_map[fname] = tid

            # 3. 读取评估结果
            passed_features = []
            failed_features = []

            passed_path = 'outputs/evaluation/passed_features.json'
            if os.path.exists(passed_path):
                with open(passed_path, 'r', encoding='utf-8') as f:
                    passed_data = json.load(f)
                passed_features = passed_data.get('passed_features', [])
                failed_features = passed_data.get('failed_features', [])
                if not failed_features:
                    self._log("  从特征设计文档推断未评估特征...")
                    if os.path.exists(design_doc_path):
                        with open(design_doc_path, 'r', encoding='utf-8') as f:
                            doc = json.load(f)
                        all_feature_names = {f['feature_name'] for f in doc.get('features', [])}
                        passed_names = {f.get('name', f.get('feature_name', '')) for f in passed_features}
                        self._log(f"     设计文档{len(all_feature_names)}个特征，已评估{len(passed_features)}个")

            # 4. 按template_id聚合
            template_groups = {}
            for f in passed_features:
                name = f.get('name', f.get('feature_name', ''))
                tid = feature_template_map.get(name) or self._guess_template_id(name)
                if tid not in template_groups:
                    template_groups[tid] = {'passed': [], 'failed': []}
                template_groups[tid]['passed'].append(f)

            for f in failed_features:
                name = f.get('name', f.get('feature_name', ''))
                tid = feature_template_map.get(name) or self._guess_template_id(name)
                if tid not in template_groups:
                    template_groups[tid] = {'passed': [], 'failed': []}
                template_groups[tid]['failed'].append(f)

            # 5. 构建反馈结构
            template_feedback = []
            for tid in sorted(template_groups.keys()):
                group = template_groups[tid]
                passed = group['passed']
                failed = group['failed']

                tmpl_info = template_map.get(tid, {})
                passed_ivs = [p.get('iv', 0) for p in passed if p.get('iv') is not None]
                passed_psis = [p.get('psi', 0) for p in passed if p.get('psi') is not None]

                entry = {
                    'template_id': tid,
                    'template_name': tmpl_info.get('template_name', ''),
                    'template_name_cn': tmpl_info.get('template_name_cn', ''),
                    'channel': tmpl_info.get('channel', 'channel1'),
                    'total_features': len(passed) + len(failed),
                    'passed': {
                        'count': len(passed),
                        'feature_names': [f.get('name', f.get('feature_name', '')) for f in passed],
                        'avg_iv': round(sum(passed_ivs) / len(passed_ivs), 4) if passed_ivs else 0,
                        'avg_psi': round(sum(passed_psis) / len(passed_psis), 4) if passed_psis else 0,
                        'iv_range': [round(min(passed_ivs), 4), round(max(passed_ivs), 4)] if passed_ivs else [0, 0]
                    } if passed else {'count': 0, 'feature_names': []},
                    'failed': {
                        'count': len(failed),
                        'reasons': [
                            {
                                'name': f.get('name', f.get('feature_name', '')),
                                'iv': f.get('iv', 0),
                                'psi': f.get('psi', 0),
                                'coverage': f.get('coverage', 0)
                            }
                            for f in failed
                        ]
                    } if failed else {'count': 0, 'reasons': []}
                }
                template_feedback.append(entry)

            # 6. 生成summary patterns
            summary_patterns = self._generate_summary_patterns(template_feedback)

            feedback = {
                'round': self.current_round,
                'timestamp': datetime.now().isoformat(),
                'total_features': sum(tf['total_features'] for tf in template_feedback),
                'passed_count': sum(tf['passed']['count'] for tf in template_feedback),
                'failed_count': sum(tf['failed']['count'] for tf in template_feedback),
                'template_feedback': template_feedback,
                'summary_patterns': summary_patterns
            }

            # 7. 保存
            os.makedirs('outputs/evaluation', exist_ok=True)
            fb_path = f'outputs/evaluation/iv_psi_feedback_r{self.current_round}.json'
            with open(fb_path, 'w', encoding='utf-8') as f:
                json.dump(feedback, f, ensure_ascii=False, indent=2)

            self._log(f"  ✅ IV/PSI反馈已保存: {fb_path}")
            self._log(f"     通过: {feedback['passed_count']}个, 失败: {feedback['failed_count']}个, "
                       f"本轮ID: round_{self.current_round}")
            return True

        except Exception as e:
            self._log(f"  ⚠️ 反馈聚合异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _aggregate_by_template(self, passed_list: List, failed_list: List, template_map: Dict) -> List:
        """按模板聚合特征评估结果"""
        from collections import defaultdict

        # 简化：根据特征名的前缀推测模板
        template_groups = defaultdict(lambda: {'passed': [], 'failed': []})

        # 把特征名映射到模板ID的简化逻辑
        # 实际应该从特征设计文档获取template_id映射
        for f in passed_list:
            name = f.get('name', '')
            tid = self._guess_template_id(name)
            template_groups[tid]['passed'].append(f)

        for f in failed_list:
            name = f.get('name', '')
            tid = self._guess_template_id(name)
            template_groups[tid]['failed'].append(f)

        feedback = []
        for tid, group in template_groups.items():
            passed = group['passed']
            failed = group['failed']

            tmpl_info = template_map.get(tid, {})
            passed_ivs = [p.get('iv', 0) for p in passed if p.get('iv') is not None]
            passed_psis = [p.get('psi', 0) for p in passed if p.get('psi') is not None]

            entry = {
                'template_id': tid,
                'template_name': tmpl_info.get('template_name', ''),
                'channel': tmpl_info.get('channel', 'channel1'),
                'total_features': len(passed) + len(failed),
                'passed': {
                    'count': len(passed),
                    'feature_names': [p.get('name', '') for p in passed],
                    'avg_iv': round(sum(passed_ivs) / len(passed_ivs), 4) if passed_ivs else 0,
                    'avg_psi': round(sum(passed_psis) / len(passed_psis), 4) if passed_psis else 0,
                    'iv_range': [round(min(passed_ivs), 4), round(max(passed_ivs), 4)] if passed_ivs else [0, 0]
                } if passed else {'count': 0, 'feature_names': []},
                'failed': {
                    'count': len(failed),
                    'feature_names': [f.get('name', '') for f in failed],
                    'reasons': [
                        {
                            'name': f.get('name', ''),
                            'iv': f.get('iv', 0),
                            'psi': f.get('psi', 0),
                            'coverage': f.get('coverage', 0)
                        }
                        for f in failed
                    ]
                } if failed else {'count': 0, 'feature_names': []}
            }
            feedback.append(entry)

        return feedback

    def _guess_template_id(self, feature_name: str) -> str:
        """从特征名推测模板ID

        根据特征名的语义前缀匹配通道1的15个DSL模板。
        这是对特征设计文档中缺失template_id字段的降级方案。
        """
        name = feature_name.lower()

        # 维度一：存量 (T001-T003)
        # distinct/unique 前缀优先匹配 T002（如 distinct_fdc_institution_90d）
        if name.startswith('distinct_') or name.startswith('unique_'):
            return 'T002'
        if name.startswith('count_') or name.startswith('num_') or name.startswith('total_'):
            if name.startswith('decayed_sum_') or 'decay' in name or 'weight' in name:
                return 'T003'
            return 'T001'
        if name.startswith('decayed_sum_') or name.startswith('decay_'):
            return 'T003'

        # 维度二：结构 (T004-T006)
        # pct_rank 必须在 pct_ 前检查
        if name.startswith('pct_rank') or name.startswith('percentile') or name.startswith('rank_'):
            return 'T010'
        if name.startswith('ratio_') or name.startswith('prop_') or name.startswith('pct_'):
            return 'T004'
        if name.startswith('entropy') or name.startswith('gini') or name.startswith('diversity'):
            return 'T005'
        if name.startswith('overlap') or name.startswith('jaccard') or name.startswith('intersection'):
            return 'T006'

        # 维度五：一致性 (T013-T015) — 在变化维度前检查,避免 _vs_ 误匹配
        if name.startswith('declared') or name.startswith('income_gap') or ('_vs_actual' in name):
            return 'T013'
        if name.startswith('discrepancy') or name.startswith('mismatch') or name.startswith('cross_source'):
            return 'T014'
        if name.startswith('cluster') or name.startswith('identity_') or name.startswith('shared_'):
            return 'T015'

        # 维度三：变化 (T007-T009)
        if name.startswith('period_') or name.startswith('change_') or ('_vs_' in name):
            return 'T007'
        if name.startswith('trend') or name.startswith('slope') or name.startswith('accel'):
            return 'T008'
        if name.startswith('spike') or name.startswith('surge') or name.startswith('burst'):
            return 'T009'

        # 维度四：定位 (T010-T012) — 剩余部分
        if name.startswith('zscore') or name.startswith('deviation') or name.startswith('std_'):
            return 'T011'
        if name.startswith('anomaly') or name.startswith('outlier') or name.startswith('isolation'):
            return 'T012'

        # 兜底
        return 'T999'

    def _generate_summary_patterns(self, template_feedback: List) -> List[str]:
        """生成经验总结"""
        patterns = []
        for tf in template_feedback:
            passed = tf.get('passed', {})
            failed = tf.get('failed', {})

            if passed.get('count', 0) == 0:
                patterns.append(f"{tf['template_id']}({tf.get('template_name', '?')}) 全量失败")
                continue

            avg_iv = passed.get('avg_iv', 0)
            avg_psi = passed.get('avg_psi', 0)

            if avg_iv >= 0.05:
                patterns.append(f"{tf['template_id']}({tf.get('template_name', '?')}) IV表现好(avg_iv={avg_iv})")
            elif avg_iv >= 0.02:
                patterns.append(f"{tf['template_id']}({tf.get('template_name', '?')}) IV达标(avg_iv={avg_iv})")
            else:
                patterns.append(f"{tf['template_id']}({tf.get('template_name', '?')}) IV偏低(avg_iv={avg_iv})")

            if avg_psi > 0.2:
                patterns.append(f"{tf['template_id']}({tf.get('template_name', '?')}) PSI需关注(avg_psi={avg_psi})")

        return patterns[:10]

    def _run_feature_deployment(self) -> bool:
        """运行特征部署Agent"""
        self._log("  开始特征部署...")
        try:
            self.deployment_agent.run(auto_deploy=False)
            self._log("  ✅ 特征部署完成")
            return True
        except Exception as e:
            self._log(f"  ❌ 特征部署失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_status(self) -> Dict:
        """获取当前流程状态"""
        return self.state

    def reset(self):
        """重置流程状态"""
        self.state = {
            'current_step': 'data_analysis',
            'completed_steps': [],
            'status': 'not_started',
            'start_time': None,
            'last_update': None
        }
        self._save_state()
        self.data_flow.registry = {'agent_executions': [], 'latest_outputs': {}}
        self.data_flow.save()
        self._log("流程状态已重置")
        self._log("数据流注册表已重置")


def main():
    """主入口函数"""
    import argparse

    parser = argparse.ArgumentParser(description='特征工程主协调Agent (v2.0) — 支持LLM迭代和批量生产两种模式')
    parser.add_argument('--mode', type=str,
                        choices=['llm', 'mass-produce'],
                        default='llm',
                        help='运行模式: llm=LLM多轮迭代(默认), mass-produce=确定性批量生产(单轮333个特征)')
    parser.add_argument('--start-from', type=str,
                        choices=['data_analysis', 'feature_development', 'feature_evaluation',
                                 'feedback_aggregation', 'feature_deployment',
                                 'mass_production', 'reference_computation'],
                        default=None,
                        help='从哪个步骤开始执行（支持断点续做）')
    parser.add_argument('--status', action='store_true',
                        help='查看当前流程状态')
    parser.add_argument('--reset', action='store_true',
                        help='重置流程状态')
    parser.add_argument('--rounds', type=int, default=1,
                        help='LLM模式的迭代轮数（每轮生成不同的参数组合，>1为多轮迭代模式）')

    args = parser.parse_args()

    orchestrator = FeatureOrchestrator()

    if args.status:
        status = orchestrator.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return

    if args.reset:
        orchestrator.reset()
        return

    if args.mode == 'mass-produce':
        orchestrator.run_mass_production()
        return

    success = orchestrator.run_full_pipeline(
        start_from_step=args.start_from,
        max_rounds=args.rounds
    )
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
