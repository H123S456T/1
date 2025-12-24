临床MDT智能模拟助手

一个基于多智能体系统的临床多学科会诊模拟平台，支持多种医学专科智能体协作讨论病例，提供专业的诊断和治疗建议。

🏥 项目简介

临床MDT智能模拟助手是一个创新的临床决策支持系统，通过模拟真实的多学科会诊（MDT）过程，整合多个医学专科智能体的专业意见，为临床医生提供全面的病例分析和治疗建议。

核心特性

• 多专科智能体协作：集成30+医学专科智能体，模拟真实MDT讨论

• 智能交互式讨论：支持用户实时介入和引导讨论方向

• 专业临床推理：基于循证医学原则提供诊断和治疗建议

• 多种导出格式：支持JSON、Word、HTML等多种结果导出格式

• 用户友好界面：提供命令行和Web两种交互界面

🚀 快速开始

环境要求

• Python 3.8+

• 支持的LLM后端：vLLM、OpenAI、DeepSeek、SiliconFlow、智谱AI等

安装步骤

1. 克隆项目
git clone <repository-url>
cd clinical-mdt-assistant


2. 安装依赖
pip install -r requirements.txt


3. 配置模型参数
# 创建模型配置文件
python -c "from utils.config import create_default_model_config; create_default_model_config()"


4. 修改配置文件
编辑 config/model_config.json，配置您的LLM API端点：
{
  "model_config": {
    "engine": "vllm",
    "api_base": "http://your-api-endpoint/v1",
    "model_name": "your-model-name"
  }
}


5. 启动系统
# 命令行界面
python clinical_cli.py

# Web界面
streamlit run web_interface.py


📋 系统功能

核心功能模块

1. 用户认证管理

• 用户注册、登录、会话管理

• 权限控制和个性化设置

• 讨论历史记录管理

2. 智能体管理

• 内置专科智能体：30+医学专科，涵盖内科、外科、医技科等

• 自定义智能体：支持用户创建个性化智能体

• 智能体注册表：统一的智能体管理和配置

3. 多智能体讨论引擎

• 轮次式讨论：多轮智能体交互讨论

• 实时用户介入：支持提问、补充信息、改变焦点等介入方式

• 逻辑一致性检查：确保讨论过程的逻辑严谨性

• 决策汇总：自动生成综合诊断和治疗方案

4. 数据存储与导出

• 讨论记录存储：JSON格式存储完整讨论过程

• 多种导出格式：Word、HTML、JSON、TXT等

• 数据备份恢复：支持数据备份和恢复功能

支持的专科智能体

类别 包含专科

内科 心内科、肾内科、内分泌科、呼吸科、消化科、血液科、风湿免疫科、感染科等

外科 普外科、胸外科、神经外科、骨科、血管外科、泌尿外科、妇产科等

医技科 影像科、病理科、放射科、麻醉科等

其他 重症医学科、急诊科、儿科、皮肤科、眼科、耳鼻喉科等

🛠 使用方法

命令行界面使用

1. 用户认证
# 启动系统后选择登录或注册
临床MDT智能模拟助手 - 用户认证
1. 用户登录
2. 用户注册
3. 退出系统


2. 开始新讨论
# 主菜单选择"开始新的讨论"
步骤1: 选择参与讨论的智能体（可多选）
步骤2: 输入病历信息（主诉、现病史、辅助检查等）
步骤3: 输入讨论问题
步骤4: 配置讨论参数（轮数、用户参与模式等）
步骤5: 开始自动讨论


3. 讨论过程中的介入
# 在讨论过程中，系统会提示用户介入选项：
💡💡💡💡 是否介入讨论？
选项: 1-向智能体提问, 2-向所有提问, 3-补充信息, 4-跳过轮次, 5-终止讨论


Web界面使用

1. 访问系统
streamlit run web_interface.py
# 在浏览器中访问 http://localhost:8501


2. 主要功能区域
• 控制面板：系统概览和快速操作

• 智能体管理：选择和管理参与讨论的智能体

• 病历输入：结构化病历信息输入界面

• 实时讨论：可视化讨论过程展示

• 结果分析：多维度的讨论结果分析

⚙️ 配置说明

模型配置

系统支持多种LLM后端，配置示例：
{
  "model_config": {
    "engine": "vllm",
    "api_base": "http://127.0.0.1:8000/v1",
    "model_name": "Qwen2-7B-Chat",
    "temperature": 0.3,
    "max_tokens": 100000,
    "timeout": 60
  }
}


讨论参数配置

• default_rounds：默认讨论轮数（1-10）

• enable_user_intervention：是否启用用户介入

• auto_save：是否自动保存讨论记录

• export_format：默认导出格式（json、docx、html等）

🏗 系统架构

核心模块


clinical-mdt-assistant/
├── auth/                 # 认证模块
│   ├── user_manager.py   # 用户管理
│   └── session_handler.py # 会话管理
├── agents/               # 智能体模块
│   ├── base_agent.py     # 基础智能体类
│   ├── specialty_agents.py # 专科智能体
│   ├── custom_agent.py   # 自定义智能体
│   └── agent_registry.py # 智能体注册表
├── discussion/           # 讨论引擎
│   ├── discussion_engine.py # 讨论引擎核心
│   └── user_interaction.py  # 用户交互管理
├── storage/              # 数据存储
│   ├── discussion_storage.py # 讨论记录存储
│   └── user_data.py      # 用户数据管理
├── interface/            # 用户界面
│   ├── cli_interface.py  # 命令行界面
│   └── web_interface.py  # Web界面
├── utils/                # 工具模块
│   ├── config.py         # 配置管理
│   ├── logger.py         # 日志管理
│   └── error_handler.py  # 错误处理
└── data/                 # 数据目录
    ├── users/            # 用户数据
    ├── discussions/      # 讨论记录
    └── exports/          # 导出文件


数据流图


用户输入 → 认证验证 → 智能体选择 → 病历输入 → 多轮讨论 → 结果生成 → 导出存储
    ↑          ↓           ↓          ↓         ↓          ↓         ↓
界面层 ←── 会话管理 ←─ 智能体管理 ←─ 数据验证 ←─ 讨论引擎 ←─ 决策汇总 ←─ 存储管理


🔧 开发指南

添加新的专科智能体

1. 在智能体注册表中添加配置
# 在agents/agent_registry.py的builtin_agents中添加
"新专科名称": {
    "specialty": "新专科名称",
    "description": "专科描述",
    "prompt": "专业提示词",
    "is_builtin": True,
    "category": "内科"
}


2. 创建专科智能体类（可选）
from agents.base_agent import BaseAgent

class NewSpecialtyAgent(BaseAgent):
    def __init__(self, args, specialty, agent_name, logger=None):
        super().__init__(args, specialty, system_prompt, agent_name, logger)
    
    def analyze_case(self, medical_record, discussion_history):
        # 实现专科特定的分析逻辑
        pass


自定义导出格式

1. 在DiscussionStorage类中添加导出方法
def export_to_custom_format(self, discussion_data, export_path=None):
    # 实现自定义导出逻辑
    pass


2. 更新导出选项
# 在clinical_cli.py中更新export_formats
export_formats = ["json", "docx", "html", "custom_format"]


🐛 故障排除

常见问题

1. 模型连接失败

错误：API调用失败
解决：检查api_base配置，确保LLM服务正常运行


2. 智能体初始化失败

错误：专科智能体'xxx'不存在
解决：检查agent_registry中的配置，确保专科名称正确


3. 讨论过程中断

错误：讨论被用户中断
解决：检查用户介入配置，或重新开始讨论


日志查看

系统日志保存在logs/目录下，可通过以下方式查看：
tail -f logs/clinical_system_*.log


📊 性能优化

讨论性能优化

• 调整max_rounds参数控制讨论轮数

• 使用temperature参数控制回答的创造性

• 配置timeout参数避免长时间等待

内存优化

• 定期清理临时文件和缓存

• 使用分页加载历史记录

• 配置自动备份和清理策略

🤝 贡献指南


开发环境设置

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate      # Windows

# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
python -m pytest tests/


📄 许可证



🙏 致谢

感谢所有为本项目做出贡献的开发者，以及提供医学专业指导的临床专家。

📞 联系方式

• 项目主页：

• 问题反馈：

• 邮箱联系：

注意：本系统旨在辅助临床决策，不能替代专业医生的诊断和治疗建议。在使用系统生成的建议时，请结合临床实际情况和专业判断。