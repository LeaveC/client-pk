from PIL import Image
import os

def convert_ico_to_icns():
    # 创建必要的目录
    if not os.path.exists('assets/icon.iconset'):
        os.makedirs('assets/icon.iconset')
    
    # 打开 ICO 文件
    try:
        img = Image.open('assets/icon.ico')
    except Exception as e:
        print(f"无法打开图标文件: {e}")
        return False
    
    # 定义所需的尺寸
    sizes = [16, 32, 64, 128, 256, 512]
    
    # 为每个尺寸创建图像
    for size in sizes:
        # 普通分辨率
        icon_name = f'icon_{size}x{size}.png'
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(f'assets/icon.iconset/{icon_name}')
        
        # 高分辨率（@2x）
        if size <= 256:  # 512@2x 太大了，不需要
            icon_name = f'icon_{size}x{size}@2x.png'
            resized = img.resize((size*2, size*2), Image.Resampling.LANCZOS)
            resized.save(f'assets/icon.iconset/{icon_name}')
    
    return True

if __name__ == '__main__':
    print("开始转换图标...")
    if convert_ico_to_icns():
        # 使用 iconutil 将图标集转换为 icns 文件
        os.system('iconutil -c icns assets/icon.iconset')
        print("图标转换完成！")
        # 清理临时文件
        os.system('rm -rf assets/icon.iconset')
    else:
        print("图标转换失败！") 