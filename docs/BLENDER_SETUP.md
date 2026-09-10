# Blender 安装与移动硬盘存储

本轮完成 Blender 安装、外置存储配置和容量监控。游戏重构、正式车辆与上海地标建模尚未执行。

## 安装结果

- 版本：Blender **5.2.1 LTS**，Apple Silicon 原生版本。
- 应用：`/Applications/Blender.app`，占用约 **907 MiB**。
- 官方来源：[下载页](https://www.blender.org/download/)、[官方镜像安装包](https://mirror.blender.org/release/Blender5.2/blender-5.2.1-macos-arm64.dmg)、[SHA-256 文件](https://download.blender.org/release/Blender5.2/blender-5.2.1.sha256)。
- 安装包 SHA-256：`6409e21de80994db5f4c4a34486b6fd43cea21085b912f7491c53e923acb65a3`，与官网一致。
- 应用签名通过 `codesign --verify --deep --strict`；macOS 评估结果为 `accepted / Notarized Developer ID`，签名主体为 Stichting Blender Foundation。
- 安装磁盘镜像已经卸载；下载包保留在移动硬盘供恢复使用。

## 使用入口

推荐从项目的 [启动Blender.command](../启动Blender.command) 启动。它调用 [scripts/blender-local.sh](../scripts/blender-local.sh)，配置外置临时目录、用户配置和可配置缓存，并让容量守护程序陪同 Blender 运行。

终端中打开模型：

```bash
bash '/Volumes/mzh的固体移动硬盘/shanghai-commute-drive/scripts/blender-local.sh' \
  '/Volumes/mzh的固体移动硬盘/shanghai-commute-drive/assets/blender/validation/installation-check.blend'
```

批量建模使用同一入口：

```bash
bash '/Volumes/mzh的固体移动硬盘/shanghai-commute-drive/scripts/blender-local.sh' \
  --background --python-exit-code 1 \
  --python '/Volumes/mzh的固体移动硬盘/shanghai-commute-drive/scripts/blender-smoke.py'
```

直接从 Finder 打开 `/Applications/Blender.app` 不会自动带上项目启动脚本的环境变量和每 5 秒容量守护。项目建模应使用上述入口，并将模型另存到移动硬盘的项目目录。系统自行管理的诊断日志、Metal 缓存等不能由项目脚本保证全部重定向。

## 文件位置

以下位置均相对于 `/Volumes/mzh的固体移动硬盘/shanghai-commute-drive`。

| 内容 | 路径 |
| --- | --- |
| 模型源文件、GLB、贴图及渲染产物 | `assets/blender/`，按模型或场景建子目录 |
| 本次验证产物 | `assets/blender/validation/` |
| 官方安装包与校验记录 | `.tooling/blender/downloads/` |
| Blender 临时文件及自动保存目录 | `.tooling/blender/tmp/` |
| 可配置缓存 | `.tooling/blender/cache/` |
| Blender 用户偏好 | `.tooling/blender/user/config/` |
| 脚本、用户数据与扩展目录 | `.tooling/blender/user/{scripts,datafiles,extensions}/` |
| 容量记录 | `.tooling/blender/storage.jsonl` |

启动脚本设置 `TMPDIR`、`TMP`、`TEMP`、`XDG_CACHE_HOME`、Python 缓存选项以及 Blender 的用户目录环境变量。Blender 用户偏好中的临时目录和渲染输出目录也已保存到移动硬盘。

移动硬盘使用 ExFAT。此轮安装与产物读写已经验证；后续 Node.js 依赖、符号链接等构建需求的兼容性尚未验证。

## 容量保护与提醒

[scripts/storage_guard.py](../scripts/storage_guard.py) 同时检查 `/Applications` 所在系统盘和移动硬盘。它先确认移动硬盘已挂载、项目实际位于该盘，再写入日志或启动任务。

| 状态 | 行为 |
| --- | --- |
| 两块盘均至少剩余 10 GiB | 正常运行 |
| 任一盘低于 10 GiB | 打印提醒，记录状态变化 |
| 启动前低于 5 GiB，或预计任务占用会使余量低于 5 GiB | 拒绝启动任务，退出码 75 |
| 运行中低于 5 GiB | 暂停由守护程序启动的进程组，保留内存内容 |
| 移动硬盘掉线或无法读取容量 | 暂停进程组，不向系统盘回退写入 |
| 挂载恢复且两块盘均达到 10 GiB | 恢复被暂停的进程 |

运行时每 **5 秒**检查一次，每 **60 秒**及状态变化时记录。暂停期间 Blender 窗口可能无法响应；恢复磁盘挂载或释放空间后会自动继续。该保护只作用于本脚本启动的进程，不处理其他软件；轮询不能撤回两次检查之间已提交给系统的写入。没有做真实拔盘或填满磁盘的破坏性测试。

已创建 Codex 当前任务的 **“上海驾驶项目磁盘容量监控”**，每 **15 分钟**只读检查一次。检测到该项目开发进程或打开项目文件的 Blender 时监控；只在低容量、掉线或告警恢复等状态变化时提醒。容量充足、状态未变或无活动进程时保持安静。此提醒依赖 Codex 自动化能够执行，不替代本地的 5 秒守护。

其他开发命令可以通过同一守护程序执行。例如预留系统盘 1.5 GiB、移动硬盘 2 GiB 后检查：

```bash
python3 '/Volumes/mzh的固体移动硬盘/shanghai-commute-drive/scripts/storage_guard.py' \
  --reserve-system-mib 1536 --reserve-external-mib 2048 check
```

执行需要监控的开发命令时，使用 `storage_guard.py run -- <命令及参数>`。为它传入与任务相符的空间预留值；本轮没有对未来正式模型大小作估算。

## 验证证据

[scripts/blender-smoke.py](../scripts/blender-smoke.py) 实际完成：

1. 创建带倒角和材质的测试模型。
2. 导出 GLB，检查文件头与非空数据。
3. 将 GLB 重新导入 Blender，确认存在有效网格。
4. 保存 `.blend` 源文件。
5. 使用 Cycles CPU 完成 640 × 480 PNG 渲染，已查看渲染图，模型正常可见。
6. 读取实际临时目录与用户配置目录，确认均位于移动硬盘。

产物：[源文件](../assets/blender/validation/installation-check.blend)、[GLB](../assets/blender/validation/installation-check.glb)、[渲染图](../assets/blender/validation/installation-check.png)、[机器可读结果](../assets/blender/validation/result.json)。

容量守护验证：预计空间不足时确实阻止命令执行；子命令退出码保留；模拟 11/9/4 GiB 和掉线状态的分支正确；使用一个真实测试子进程验证了低容量暂停及容量恢复后的继续执行。

桌面 Blender 进程已启动，日志确认读取移动硬盘上的测试 `.blend`，收尾时保持运行。桌面控制工具两次无法启动，因此没有完成窗口截图或菜单交互验证。此次只证明安装及基础建模、导出、渲染链路可用，不代表正式游戏模型或性能已验收。

容量快照（2026-09-08 12:30，Europe/Vilnius）：系统盘约 **14.1 GiB**，移动硬盘约 **81.4 GiB**。安装前移动硬盘曾为约 21.3 GiB，期间两块盘的可用空间均出现变化；本任务没有执行文件清理，容量以实时日志为准。

## 本轮文件变更

全部为新增，没有替换或删除原有游戏文件。

| 文件或目录 | 新增内容 |
| --- | --- |
| `启动Blender.command` | 项目 Blender 启动入口 |
| `scripts/blender-local.sh` | 外置路径配置及受监控的 Blender 启动 |
| `scripts/storage_guard.py` | 双盘容量检查、空间预留、进程暂停与恢复 |
| `scripts/blender-smoke.py` | 安装后的实际建模、导出、重新导入与渲染验证 |
| `assets/blender/validation/` | 测试源文件、GLB、渲染图及验证结果 |
| `.tooling/blender/` | 下载包、配置、缓存、临时文件和容量记录 |
| `docs/BLENDER_SETUP.md` | 本说明与验证记录 |

系统侧新增 `/Applications/Blender.app`；Codex 中新增一条上述容量提醒。没有进行 Git 写入、安装第三方 Blender 插件、修改游戏代码或重启游戏服务。
