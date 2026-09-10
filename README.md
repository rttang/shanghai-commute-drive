# 上海漫游 · 一江两岸

[English](README.en.md) · [文档索引](docs/INDEX.md)

基于 **TypeScript、Three.js、Vite 与 Blender** 的浏览器城市游览和驾驶项目，包含自动观光、手动驾驶、选车、街景分块加载、碰撞、停车和观景活动，以及浏览器本地进度和相册。

**本仓库用于个人私有开发与换机恢复，不作为公开开源发行版。** 当前游戏和真实素材保留，不使用此前讨论的程序化替代版，也未为整个项目授予 MIT 许可。第三方代码、地图、模型和照片保留各自许可，见[资产来源](docs/ASSET_SOURCES.md)。

## 恢复后运行

Git 保存源码、脚本、测试、依赖锁定、技术文档和结构化来源记录。模型、贴图和 Blender 工程保存在同一私有仓库的 Release 附件中。只克隆仓库不会取得这些大型资源。

需要 Node.js 20.19+（或兼容的 22.12+／24 系列）、Python 3.9+、Git 和已登录的 GitHub CLI。

```sh
git clone https://github.com/rttang/shanghai-commute-drive.git
cd shanghai-commute-drive
gh release download backup-2026-09-10 --repo rttang/shanghai-commute-drive --pattern '*.zip' --dir .tooling/restore-downloads
python3 scripts/restore_private_assets.py --parts .tooling/restore-downloads --group runtime
npm ci
npm run dev
```

访问 [本地开发入口](http://127.0.0.1:8080/)。端口占用时启动会失败，不会结束无关进程。ExFAT 外置盘使用 `npm ci --no-bin-links`。需要继续建模时，以 `--group all` 恢复可编辑工程、原始素材和设计参考；脚本不会覆盖内容不同的本地文件。

完整下载、Windows／WSL 和恢复步骤见[资源与恢复说明](docs/RESOURCE_RECOVERY.md)。

## 主要命令

| 命令 | 用途 |
| --- | --- |
| `npm run dev` | 当前源码开发服务，8080 |
| `npm run build` | 类型检查、照片模型定位核对、Vite 构建和静态资源 SHA-256 校验 |
| `npm run preview` | 预览 dist，8080 |
| `npm run test:portable` | 排除私人历史冻结档案检查的回归测试 |
| `npm test` | 原始测试集合，含历史源图及备份保留检查，换机后可能需要原档案 |
| `npm run build:release` | 从匹配的源资产生成压缩、共享贴图与分块发布产物 |
| `npm run preview:release` | 本地发布产物预览，8081 |
| `npm run streets:master` | 离线街景建模，先恢复源工程并配置 Blender |

已有 GLB 时运行网页不需要 Blender。不要把 `npm run models` 当作启动命令，它会重建一批模型。

## 操作和边界

- W／↑ 加速，S／↓ 制动或在符合条件时倒车，A／D／左右键转向，空格手刹。
- P／Esc 暂停和继续，R 回到附近路线，C 切换相机；支持屏幕控件与选车。
- 偏好、行程和相册保存在浏览器本地，不通过 Git 同步。
- 当前默认车辆映射为 10 款。开发街景清单为 47 个分块，已有优化发布清单为 150 个；具体以恢复版本的清单为准。
- 完整城市 GLB 约 947.54 MiB，供离线校验和完整工程使用；浏览器读取分块。动力学属于游戏调校，地图和建筑有简化，不能用于真实导航、测绘或车辆性能认证。

## 技术与资料

| 文档 | 内容 |
| --- | --- |
| [技术方案](docs/TECHNICAL_DESIGN.md) | 技术栈、驾驶、碰撞、渲染、资源管线、压缩、存储与验证 |
| [架构](docs/ARCHITECTURE.zh-CN.md) / [English](docs/ARCHITECTURE.md) | 模块职责和数据流 |
| [资源与恢复](docs/RESOURCE_RECOVERY.md) | 私有附件、去重、哈希、Windows／WSL 和恢复边界 |
| [来源与许可](docs/ASSET_SOURCES.md) | 原作、作者、许可、来源记录和已知限制 |
| [第三方详细说明](THIRD_PARTY_NOTICES.md) | 历史素材和派生条件 |
| [重构记录](docs/REFACTOR.md) | 分阶段实现、历史验证与未完成项 |
| [发布优化](docs/DEPLOYMENT_OPTIMIZATION.md) | 压缩、缓存与既有托管方案 |
| [本次上传报告](docs/private-backup/REPORT.md) | 上传、恢复校验、清理结果和剩余事项 |

本次私有上传不改变素材许可。未来如需公开或新增使用方式，应重新核查具体内容。
