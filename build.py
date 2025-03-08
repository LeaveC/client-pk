import os
import platform
import shutil
import subprocess
import sys
import argparse
from PyInstaller.__main__ import run
from pathlib import Path
from PIL import Image
import tempfile

def convert_ico_to_icns(ico_path):
    """将.ico文件转换为.icns文件"""
    if not os.path.exists(ico_path):
        print(f"错误：找不到图标文件 {ico_path}")
        return None
    
    try:
        # 创建临时目录
        with tempfile.TemporaryDirectory() as iconset_dir:
            iconset_path = os.path.join(iconset_dir, 'icon.iconset')
            os.makedirs(iconset_path)
            
            # 打开ICO文件
            img = Image.open(ico_path)
            
            # 转换为PNG并保存不同尺寸
            sizes = [(16,16), (32,32), (64,64), (128,128), (256,256), (512,512)]
            for size in sizes:
                resized = img.resize(size, Image.Resampling.LANCZOS)
                resized.save(os.path.join(iconset_path, f'icon_{size[0]}x{size[0]}.png'))
                if size[0] <= 32:  # 对于小尺寸，也创建@2x版本
                    double_size = (size[0]*2, size[0]*2)
                    resized = img.resize(double_size, Image.Resampling.LANCZOS)
                    resized.save(os.path.join(iconset_path, f'icon_{size[0]}x{size[0]}@2x.png'))
            
            # 使用iconutil转换为icns
            icns_path = os.path.join(os.path.dirname(ico_path), 'icon.icns')
            subprocess.run(['iconutil', '-c', 'icns', iconset_path], check=True)
            
            if os.path.exists(icns_path):
                return icns_path
            return None
    except Exception as e:
        print(f"转换图标时出错：{e}")
        return None

def parse_args():
    parser = argparse.ArgumentParser(description='构建Cursor插件')
    parser.add_argument('--arch', choices=['arm64', 'x86_64'], help='目标架构 (arm64 或 x86_64)')
    return parser.parse_args()

def check_dependencies():
    try:
        import PyInstaller
        return True
    except ImportError:
        print("错误：未安装 PyInstaller")
        print("正在尝试安装 PyInstaller...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("PyInstaller 安装成功！")
            return True
        except subprocess.CalledProcessError:
            print("安装 PyInstaller 失败！")
            print("请手动运行: pip install pyinstaller")
            return False

def get_certifi_path():
    try:
        import certifi
        return os.path.join(os.path.dirname(certifi.__file__), 'cacert.pem')
    except Exception as e:
        print(f"警告：无法找到证书文件: {e}")
        return None

def build():
    args = parse_args()
    
    # 清理之前的构建
    dist_dir = Path("dist")
    build_dir = Path("build")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # 获取证书文件路径
    cert_path = get_certifi_path()
    if not cert_path:
        print("警告：未找到证书文件，将尝试使用系统证书")

    # 转换图标
    ico_path = os.path.join('assets', 'icon.ico')
    icns_path = convert_ico_to_icns(ico_path)
    if not icns_path:
        print("警告：图标转换失败，将使用默认图标")

    # 打包参数
    pyinstaller_args = [
        'main.py',
        '--name=Cursor插件',
        '--noconsole',
        '--onefile',
        f'--icon={icns_path if icns_path else ico_path}',
        '--runtime-tmpdir=.',
        '--add-data=.env:.',
        '--hidden-import=requests',
        '--hidden-import=sqlalchemy',
        '--hidden-import=PySide6',
        '--hidden-import=PySide6.QtCore',
        '--hidden-import=PySide6.QtGui',
        '--hidden-import=PySide6.QtWidgets',
        '--hidden-import=dotenv',
        '--hidden-import=jose',
        '--hidden-import=passlib',
        '--hidden-import=certifi',
        '--clean',
        '--strip',
        '--noupx',
        '--disable-windowed-traceback',
        '--log-level=ERROR',
    ]

    # 添加证书文件
    if cert_path:
        if sys.platform.startswith('win'):
            pyinstaller_args.append(f'--add-data={cert_path};certifi')
        else:
            pyinstaller_args.append(f'--add-data={cert_path}:certifi')

    # 根据操作系统添加特定参数
    if sys.platform.startswith('win'):
        pyinstaller_args.extend([
            '--version-file=version.txt',
            '--manifest=manifest.xml',
        ])
    elif sys.platform.startswith('darwin'):
        # 获取目标架构
        current_arch = platform.machine()
        target_arch = args.arch if args.arch else ('arm64' if current_arch == 'arm64' else 'x86_64')
        
        # 设置环境变量以支持交叉编译
        if current_arch == 'arm64' and target_arch == 'x86_64':
            print("正在配置x86_64交叉编译环境...")
            os.environ['ARCHFLAGS'] = '-arch x86_64'
            os.environ['MACOSX_DEPLOYMENT_TARGET'] = '10.15'
        
        pyinstaller_args.extend([
            f'--target-arch={target_arch}',
        ])
        
        print(f"目标架构: {target_arch}")
        if current_arch != target_arch:
            print(f"正在进行交叉编译: 从 {current_arch} 到 {target_arch}")

    # 执行打包
    run(pyinstaller_args)

if __name__ == '__main__':
    build() 