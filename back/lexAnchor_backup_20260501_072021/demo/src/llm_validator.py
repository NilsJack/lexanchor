import os
import json
import yaml
import concurrent.futures
from typing import List, Dict, Any, Optional
import requests

class LexSemanticValidator:
    """
    军火库中控裁判：根据 arsenal.yaml 的配置，动态选择、降级和调用 LLM。
    支持 Tier 优先级排序与自动失败重试。
    """
    def __init__(self, projects_root: str, backend_mode: str = "local"):
        self.projects_root = projects_root
        self.backend_mode = str(backend_mode or "local").strip().lower() or "local"
        self.arsenal_path = os.path.abspath(os.path.join(projects_root, "../../../arsenal.yaml"))
        self.proxies = {
            "http": "http://127.0.0.1:51809",
            "https": "http://127.0.0.1:51809"
        }
        self.model_pool = self._load_active_pool()

    def _load_active_pool(self) -> List[Dict[str, Any]]:
        """加载并按 Tier 排序活跃模型池"""
        if not os.path.exists(self.arsenal_path):
            raise FileNotFoundError(f"未找到军火库配置文件: {self.arsenal_path}")
            
        with open(self.arsenal_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        active_keys = [k for k in data.get("keys", []) if k.get("active")]
        active_keys = self._filter_pool_by_backend(active_keys)
        
        # 权重映射
        tier_weight = {"X": 100, "S": 80, "A": 60, "B": 40, "0": 20}
        active_keys.sort(key=lambda x: tier_weight.get(str(x.get("tier")), 0), reverse=True)
        
        print(f"[+] 军火库就绪，当前可用梯队: {[k['id'] for k in active_keys]}")
        return active_keys

    def _filter_pool_by_backend(self, active_keys: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.backend_mode == "network":
            preferred = [k for k in active_keys if k.get("id") == "google_gemini_3_flash_preview" or k.get("model") == "gemini-3-flash-preview"]
            return preferred or [k for k in active_keys if k.get("provider") == "google_studio"]
        preferred = [k for k in active_keys if k.get("id") == "ollama_gemma4_e4b" or k.get("model") == "gemma4:e4b"]
        return preferred or [k for k in active_keys if k.get("provider") == "ollama"]

    def validate_findings(self, findings: List[Dict[str, Any]], full_text: str) -> List[Dict[str, Any]]:
        semantic_tasks = [r for r in findings if r.get("requires_llm")]
        if not semantic_tasks:
            return findings

        print(f"[*] 启动军火库集群研判，共计 {len(semantic_tasks)} 项任务...")
        
        validated_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_task = {executor.submit(self._check_with_fallback, task): task for task in semantic_tasks}
            for future in concurrent.futures.as_completed(future_to_task):
                try:
                    res = future.result()
                    if res:
                        validated_results.append(res)
                except Exception as e:
                    print(f"[-] 关键研判异常: {e}")

        final_findings = [f for f in findings if not f.get("requires_llm")]
        final_findings.extend(validated_results)
        return final_findings

    def _check_with_fallback(self, task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """尝试模型池中的所有模型，直到成功或池尽"""
        for config in self.model_pool:
            try:
                res = self._call_provider(task, config)
                if res is not None:
                    return res
            except Exception as e:
                print(f"[-] 模型 {config['id']} 罢工: {e}，尝试下一顺位...")
                continue
        return None

    def _call_provider(self, task: Dict[str, Any], config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        provider = config.get("provider")
        if provider == "google_studio":
            return self._call_google(task, config)
        elif provider in ["openai_generic", "together", "lm_studio"]:
            return self._call_openai_compatible(task, config)
        elif provider == "ollama":
            return self._call_ollama(task, config)
        return None

    def _call_google(self, task: Dict[str, Any], config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{config['model']}:generateContent?key={config['api_key']}"
        payload = {
            "contents": [{"parts": [{"text": self._build_prompt(task)}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.1}
        }
        response = requests.post(url, json=payload, proxies=self.proxies, timeout=30)
        res_data = response.json()
        if "candidates" not in res_data:
            raise ValueError(f"Google 响应异常: {res_data}")
        content = res_data["candidates"][0]["content"]["parts"][0]["text"]
        return self._parse_llm_json(task, content)

    def _call_openai_compatible(self, task: Dict[str, Any], config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        url = f"{config['base_url'].rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}
        payload = {
            "model": config["model"],
            "messages": [{"role": "user", "content": self._build_prompt(task)}],
            "temperature": 0,
            "response_format": {"type": "json_object"}
        }
        response = requests.post(url, headers=headers, json=payload, proxies=self.proxies if "localhost" not in url else None, timeout=60)
        res_data = response.json()
        content = res_data["choices"][0]["message"]["content"]
        return self._parse_llm_json(task, content)

    def _call_ollama(self, task: Dict[str, Any], config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        url = "http://localhost:11434/api/chat"
        payload = {
            "model": config["model"],
            "messages": [{"role": "user", "content": self._build_prompt(task)}],
            "stream": False,
            "format": "json"
        }
        response = requests.post(url, json=payload, timeout=60)
        content = response.json()["message"]["content"]
        return self._parse_llm_json(task, content)

    def _parse_llm_json(self, task: Dict[str, Any], content: str) -> Optional[Dict[str, Any]]:
        llm_output = json.loads(content)
        if llm_output.get("is_risk"):
            task["is_validated"] = True
            task["reason"] = llm_output.get("reason")
            task["evidence_spans"] = llm_output.get("evidence_spans", [])
            task["confidence"] = llm_output.get("confidence", 1.0)
            return task
        return None

    def _build_prompt(self, task: Dict[str, Any]) -> str:
        return f"""你是一位资深的法律审查专家。请针对以下合同片段，判断是否命中指定的【风险规则】。

### 风险规则详情
名称：{task['rule_id']}
风险描述：{task['recommendation']}

### 待审查合同片段
\"\"\"
{task['context']}
\"\"\"

### 任务要求
1. 判断该片段是否真正构成了上述风险 (is_risk: true/false)。
2. 如果是风险，请给出判定理由 (reason)。
3. **证据提取**：从原文中摘取支持你判断的核心短语 (evidence_spans)，必须是原文中的精确字符串。

### 输出格式 (JSON)
{{
  "is_risk": bool,
  "reason": "字符串",
  "confidence": 0.0-1.0,
  "evidence_spans": [
    {{ "text": "原文精确片段", "importance": "core" }}
  ]
}}
"""

if __name__ == "__main__":
    v = LexSemanticValidator("workspace/TOOLS/LexAnchor")
    print("Multi-Model Arsenal Engine Ready.")
