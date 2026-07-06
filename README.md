# Git-Tool v1.5

这是一个给不熟悉 Git 的人使用的小型桌面工具。

目标很简单：

```text
代码写完一版
↓
点击“一键保存并上传”
↓
自动保存版本并上传到云端
```

---

## 功能

1. 选择项目
2. 初始化项目
3. 查看修改
4. 保存版本
5. 上传云端
6. 获取最新版本
7. 查看历史版本
8. 切换分支 / 从旧版本继续修改
9. 分支合并
10. 定时提醒上传代码
11. 一键保存并上传

---

## 运行环境

需要先安装：

1. Python 3.10 或以上
2. Git

安装依赖：

```bat
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

运行：

```bat
run.bat
```

---

## 打包成 exe

双击：

```bat
build.bat
```

打包完成后，exe 在：

```text
dist\Git-Tool-v1.5.exe
```

---

## 第一次使用流程

1. 打开工具
2. 点击「选择项目」
3. 选择你的代码文件夹
4. 点击「初始化项目」
5. 输入 GitHub / Gitee 仓库地址
6. 之后日常只需要点击「一键保存并上传」

---

## 注意

如果上传失败，常见原因是：

1. GitHub / Gitee 没有登录
2. 远程仓库地址不对
3. 云端有新版本，需要先获取最新版本
4. 当前账号没有仓库权限

如果是 GitHub，建议先在命令行执行一次：

```bat
git push
```

完成登录授权后，再使用这个工具。

---

## 2026-07-03 优化说明

本版本将初始化项目时的默认主分支从 `main` 改为 `master`，用于匹配公司 Gitblit 默认 `HEAD -> master` 的显示逻辑。

修复的问题：

```text
新仓库实际提交在 main 分支，Gitblit 首页默认看 master，导致需要手动点击 main 才能查看历史版本。
```

现在新项目初始化后会使用：

```bat
git branch -M master
```

如果之前已经上传到了 `main` 分支，历史仓库仍需要在服务器把 HEAD 指到 main，或者把 main 改回 master。
