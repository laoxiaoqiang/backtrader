#!/usr/bin/env python3
"""
测试matplotlib图表显示能力
"""

import matplotlib
print(f"当前matplotlib后端: {matplotlib.get_backend()}")

# 尝试设置PyQt5后端
try:
    matplotlib.use('pyqt5')
    print(f"设置PyQt5后端成功，当前后端: {matplotlib.get_backend()}")
except Exception as e:
    print(f"设置PyQt5后端失败: {e}")

# 尝试导入matplotlib.pyplot
try:
    import matplotlib.pyplot as plt
    print("matplotlib.pyplot导入成功")
except Exception as e:
    print(f"matplotlib.pyplot导入失败: {e}")

# 尝试创建简单图表
try:
    import numpy as np
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    
    plt.figure()
    plt.plot(x, y)
    plt.title("测试图表")
    
    # 尝试显示图表
    plt.show()
    print("✅ 图表显示成功!")
    
except Exception as e:
    print(f"❌ 图表显示失败: {e}")
    import traceback
    traceback.print_exc()
