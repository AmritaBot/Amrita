"""Amrita机器人入口模块

该模块是Amrita机器人的入口点，负责初始化和运行机器人。
"""

import amrita

# 初始化Amrita框架
amrita.init()

# 加载插件
amrita.load_plugins()


def main():
    """主函数，启动Amrita机器人"""
    amrita.run()


if __name__ == "__main__":
    main()
