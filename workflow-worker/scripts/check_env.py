#!/usr/bin/env python3
"""
环境验证脚本
检查 Python 版本和已安装的依赖
"""
import sys
from pathlib import Path

def check_python_version():
    """检查 Python 版本"""
    print("🐍 Python 版本检查")
    version = sys.version_info
    print(f"   当前版本: {version.major}.{version.minor}.{version.micro}")

    if version.major == 3 and version.minor >= 13:
        print("   ✅ Python 版本符合要求 (>= 3.13)")
        return True
    else:
        print("   ⚠️  警告: 推荐使用 Python 3.13+")
        return False

def check_package(package_name, min_version=None, import_name=None):
    """检查包是否已安装"""
    if import_name is None:
        import_name = package_name

    try:
        module = __import__(import_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"   ✅ {package_name} {version}")
        return True
    except ImportError:
        print(f"   ❌ {package_name} 未安装")
        return False

def main():
    print("=" * 50)
    print("🔍 环境检查")
    print("=" * 50)
    print()

    # 检查 Python 版本
    python_ok = check_python_version()
    print()

    # 核心依赖
    print("📦 核心依赖")
    core_packages = [
        ("pydantic", "2.0.0", "pydantic"),
        ("requests", None, "requests"),
        ("aiohttp", None, "aiohttp"),
        ("dynaconf", None, "dynaconf"),
        ("tqdm", None, "tqdm"),
    ]
    core_ok = all(check_package(*pkg) for pkg in core_packages)
    print()

    # 可选依赖组
    print("📦 可选依赖")

    # gRPC
    print("   gRPC 和 Protobuf:")
    grpc_ok = all([
        check_package("grpcio", None, "grpc"),
        check_package("protobuf", "4.0.0", "google.protobuf"),
    ])
    print()

    # 媒体处理
    print("   媒体处理:")
    media_ok = all([
        check_package("numpy", "2.0.0", "numpy"),
        check_package("opencv-python", None, "cv2"),
        check_package("ffmpeg-python", None, "ffmpeg"),
    ])
    print()

    # 存储
    print("   存储:")
    storage_ok = check_package("minio", None, "minio")
    print()

    # 异步
    print("   异步支持:")
    async_ok = check_package("janus", None, "janus")
    print()

    # 数据库
    print("   数据库:")
    db_ok = check_package("psycopg2", None, "psycopg2")
    print()

    # Thrift
    print("   Thrift:")
    thrift_ok = all([
        check_package("thrift", None, "thrift"),
        check_package("thriftpy2", None, "thriftpy2"),
    ])
    print()

    # 工具
    print("   其他工具:")
    tools_ok = all([
        check_package("XlsxWriter", None, "xlsxwriter"),
        check_package("pypinyin", None, "pypinyin"),
        check_package("authlib", None, "authlib"),
    ])
    print()

    # 开发工具
    print("🔧 开发工具:")
    dev_ok = all([
        check_package("black", None, "black"),
        check_package("pylint", None, "pylint"),
    ])
    print()

    # 总结
    print("=" * 50)
    print("📊 总结")
    print("=" * 50)
    print(f"   ✅ 核心依赖: {'OK' if core_ok else 'FAILED'}")
    print(f"   ✅ gRPC: {'OK' if grpc_ok else 'NOT INSTALLED'}")
    print(f"   ✅ 媒体处理: {'OK' if media_ok else 'NOT INSTALLED'}")
    print(f"   ✅ 存储: {'OK' if storage_ok else 'NOT INSTALLED'}")
    print(f"   ✅ 异步: {'OK' if async_ok else 'NOT INSTALLED'}")
    print(f"   ✅ 数据库: {'OK' if db_ok else 'NOT INSTALLED'}")
    print(f"   ✅ Thrift: {'OK' if thrift_ok else 'NOT INSTALLED'}")
    print(f"   ✅ 工具: {'OK' if tools_ok else 'NOT INSTALLED'}")
    print(f"   ✅ 开发工具: {'OK' if dev_ok else 'NOT INSTALLED'}")
    print()

    if not core_ok:
        print("❌ 核心依赖缺失，请运行: uv sync")
        sys.exit(1)

    if not (grpc_ok or media_ok or storage_ok):
        print("⚠️  可选依赖未安装")
        print("   根据需要安装:")
        print("   ./scripts/install_deps.sh all")
        print("   或")
        print("   uv sync --all")

    print("✅ 环境检查完成！")

if __name__ == "__main__":
    main()
