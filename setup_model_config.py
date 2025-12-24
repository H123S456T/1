#!/usr/bin/env python3
"""
模型配置初始化脚本
"""

import json
import os
from pathlib import Path

def create_default_model_config():
    """创建默认的模型配置文件"""
    config = {
        "model_config": {
            "engine": "vllm",
            "api_base": "http://10.124.0.7:9001/v1",
            "model_name": "Qwen3-next",
            "temperature": 0.3,
            "max_tokens": 100000,
            "timeout": 60,
            "max_retries": 3
        },
        "available_models": [
            {
                "name": "vllm-local",
                "engine": "vllm",
                "api_base": "http://10.124.0.7:9001/v1",
                "model_name": "Qwen3-next",
                "description": "本地VLLM服务"
            },
            {
                "name": "deepseek-cloud",
                "engine": "deepseek", 
                "api_base": "https://api.deepseek.com/v1",
                "model_name": "deepseek-chat",
                "description": "DeepSeek云服务"
            }
        ]
    }
    
    # 确保目录存在
    os.makedirs("config", exist_ok=True)
    
    with open("config/model_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print("✅ 默认模型配置文件已创建: config/model_config.json")
    print("📋 请根据您的环境修改API端点配置")

if __name__ == "__main__":
    create_default_model_config()