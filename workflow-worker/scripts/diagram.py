#!/usr/bin/env python3
"""
Workflow Worker - DDD 架构可视化

生成架构层次图
"""

ARCHITECTURE_DIAGRAM = """
┌─────────────────────────────────────────────────────────────────┐
│                        Workflow Worker                          │
│                    (Video Inspection System)                    │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Interfaces  │    │Applications  │    │   Services   │
│     Layer    │───▶│    Layer     │───▶│    Layer     │
│              │    │              │    │              │
│ • API        │    │ • Jobs       │    │ • AI Service │
│ • CLI        │    │ • Workflows  │    │ • Media      │
│ • Events     │    │ • Use Cases  │    │              │
└──────────────┘    └──────┬───────┘    └──────┬───────┘
                           │                    │
                           │         ┌──────────┘
                           │         │
                           ▼         ▼
                    ┌──────────────┐
                    │    Domain    │
                    │    Layer     │
                    │              │
                    │ • Entities   │
                    │ • Value Obj  │
                    │ • Repositories│
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │Infrastructure│
                    │    Layer     │
                    │              │
                    │ • Media      │
                    │ • External   │
                    │ • Storage    │
                    └──────────────┘
                           ▲
                           │
                    ┌──────┴───────┐
                    │    Shared    │
                    │   Module     │
                    │              │
                    │ • Config     │
                    │ • Logging    │
                    │ • Utils      │
                    └──────────────┘

All layers depend on Shared Module.
Dependencies flow downward only.
"""

LAYER_MAPPING = """
旧结构 → 新结构映射
═══════════════════════════════════════════════════════════

旧路径                          新路径
───────────────────────────────────────────────────────────
engine/models/          →    domain/entities/
engine/service/         →    services/ai/
framework/modules/      →    applications/jobs/
framework/media/        →    infrastructure/media/
framework/client/       →    infrastructure/external/
apis/                   →    interfaces/api/
engine/utils/           →    shared/utils/
engine/config.py        →    shared/config/
engine/logging.py       →    shared/logging/

═══════════════════════════════════════════════════════════
"""

PRINCIPLES = """
DDD 核心原则
═══════════════════════════════════════════════════════════

1. 依赖方向
   ✅ Interfaces → Applications → Services → Domain
   ✅ Infrastructure implements Domain interfaces
   ✅ All layers → Shared
   ❌ Domain 依赖任何层

2. 分层职责
   📦 Domain      - 核心业务逻辑（无依赖）
   🔧 Services    - 业务服务编排（依赖 Domain）
   📋 Applications - 用例和工作流（依赖 Domain + Services）
   🌐 Interfaces  - API 和 CLI（依赖 Applications）
   ⚙️ Infrastructure - 技术实现（依赖 Domain）
   🛠️ Shared      - 工具和配置（被所有层使用）

3. 关键优势
   • 清晰的职责划分
   • 易于测试
   • 便于维护
   • 支持并行开发

═══════════════════════════════════════════════════════════
"""

def main():
    print("=" * 65)
    print("  Workflow Worker - DDD Architecture Overview")
    print("=" * 65)
    print()
    print(ARCHITECTURE_DIAGRAM)
    print()
    print(LAYER_MAPPING)
    print()
    print(PRINCIPLES)

if __name__ == "__main__":
    main()
