#!/usr/bin/env python3
"""
临床MDT智能模拟助手 - 主入口文件
修复导入问题版本
"""

import argparse
import sys
import traceback
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="临床MDT智能模拟助手")
    
    # 模型配置参数
    parser.add_argument("--model", type=str, default="vllm",
                        choices=["vllm", "openai", "deepseek", "siliconflow", "zhipuai"],
                        help="使用的LLM后端")
    parser.add_argument("--llm_name", type=str, default="clinical-model",
                        help="具体的模型名称")
    parser.add_argument("--api_base", type=str, default="http://127.0.0.1:7778/v1",
                        help="LLM API地址")
    
    # 系统配置参数
    parser.add_argument("--debug", action="store_true",
                        help="启用调试模式")
    parser.add_argument("--log_level", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="日志级别")
    parser.add_argument("--data_dir", type=str, default="data",
                        help="数据存储目录")
    
    # 讨论配置参数
    parser.add_argument("--rounds", type=int, default=3,
                        help="默认讨论轮数")
    parser.add_argument("--max_rounds", type=int, default=10,
                        help="最大讨论轮数")
    parser.add_argument("--num_agents", type=int, default=3,
                        help="默认智能体数量")
    
    return parser.parse_args()

def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()
    
    try:
        print("启动临床多智能体讨论系统...")
        
        # 1. 导入基础模块
        print("加载基础模块...")
        
        # 导入用户管理器
        from auth.user_manager import UnifiedUserManager, get_user_manager
        print("✅ 用户管理器模块导入成功")
        
        # 2. 尝试导入CLI接口
        from interface.cli_interface import ClinicalCLI
        print("✅ CLI接口模块导入成功")
       
        # 3. 创建并运行CLI
        print("启动命令行界面...")

        cli = ClinicalCLI()  # 移除参数
        
        cli.run()
        
        print("✅ 系统正常退出")
        return 0
        
    except Exception as e:
        print(f"❌❌ 系统启动失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
if __name__ == "__main__":
    # 添加更详细的错误信息
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"未捕获的异常: {e}")
        traceback.print_exc()
        sys.exit(1)