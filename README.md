# Maodan 桌面宠物

住在桌面上的猫蛋（一只银色虎斑美国短毛猫）。它从 PROMIS 的桌面伙伴里独立出来，不再连接 PROMIS，也不需要服务器或网络。

## 启动

双击 **`启动 Maodan.bat`**，猫会出现在屏幕右下角。

- 在一台电脑上第一次运行时，启动文件会自动安装 [pixi](https://pixi.sh)，再按 `pixi.lock` 准备独立的 Python 和 Tk 环境（需要联网一次，无需管理员权限）。如果在线安装失败，仍会尝试电脑上已有的 Python 3 与 Tkinter。
- 猫已经在运行时再双击一次，会把它叫回来（包括用过 *Hide for now* 之后），不会出现第二只。

## 怎么玩

| 操作 | 反应 |
|---|---|
| 拖动 | 往左右拖会跑，往上拖会跳，往下拖会趴下；松手后打招呼 |
| 单击 | 喵一声，随机表演一个小动作 |
| 鼠标停在猫身上 | 眼睛跟着鼠标看 |
| 在任何地方打字 | 一起“学习”（可在菜单里关掉） |
| 什么都不做 | 过一会儿会自己找点事做 |

右键菜单：

- **Play with Maodan**：8 个动作
- **Size**：25% 到 150%
- **Reduce motion**：减少动画
- **Study along while I type**：打字陪学开关
- **Hide for now**：暂时隐藏
- **Quit Maodan**：退出

打字陪学只询问 Windows“现在有没有在按打字键”这一个是/否，不记录按了哪个键，也不会发送到任何地方。

大小和打字陪学开关保存在 `%APPDATA%\Maodan\settings.json`。如果猫意外退出，错误信息会写到同一目录下的 `maodan.log`。

## 开发

```
pixi run start                # 带控制台运行，方便看报错
pixi run test                 # 单元测试
pixi run -e art build-atlas   # 改了 art/ 里的姿势图后，重新生成 assets/ 里的精灵图（会用到 Pillow）
```

## 目录

```
maodan/
├── 启动 Maodan.bat       一键启动
├── maodan.py             桌面宠物本体（只用 Python 标准库和 Tkinter）
├── instance.py           保证只运行一只，再次启动时唤醒已有的那只
├── assets/               运行时用的动画清单和精灵图
├── art/                  生成精灵图用的姿势原图
├── tools/build_atlas.py  把 art/ 排成 assets/ 里的精灵图
├── tests/                单元测试
└── pixi.toml, pixi.lock  Python 环境
```
